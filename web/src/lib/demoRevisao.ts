import type {
  Ajuste, Assignment, Backlog, Capacity, ConfirmacaoDeAjuste, Consequencia,
  PedidoDeAjuste, Previa, Revisao, RascunhoDeAjuste, Schedule, Solucao, Verification,
} from '@/lib/api';
import { diaDe, minutosDe, minutosEntre } from '@/lib/semana';

type ChaveCarga = `${string}|${string}`;

function copiarSolucao(solucao: Solucao): Solucao {
  return {
    status: solucao.status,
    assignments: solucao.assignments.map((item) => ({
      ...item, worker_ids: [...item.worker_ids], window: { ...item.window }, reason_codes: [...item.reason_codes],
    })),
    unscheduled: solucao.unscheduled.map((item) => ({ ...item, details: [...item.details] })),
  };
}

export function criarRevisaoDemo(
  runId: string, schedule: Schedule, backlog: Backlog, verification: Verification,
): Revisao {
  return {
    run_id: runId,
    revision_sequence: 0,
    groups: 0,
    adjustments: [],
    solution: copiarSolucao(schedule),
    verification: { ...verification, violations: [...verification.violations] },
    created_violations: [],
    inherited_violations: [...verification.violations],
    capacities: backlog.capacities.map((item) => ({
      ...item, slots: item.slots.map((slot) => ({ ...slot, window: { ...slot.window } })),
    })),
    duration_overrides: {},
  };
}

function aplicarRemocao(solucao: Solucao, operationId: string): void {
  const indice = solucao.assignments.findIndex((item) => item.operation_id === operationId);
  if (indice < 0) return;
  const [removida] = solucao.assignments.splice(indice, 1);
  if (!solucao.unscheduled.some((item) => item.operation_id === operationId)) {
    solucao.unscheduled.push({
      work_order_id: removida.work_order_id,
      operation_id: removida.operation_id,
      reason: 'manual',
      details: ['Retirada na demonstração interativa.'],
    });
  }
}

function fusoEmMinutos(iso: string): number {
  if (iso.endsWith('Z')) return 0;
  const fuso = /([+-])(\d{2}):(\d{2})$/.exec(iso);
  if (!fuso) return 0;
  const minutos = Number(fuso[2]) * 60 + Number(fuso[3]);
  return fuso[1] === '-' ? -minutos : minutos;
}

function somarMinutos(iso: string, minutos: number): string {
  const fuso = fusoEmMinutos(iso);
  const local = new Date(new Date(iso).getTime() + minutos * 60_000 + fuso * 60_000);
  const parte = [
    local.getUTCFullYear(),
    String(local.getUTCMonth() + 1).padStart(2, '0'),
    String(local.getUTCDate()).padStart(2, '0'),
  ].join('-');
  const hora = [
    String(local.getUTCHours()).padStart(2, '0'),
    String(local.getUTCMinutes()).padStart(2, '0'),
    String(local.getUTCSeconds()).padStart(2, '0'),
  ].join(':');
  const sufixo = iso.endsWith('Z') ? 'Z' : iso.slice(-6);
  return `${parte}T${hora}${sufixo}`;
}

function mover(solucao: Solucao, acao: RascunhoDeAjuste): void {
  if (!acao.operation_id) return;
  const item = solucao.assignments.find((assignment) => assignment.operation_id === acao.operation_id);
  if (!item) return;
  const duracao = minutosDe(item);
  const inicio = acao.target_start
    ?? (acao.target_date ? `${acao.target_date}${item.window.start.slice(10)}` : item.window.start);
  item.window = { start: inicio, end: somarMinutos(inicio, duracao) };
  if (acao.target_worker_id) item.worker_ids = [acao.target_worker_id];
}

function alterarDuracao(
  solucao: Solucao, acao: RascunhoDeAjuste, sobrescritas: Record<string, number>,
): void {
  if (!acao.operation_id || !acao.minutes) return;
  sobrescritas[acao.operation_id] = acao.minutes;
  const item = solucao.assignments.find((assignment) => assignment.operation_id === acao.operation_id);
  if (item) item.window.end = somarMinutos(item.window.start, acao.minutes);
}

