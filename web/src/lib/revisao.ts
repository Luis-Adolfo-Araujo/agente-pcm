import type { Ajuste, Backlog, Causa, Revisao, Schedule, TipoDeAjuste } from '@/lib/api';
import type { Remanejo } from '@/lib/remanejos';
import type { Troca } from '@/lib/trocas';
import { TIPO_DE_AJUSTE } from '@/lib/rotulos';
import { diaDe } from '@/lib/semana';

/**
 * A semana que a tela mostra é a revisão: a proposta do agente com os ajustes
 * gravados por cima. A cobertura continua sendo a do agente — ela conta o que
 * a montagem conseguiu, e é isso que o cartão de cobertura promete.
 */
export function semanaRevisada(proposta: Schedule, revisao: Revisao | null): Schedule {
  if (!revisao || revisao.revision_sequence === 0) return proposta;
  return {
    ...proposta,
    status: revisao.solution.status,
    assignments: revisao.solution.assignments,
    unscheduled: revisao.solution.unscheduled,
  };
}

/** O backlog com a escala sem ausências e as durações que a revisão alterou. */
export function backlogRevisado(backlog: Backlog, revisao: Revisao | null): Backlog {
  if (!revisao || revisao.revision_sequence === 0) return backlog;
  const minutos = revisao.duration_overrides;
  return {
    capacities: revisao.capacities,
    backlog: backlog.backlog.map((item) => {
      const novo = minutos[item.operation.operation_id];
      return novo === undefined ? item : { ...item, duration: { ...item.duration, minutes: novo } };
    }),
  };
}

function emOrdem(ajustes: Ajuste[]): Ajuste[] {
  return [...ajustes].sort((a, b) => a.sequence - b.sequence);
}

/**
 * As trocas de executante gravadas: `move` que põe uma pessoa no lugar de
 * outra. O empurrão da cascata também usa `replace_worker_id`, mas com a mesma
 * pessoa dos dois lados — ele muda a hora, não quem faz.
 */
export function trocasDaRevisao(ajustes: Ajuste[]): Troca[] {
  const ultimas = new Map<string, Troca>();
  emOrdem(ajustes).forEach((a) => {
    if (a.kind !== 'move' || !a.operation_id || !a.replace_worker_id || !a.target_worker_id) return;
    if (a.replace_worker_id === a.target_worker_id) return;
    ultimas.set(a.operation_id, {
      operation_id: a.operation_id, de: a.replace_worker_id, para: a.target_worker_id,
      motivo: a.reason ?? '', em: a.applied_at,
    });
  });
  return [...ultimas.values()];
}

/**
 * Ordens que foram movidas e estão, na revisão, num dia diferente do que o
 * agente propôs. Uma que voltou ao dia original deixa de ser marcada: o cartão
 * diz onde a ordem está, não por onde ela passou.
 */
export function remanejosDaRevisao(ajustes: Ajuste[], proposta: Schedule, semana: Schedule): Remanejo[] {
  const original = new Map(proposta.assignments.map((a) => [a.operation_id, a]));
  const atual = new Map(semana.assignments.map((a) => [a.operation_id, a]));
  const ultimos = new Map<string, Ajuste>();
  emOrdem(ajustes).forEach((a) => {
    if (a.kind === 'move' && a.operation_id) ultimos.set(a.operation_id, a);
  });
  const remanejos: Remanejo[] = [];
  ultimos.forEach((a, operationId) => {
    const antes = original.get(operationId);
    const agora = atual.get(operationId);
    if (!antes || !agora || diaDe(antes.window.start) === diaDe(agora.window.start)) return;
    remanejos.push({
      operation_id: operationId,
      deDia: diaDe(antes.window.start), deInicio: antes.window.start, deTecnico: antes.worker_ids[0] ?? '',
      paraDia: diaDe(agora.window.start), paraInicio: agora.window.start, paraTecnico: agora.worker_ids[0] ?? '',
      motivo: a.reason ?? '', em: a.applied_at,
    });
  });
  return remanejos;
}

