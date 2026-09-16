import type { Causa, RascunhoDeAjuste } from '@/lib/api';
import { lerHhmm } from '@/lib/duracao';

/**
 * Os pedidos que os formulários de ajuste montam. `null` quer dizer "ainda não
 * dá para pedir": a prévia espera o formulário ficar completo em vez de
 * perguntar à API o que ela recusaria.
 */
export function pedidoDeIndisponibilidade(
  tecnico: string, de: string, ate: string, causa: Causa | '', dias: string[],
): RascunhoDeAjuste[] | null {
  if (!causa || !dias.includes(de) || !dias.includes(ate) || de > ate) return null;
  return [{ kind: 'unavailable', worker_id: tecnico, date_from: de, date_to: ate, cause: causa }];
}

export function pedidoDeDuracao(
  operationId: string, texto: string, atual: number | null,
): RascunhoDeAjuste[] | null {
  const minutos = lerHhmm(texto);
  if (minutos === null || minutos === atual) return null;
  return [{ kind: 'duration', operation_id: operationId, minutes: minutos }];
}

export type Escolha = { tecnico: string; dia: string };

/**
 * Incluir uma ordem sem duração pede o tempo junto: sem ele, a ordem não tem
 * tamanho para encaixar. O par vai no mesmo grupo, a duração primeiro.
 */
export function pedidoDeInclusao(
  operationId: string, escolha: Escolha | null, minutosNovos: number | null, precisaDuracao: boolean,
): RascunhoDeAjuste[] | null {
  if (!escolha) return null;
  const incluir: RascunhoDeAjuste = {
    kind: 'include', operation_id: operationId, target_date: escolha.dia, target_worker_id: escolha.tecnico,
  };
  if (!precisaDuracao) return [incluir];
  if (minutosNovos === null) return null;
  return [{ kind: 'duration', operation_id: operationId, minutes: minutosNovos }, incluir];
}
