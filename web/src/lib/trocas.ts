import type { Assignment } from '@/lib/api';

/**
 * Uma troca é o programador discordando do executante que o agente escolheu.
 *
 * Ela é gravada como ajuste da revisão (`move` com `replace_worker_id`), e este
 * tipo é a leitura desse ajuste para as marcas da tela: a proposta do agente
 * continua intocada, e quem sabe da troca é a revisão, não a sessão.
 */
export type Troca = {
  operation_id: string;
  de: string;
  para: string;
  motivo: string;
  em: string;
};

export function trocaDaOrdem(trocas: Troca[], operationId: string): Troca | undefined {
  return trocas.find((t) => t.operation_id === operationId);
}

/** Quantas ordens de um técnico, num dado conjunto, vieram de troca manual. */
export function trocasNoConjunto(trocas: Troca[], ordens: Assignment[]): number {
  const ids = new Set(ordens.map((a) => a.operation_id));
  return trocas.filter((t) => ids.has(t.operation_id)).length;
}

/**
 * O texto que vai para o `reason` do feedback. A API só guarda uma string, então
 * o destino precisa estar dentro dela ou a intenção se perde no golden set — e é
 * ele que cumpre o mínimo de um caractere quando a justificativa vem vazia.
 */
export function motivoDoFeedback(troca: Pick<Troca, 'de' | 'para' | 'motivo'>): string {
  const movimento = `passar de ${troca.de} para ${troca.para}`;
  const motivo = troca.motivo.trim();
  return motivo ? `${movimento} · ${motivo}` : movimento;
}