/** Ordens que entraram na semana por ajuste e continuam nela. */
export function incluidasDaRevisao(ajustes: Ajuste[], proposta: Schedule, semana: Schedule): Set<string> {
  const propostas = new Set(proposta.assignments.map((a) => a.operation_id));
  const incluidas = new Set(
    ajustes.filter((a) => a.kind === 'include' && a.operation_id).map((a) => a.operation_id as string),
  );
  return new Set(
    semana.assignments
      .map((a) => a.operation_id)
      .filter((id) => incluidas.has(id) && !propostas.has(id)),
  );
}

/** A duração que o agente tinha estimado, para cada ordem cuja duração foi alterada. */
export function duracoesAntes(revisao: Revisao | null, backlogDoAgente: Backlog): Map<string, number | null> {
  const antes = new Map<string, number | null>();
  if (!revisao) return antes;
  const doAgente = new Map(backlogDoAgente.backlog.map((i) => [i.operation.operation_id, i.duration.minutes]));
  Object.keys(revisao.duration_overrides).forEach((id) => antes.set(id, doAgente.get(id) ?? null));
  return antes;
}

/** Dia a dia, quem está indisponível e por quê. Só dias do período entram. */
export function indisponiveisDaRevisao(ajustes: Ajuste[], dias: string[]): Map<string, Map<string, Causa>> {
  const mapa = new Map<string, Map<string, Causa>>();
  emOrdem(ajustes).forEach((a) => {
    if (a.kind !== 'unavailable' || !a.worker_id || !a.date_from || !a.date_to || !a.cause) return;
    const { date_from: de, date_to: ate, cause } = a;
    const doTecnico = mapa.get(a.worker_id) ?? new Map<string, Causa>();
    dias.filter((d) => d >= de && d <= ate).forEach((d) => doTecnico.set(d, cause));
    mapa.set(a.worker_id, doTecnico);
  });
  return mapa;
}

export type Grupo = {
  grupo: number;
  quem: string;
  em: string;
  total: number;
  porTipo: Partial<Record<TipoDeAjuste, number>>;
};

/** Uma confirmação é um grupo; a lista vem do mais novo, que é o que desfazer tira. */
export function gruposDaRevisao(ajustes: Ajuste[]): Grupo[] {
  const grupos = new Map<number, Grupo>();
  emOrdem(ajustes).forEach((a) => {
    const grupo = grupos.get(a.group) ?? { grupo: a.group, quem: a.applied_by, em: a.applied_at, total: 0, porTipo: {} };
    grupo.total += 1;
    grupo.porTipo[a.kind] = (grupo.porTipo[a.kind] ?? 0) + 1;
    grupos.set(a.group, grupo);
  });
  return [...grupos.values()].sort((a, b) => b.grupo - a.grupo);
}

/**
 * O `reason` do feedback. A API só guarda uma string, então o movimento vai
 * sempre — é ele que cumpre o mínimo de um caractere quando a justificativa
 * vem vazia, e sem separador pendurado.
 */
export function motivoDeAjuste(movimento: string, motivo: string): string {
  const texto = motivo.trim();
  return texto ? `${movimento} · ${texto}` : movimento;
}

/** "1 indisponibilidade, 5 movimentos": a ação primeiro, as consequências depois. */
export function resumoDoGrupo(porTipo: Partial<Record<TipoDeAjuste, number>>): string {
  const ordem: TipoDeAjuste[] = ['unavailable', 'include', 'duration', 'move', 'remove'];
  const partes = ordem
    .filter((tipo) => (porTipo[tipo] ?? 0) > 0)
    .map((tipo) => {
      const quantos = porTipo[tipo] ?? 0;
      const [singular, plural] = TIPO_DE_AJUSTE[tipo];
      return `${quantos} ${quantos === 1 ? singular : plural}`;
    });
  return partes.join(', ');
}

/** As marcas que o cartão mostra além de troca e movimento. */
export type MarcasDaRevisao = {
  /** Entraram na semana por ajuste. */
  incluidas: Set<string>;
  /** Tiveram a duração alterada; o valor é o que o agente tinha estimado. */
  duracaoAntes: Map<string, number | null>;
};
