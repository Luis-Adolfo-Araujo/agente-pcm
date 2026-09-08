import type { Assignment, Schedule } from '@/lib/api';

/**
 * Uma troca é o programador discordando do executante que o agente escolheu.
 *
 * Ela não reescreve a proposta gravada: a API do piloto não tem caminho de
 * escrita para `Assignment.worker_ids`, e inventar um aqui faria a tela mentir
 * sobre o que está no banco. O que existe de verdade é o feedback registrado —
 * a troca vive na sessão, por cima da proposta, e diz isso na cara.
 */
export type Troca = {
  operation_id: string;
  de: string;
  para: string;
  motivo: string;
  em: string;
};

/** A proposta do agente com as discordâncias da sessão aplicadas por cima. */
export function aplicarTrocas(schedule: Schedule, trocas: Troca[]): Schedule {
  if (trocas.length === 0) return schedule;
  const porOrdem = new Map(trocas.map((t) => [t.operation_id, t]));
  const assignments = schedule.assignments.map((a): Assignment => {
    const troca = porOrdem.get(a.operation_id);
    if (!troca) return a;
    const worker_ids = a.worker_ids.map((w) => (w === troca.de ? troca.para : w));
    // Se `de` não estava mais na alocação, a troca é de uma versão anterior da
    // tela e não tem o que fazer: devolvemos a alocação intacta.
    if (worker_ids.every((w, i) => w === a.worker_ids[i])) return a;
    return { ...a, worker_ids };
  });
  return { ...schedule, assignments };
}

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