/**
 * Onde a ordem incluída começa: a primeira folga contígua da escala daquele dia
 * que a comporta. Encostar toda inclusão no começo do turno empilharia a ordem
 * nova em cima da que já está lá — e a tela desenha as duas no mesmo horário,
 * sem dizer que se sobrepõem. A conta de folga é a mesma que a grade de
 * destinos mostra a quem escolhe (`maiorFolga`), então o lugar sugerido aqui é
 * o lugar que a tela prometeu.
 */
function inicioDaInclusao(
  solucao: Solucao, acao: RascunhoDeAjuste, capacidades: Capacity[], minutos: number,
): string | null {
  if (!acao.target_worker_id || !acao.target_date) return null;
  const ms = (iso: string) => new Date(iso).getTime();
  const turnos = (capacidades.find((item) => item.worker_id === acao.target_worker_id)?.slots ?? [])
    .filter((slot) => diaDe(slot.window.start) === acao.target_date)
    .sort((a, b) => ms(a.window.start) - ms(b.window.start));
  const ocupadas = solucao.assignments
    .filter((item) => (
      item.worker_ids.includes(acao.target_worker_id!) && diaDe(item.window.start) === acao.target_date
    ))
    .map((item) => item.window)
    .sort((a, b) => ms(a.start) - ms(b.start));

  for (const turno of turnos) {
    const abertura = ms(turno.window.start);
    const fim = ms(turno.window.end);
    let cursor = abertura;
    const emISO = () => somarMinutos(turno.window.start, (cursor - abertura) / 60_000);
    for (const janela of ocupadas) {
      if (ms(janela.end) <= cursor || ms(janela.start) >= fim) continue;
      if (ms(janela.start) - cursor >= minutos * 60_000) return emISO();
      cursor = Math.max(cursor, ms(janela.end));
    }
    if (fim - cursor >= minutos * 60_000) return emISO();
  }

  // Nenhuma folga do dia comporta a ordem. Ela entra depois da última que já
  // está lá, estourando a escala: a linha de carga da prévia mostra o excesso,
  // e quem revisa decide. Encostá-la no começo do turno esconderia o estouro
  // numa sobreposição, que o quadro desenha como dois cartões no mesmo horário.
  const abertura = turnos[0]?.window.start ?? `${acao.target_date}T08:00:00-03:00`;
  const ultimoFim = ocupadas.reduce((maior, janela) => Math.max(maior, ms(janela.end)), 0);
  if (ultimoFim <= ms(abertura)) return abertura;
  return somarMinutos(abertura, (ultimoFim - ms(abertura)) / 60_000);
}

function incluir(
  solucao: Solucao, acao: RascunhoDeAjuste, backlog: Backlog,
  capacidades: Capacity[], sobrescritas: Record<string, number>,
): void {
  if (!acao.operation_id || !acao.target_worker_id) return;
  if (solucao.assignments.some((item) => item.operation_id === acao.operation_id)) return;
  const item = backlog.backlog.find((candidato) => candidato.operation.operation_id === acao.operation_id);
  if (!item) return;
  const minutos = sobrescritas[acao.operation_id] ?? item.duration.minutes ?? 60;
  const inicio = inicioDaInclusao(solucao, acao, capacidades, minutos);
  if (!inicio) return;
  solucao.assignments.push({
    work_order_id: item.operation.work_order_id,
    operation_id: item.operation.operation_id,
    worker_ids: [acao.target_worker_id],
    window: { start: inicio, end: somarMinutos(inicio, minutos) },
    priority_score: item.priority.score,
    reason_codes: ['MANUAL_INCLUDE', 'DEMO'],
  });
  solucao.unscheduled = solucao.unscheduled.filter((fora) => fora.operation_id !== acao.operation_id);
}

