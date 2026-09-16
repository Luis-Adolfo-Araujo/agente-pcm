import type { Consequencia, Lugar, Previa, RascunhoDeAjuste } from '@/lib/api';
import { rotuloDia } from '@/lib/semana';

/** Para onde a consequência leva a ordem, depois da escolha de quem revisa. */
export type Destino = 'move' | 'fora' | 'inclui' | 'fica';

export function destinoEfetivo(c: Consequencia): Destino {
  if (!c.accepted) return c.if_rejected === 'remove' ? 'fora' : 'fica';
  if (c.adjustment.kind === 'remove') return 'fora';
  if (c.adjustment.kind === 'include') return 'inclui';
  return 'move';
}

/** Quantos ajustes a confirmação grava: as ações e toda consequência que muda algo. */
export function quantosAjustes(acoes: RascunhoDeAjuste[], previa: Previa): number {
  return acoes.length + previa.consequences.filter((c) => destinoEfetivo(c) !== 'fica').length;
}

export function resumoDasConsequencias(previa: Previa): string {
  const conta: Record<Destino, number> = { move: 0, fora: 0, inclui: 0, fica: 0 };
  previa.consequences.forEach((c) => { conta[destinoEfetivo(c)] += 1; });
  const partes: string[] = [];
  if (conta.move > 0) partes.push(`${conta.move} ${conta.move === 1 ? 'muda' : 'mudam'} de lugar`);
  if (conta.fora > 0) partes.push(`${conta.fora} ${conta.fora === 1 ? 'vai' : 'vão'} para fora da semana`);
  if (conta.inclui > 0) partes.push(`${conta.inclui} ${conta.inclui === 1 ? 'entra' : 'entram'} na semana`);
  return partes.length > 0 ? `${partes.join(' · ')}.` : 'Nenhuma outra ordem muda.';
}

/**
 * "qua 19/08 07:30 Técnico-A", ou "fora da semana". A hora sai da própria
 * string, como o dia: converter para o fuso do navegador mostraria outro
 * horário do que a janela da ordem diz.
 */
export function descreverLugar(lugar: Lugar | null): string {
  if (!lugar) return 'fora da semana';
  const { nome, numero } = rotuloDia(lugar.date);
  return `${nome} ${numero} ${lugar.start.slice(11, 16)} ${lugar.worker_ids.join(', ')}`;
}
