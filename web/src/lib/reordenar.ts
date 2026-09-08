import type { Assignment, Schedule } from '@/lib/api';
import { diaDe, minutosDe } from '@/lib/semana';

/**
 * A sequência que o programador desenhou para o dia de uma pessoa.
 *
 * Como a troca de executante, isto não reescreve a proposta: a API não tem
 * caminho de escrita para as janelas. O que existe de verdade é o feedback
 * registrado; a sequência vive na sessão, por cima da proposta.
 */
export type Reordenacao = {
  tecnico: string;
  dia: string;
  /** operation_id na ordem desejada. */
  sequencia: string[];
  registrada: boolean;
};

/** O deslocamento que a janela original carrega. Sem ele, o dia vira UTC. */
export function deslocamentoDe(iso: string): string {
  const achado = iso.match(/(Z|[+-]\d{2}:\d{2})$/);
  return achado ? achado[1] : 'Z';
}

function minutosDoDeslocamento(offset: string): number {
  if (offset === 'Z') return 0;
  const sinal = offset[0] === '-' ? -1 : 1;
  return sinal * (Number(offset.slice(1, 3)) * 60 + Number(offset.slice(4, 6)));
}

/**
 * Formata um instante no mesmo fuso da janela de origem. `toISOString` daria
 * UTC, e aí a ordem das 4 da manhã cairia no dia anterior na hora de agrupar.
 */
export function instanteEm(ms: number, offset: string): string {
  const deslocada = new Date(ms + minutosDoDeslocamento(offset) * 60000);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${deslocada.getUTCFullYear()}-${p(deslocada.getUTCMonth() + 1)}-${p(deslocada.getUTCDate())}`
    + `T${p(deslocada.getUTCHours())}:${p(deslocada.getUTCMinutes())}:${p(deslocada.getUTCSeconds())}${offset}`;
}

/**
 * Remonta o dia na sequência pedida, colando uma ordem na outra a partir do
 * primeiro início original. Cada ordem leva a própria duração, então nunca há
 * sobreposição — o preço é que mover uma desloca o horário de todas as
 * seguintes, e os intervalos que o otimizador tinha deixado somem.
 */
export function reempacotar(ordens: Assignment[], sequencia: string[]): Assignment[] {
  if (ordens.length === 0) return ordens;

  const porId = new Map(ordens.map((a) => [a.operation_id, a]));
  const fila: Assignment[] = [];
  sequencia.forEach((id) => {
    const achada = porId.get(id);
    if (achada) { fila.push(achada); porId.delete(id); }
  });
  // Quem não estava na sequência — chegou depois, por uma troca de executante —
  // fica no fim, na ordem em que já estava.
  ordens.forEach((a) => { if (porId.has(a.operation_id)) fila.push(a); });

  const offset = deslocamentoDe(ordens[0].window.start);
  let cursor = new Date(ordens[0].window.start).getTime();
  return fila.map((a) => {
    const duracao = minutosDe(a) * 60000;
    const janela = { start: instanteEm(cursor, offset), end: instanteEm(cursor + duracao, offset) };
    cursor += duracao;
    return { ...a, window: janela };
  });
}

export type Mudanca = {
  operation_id: string;
  dePosicao: number;
  paraPosicao: number;
  deInicio: string;
  paraInicio: string;
  /**
   * Se a ordem saiu do lugar, ou só foi empurrada pelo reempacotamento. A
   * distinção decide o que vira feedback: mover uma ordem desloca o horário de
   * todas as seguintes, e gravar isso como "o agente errou" em cada uma delas
   * ensinaria o contrário do que a pessoa quis dizer.
   */
  mudouPosicao: boolean;
};

/** O que de fato mudou entre o dia proposto e o dia remexido. */
export function mudancas(original: Assignment[], novo: Assignment[]): Mudanca[] {
  const antes = new Map(original.map((a, i) => [a.operation_id, { i, inicio: a.window.start }]));
  return novo
    .map((a, i) => {
      const anterior = antes.get(a.operation_id);
      if (!anterior) return null;
      if (anterior.i === i && anterior.inicio === a.window.start) return null;
      return {
        operation_id: a.operation_id,
        dePosicao: anterior.i + 1,
        paraPosicao: i + 1,
        deInicio: anterior.inicio,
        paraInicio: a.window.start,
        mudouPosicao: anterior.i !== i,
      };
    })
    .filter((m): m is Mudanca => m !== null);
}

/** As ordens de uma pessoa num dia, em ordem de relógio. */
export function ordensDoDia(schedule: Schedule, tecnico: string, dia: string): Assignment[] {
  return schedule.assignments
    .filter((a) => diaDe(a.window.start) === dia && a.worker_ids.includes(tecnico))
    .sort((a, b) => a.window.start.localeCompare(b.window.start));
}

/** A semana com as sequências da sessão aplicadas por cima. */
export function aplicarReordens(schedule: Schedule, reordens: Reordenacao[]): Schedule {
  if (reordens.length === 0) return schedule;
  const novas = new Map<string, Assignment>();
  reordens.forEach((r) => {
    // Cada reordenação lê a semana já com as anteriores aplicadas: duas pessoas
    // podem dividir uma ordem, e a segunda precisa ver o que a primeira fez.
    const atual = schedule.assignments.map((a) => novas.get(a.operation_id) ?? a);
    const dia = ordensDoDia({ ...schedule, assignments: atual }, r.tecnico, r.dia);
    reempacotar(dia, r.sequencia).forEach((a) => novas.set(a.operation_id, a));
  });
  if (novas.size === 0) return schedule;
  return { ...schedule, assignments: schedule.assignments.map((a) => novas.get(a.operation_id) ?? a) };
}

/** Só o que a pessoa de fato decidiu — é isto que vira feedback. */
export function trocasDePosicao(lista: Mudanca[]): Mudanca[] {
  return lista.filter((m) => m.mudouPosicao);
}

export function reordenacaoDe(
  reordens: Reordenacao[], tecnico: string, dia: string,
): Reordenacao | undefined {
  return reordens.find((r) => r.tecnico === tecnico && r.dia === dia);
}

/** Move um item de uma posição para outra. É o que o arraste e o teclado fazem. */
export function mover<T>(lista: T[], de: number, para: number): T[] {
  if (de === para || de < 0 || de >= lista.length) return lista;
  const destino = Math.max(0, Math.min(lista.length - 1, para));
  const copia = [...lista];
  const [item] = copia.splice(de, 1);
  copia.splice(destino, 0, item);
  return copia;
}

/** O texto que vai para o `reason` do feedback: a API só guarda uma string. */
export function motivoDaReordenacao(m: Mudanca, hora: (iso: string) => string, motivo: string): string {
  const movimento = `reordenada: ${m.dePosicao}ª → ${m.paraPosicao}ª posição do dia `
    + `(${hora(m.deInicio)} → ${hora(m.paraInicio)})`;
  const texto = motivo.trim();
  return texto ? `${movimento} · ${texto}` : movimento;
}
