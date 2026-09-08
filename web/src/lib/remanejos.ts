import type { Assignment, Schedule } from '@/lib/api';
import { deslocamentoDe, instanteEm } from '@/lib/reordenar';
import { minutosDe } from '@/lib/semana';

/**
 * O programador discordando do dia em que o agente encaixou a ordem.
 *
 * Como a troca e a sequência, isto não reescreve a proposta: a API não tem
 * caminho de escrita para a janela. O que existe de verdade é o feedback
 * gravado; o remanejo vive na sessão, por cima da proposta.
 */
export type Remanejo = {
  operation_id: string;
  deDia: string;
  deInicio: string;
  deTecnico: string;
  paraDia: string;
  paraInicio: string;
  paraTecnico: string;
  motivo: string;
  em: string;
};

/** O instante do dia novo, no mesmo fuso da janela que a ordem já tinha. */
export function inicioNoDia(janelaOriginal: string, dia: string, hhmm: string): string {
  return `${dia}T${hhmm}:00${deslocamentoDe(janelaOriginal)}`;
}

/** A semana com os remanejos da sessão aplicados por cima. */
export function aplicarRemanejos(schedule: Schedule, remanejos: Remanejo[]): Schedule {
  if (remanejos.length === 0) return schedule;
  const porOrdem = new Map(remanejos.map((r) => [r.operation_id, r]));
  const assignments = schedule.assignments.map((a): Assignment => {
    const remanejo = porOrdem.get(a.operation_id);
    if (!remanejo) return a;
    const offset = deslocamentoDe(a.window.start);
    const inicio = remanejo.paraInicio;
    const fim = instanteEm(new Date(inicio).getTime() + minutosDe(a) * 60000, offset);
    // O executante vira o escolhido, e só ele: uma ordem dividida entre duas
    // pessoas não tem como manter a segunda, que pode nem ter escala no dia novo.
    return { ...a, worker_ids: [remanejo.paraTecnico], window: { start: inicio, end: fim } };
  });
  return { ...schedule, assignments };
}

export function remanejoDaOrdem(remanejos: Remanejo[], operationId: string): Remanejo | undefined {
  return remanejos.find((r) => r.operation_id === operationId);
}

/** Quantas ordens de um conjunto vieram de outro dia. */
export function remanejosNoConjunto(remanejos: Remanejo[], ordens: Assignment[]): number {
  const ids = new Set(ordens.map((a) => a.operation_id));
  return remanejos.filter((r) => ids.has(r.operation_id)).length;
}

/**
 * O texto que vai para o `reason`. A API só guarda uma string, então dia, hora e
 * pessoa dos dois lados precisam caber nela — e é o movimento que cumpre o
 * mínimo de um caractere quando a justificativa vem vazia.
 */
export function motivoDoRemanejo(r: Omit<Remanejo, 'operation_id' | 'em'>): string {
  const dia = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
  const hora = (iso: string) => iso.slice(11, 16);
  const movimento = `passar de ${dia(r.deInicio)} ${hora(r.deInicio)} com ${r.deTecnico} `
    + `para ${dia(r.paraInicio)} ${hora(r.paraInicio)} com ${r.paraTecnico}`;
  const motivo = r.motivo.trim();
  return motivo ? `${movimento} · ${motivo}` : movimento;
}