function lugar(item: Assignment) {
  return { date: diaDe(item.window.start), start: item.window.start, worker_ids: [...item.worker_ids] };
}

function consequenciasDeIndisponibilidade(
  solucao: Solucao, acao: RascunhoDeAjuste, group: number,
): Consequencia[] {
  if (!acao.worker_id || !acao.date_from || !acao.date_to) return [];
  return solucao.assignments
    .filter((item) => (
      item.worker_ids.includes(acao.worker_id!)
      && diaDe(item.window.start) >= acao.date_from!
      && diaDe(item.window.start) <= acao.date_to!
    ))
    .map((item, indice) => ({
      id: `demo-unavailable-${item.operation_id}`,
      adjustment: {
        sequence: indice + 1, group, kind: 'remove', operation_id: item.operation_id,
        target_date: null, target_worker_id: null, target_start: null, replace_worker_id: null,
        minutes: null, worker_id: null, date_from: null, date_to: null, cause: null,
        reason: 'Indisponibilidade simulada', applied_by: 'demonstração', applied_at: new Date().toISOString(),
      },
      default_accepted: true,
      accepted: true,
      locked: false,
      reason_code: 'NO_CANDIDATE_WITH_ROOM',
      if_rejected: 'stay' as const,
      from: lugar(item),
      to: null,
    }));
}

function aplicarIndisponibilidade(
  solucao: Solucao, capacidades: Capacity[], acao: RascunhoDeAjuste, rejeitadas: string[], group: number,
): Consequencia[] {
  const consequencias = consequenciasDeIndisponibilidade(solucao, acao, group);
  consequencias.forEach((item) => {
    item.accepted = !rejeitadas.includes(item.id);
    if (item.accepted && item.adjustment.operation_id) aplicarRemocao(solucao, item.adjustment.operation_id);
  });
  if (acao.worker_id && acao.date_from && acao.date_to) {
    const capacidade = capacidades.find((item) => item.worker_id === acao.worker_id);
    if (capacidade) {
      capacidade.slots = capacidade.slots.filter((slot) => {
        const dia = diaDe(slot.window.start);
        return dia < acao.date_from! || dia > acao.date_to!;
      });
    }
  }
  return consequencias;
}

type Simulacao = {
  solution: Solucao;
  capacities: Capacity[];
  durationOverrides: Record<string, number>;
  consequences: Consequencia[];
};

function simular(
  revisao: Revisao, backlog: Backlog, acoes: RascunhoDeAjuste[], rejeitadas: string[], group: number,
): Simulacao {
  const solution = copiarSolucao(revisao.solution);
  const capacities = revisao.capacities.map((item) => ({
    ...item, slots: item.slots.map((slot) => ({ ...slot, window: { ...slot.window } })),
  }));
  const durationOverrides = { ...revisao.duration_overrides };
  const consequences: Consequencia[] = [];
  acoes.forEach((acao) => {
    if (acao.kind === 'remove' && acao.operation_id) aplicarRemocao(solution, acao.operation_id);
    if (acao.kind === 'move') mover(solution, acao);
    if (acao.kind === 'duration') alterarDuracao(solution, acao, durationOverrides);
    if (acao.kind === 'include') incluir(solution, acao, backlog, capacities, durationOverrides);
    if (acao.kind === 'unavailable') {
      consequences.push(...aplicarIndisponibilidade(solution, capacities, acao, rejeitadas, group));
    }
  });
  return { solution, capacities, durationOverrides, consequences };
}

function cargas(solucao: Solucao): Map<ChaveCarga, number> {
  const resultado = new Map<ChaveCarga, number>();
  solucao.assignments.forEach((item) => {
    const dia = diaDe(item.window.start);
    item.worker_ids.forEach((workerId) => {
      const chave: ChaveCarga = `${workerId}|${dia}`;
      resultado.set(chave, (resultado.get(chave) ?? 0) + minutosDe(item));
    });
  });
  return resultado;
}

