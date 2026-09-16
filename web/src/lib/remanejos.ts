import type { Assignment } from '@/lib/api';
import { deslocamentoDe } from '@/lib/reordenar';

/**
 * O programador discordando do dia em que o agente encaixou a ordem.
 *
 * Gravado como ajuste da revisão (`move` com `target_start`); este tipo é a
 * leitura desse ajuste para as marcas da tela e para o texto do feedback.
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