function escalas(revisao: Revisao): Map<ChaveCarga, number> {
  const resultado = new Map<ChaveCarga, number>();
  revisao.capacities.forEach((capacidade) => {
    capacidade.slots.forEach((slot) => {
      const chave: ChaveCarga = `${capacidade.worker_id}|${diaDe(slot.window.start)}`;
      resultado.set(chave, (resultado.get(chave) ?? 0)
        + minutosEntre(slot.window.start, slot.window.end));
    });
  });
  return resultado;
}

function cargaQueMuda(antes: Solucao, depois: Solucao, revisao: Revisao): Previa['load'] {
  const inicial = cargas(antes);
  const final = cargas(depois);
  const escala = escalas(revisao);
  const chaves = new Set([...inicial.keys(), ...final.keys()]);
  return [...chaves]
    .filter((chave) => (inicial.get(chave) ?? 0) !== (final.get(chave) ?? 0))
    .sort()
    .map((chave) => {
      const [worker_id, date] = chave.split('|');
      return {
        worker_id, date,
        before_minutes: inicial.get(chave) ?? 0,
        after_minutes: final.get(chave) ?? 0,
        shift_minutes: escala.get(chave) ?? 0,
      };
    });
}

export function preverAjustesDemo(revisao: Revisao, backlog: Backlog, body: PedidoDeAjuste): Previa {
  const simulacao = simular(revisao, backlog, body.actions, body.rejected, revisao.groups + 1);
  return {
    run_id: revisao.run_id,
    base_revision: revisao.revision_sequence,
    consequences: simulacao.consequences,
    load: cargaQueMuda(revisao.solution, simulacao.solution, {
      ...revisao, capacities: simulacao.capacities,
    }),
    violations: { created: [], resolved: [] },
    notes: [],
  };
}

function ajusteGravado(
  acao: RascunhoDeAjuste, sequence: number, group: number,
  body: ConfirmacaoDeAjuste, appliedAt: string,
): Ajuste {
  return {
    sequence,
    group,
    kind: acao.kind,
    operation_id: acao.operation_id ?? null,
    target_date: acao.target_date ?? null,
    target_worker_id: acao.target_worker_id ?? null,
    target_start: acao.target_start ?? null,
    replace_worker_id: acao.replace_worker_id ?? null,
    minutes: acao.minutes ?? null,
    worker_id: acao.worker_id ?? null,
    date_from: acao.date_from ?? null,
    date_to: acao.date_to ?? null,
    cause: acao.cause ?? null,
    reason: body.reason,
    applied_by: body.recorded_by,
    applied_at: appliedAt,
  };
}

export function confirmarAjustesDemo(
  revisao: Revisao, backlog: Backlog, body: ConfirmacaoDeAjuste,
): Revisao {
  const grupo = revisao.groups + 1;
  const simulacao = simular(revisao, backlog, body.actions, body.rejected, grupo);
  const inicio = revisao.revision_sequence + 1;
  const aplicadoEm = new Date().toISOString();
  // O grupo grava a ação e toda consequência aceita, nesta ordem — é o que o
  // servidor faz, e é a conta que a prévia já mostrou a quem confirma. Gravar
  // só as ações faria o rodapé contar menos ajustes do que a tela prometeu.
  const novos: Ajuste[] = [
    ...body.actions.map((acao) => ajusteGravado(acao, 0, grupo, body, aplicadoEm)),
    ...simulacao.consequences
      .filter((consequencia) => consequencia.accepted)
      .map((consequencia) => ({
        ...consequencia.adjustment,
        group: grupo,
        applied_by: body.recorded_by,
        applied_at: aplicadoEm,
      })),
  ].map((ajuste, indice) => ({ ...ajuste, sequence: inicio + indice }));
  return {
    ...revisao,
    revision_sequence: revisao.revision_sequence + novos.length,
    groups: grupo,
    adjustments: [...revisao.adjustments, ...novos],
    solution: simulacao.solution,
    capacities: simulacao.capacities,
    duration_overrides: simulacao.durationOverrides,
  };
}
