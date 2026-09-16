import type { Assignment, Capacity, Enriched } from '@/lib/api';
import { diaDe } from '@/lib/semana';

type Janela = { start: string; end: string };

/**
 * A maior folga contígua, em minutos, dentro da escala e fora do que já está
 * ocupado. É contígua porque uma ordem é um bloco só: duas horas soltas em
 * pedaços de meia hora não recebem uma ordem de duas horas.
 */
export function maiorFolga(escala: Janela[], ocupadas: Janela[]): number {
  const ms = (iso: string) => new Date(iso).getTime();
  const blocos = ocupadas.map((o) => [ms(o.start), ms(o.end)] as const).sort((a, b) => a[0] - b[0]);
  let maior = 0;
  escala.forEach((janela) => {
    let cursor = ms(janela.start);
    const fim = ms(janela.end);
    blocos.forEach(([inicio, termino]) => {
      if (termino <= cursor || inicio >= fim) return;
      maior = Math.max(maior, inicio - cursor);
      cursor = Math.max(cursor, termino);
    });
    maior = Math.max(maior, fim - cursor);
  });
  return Math.max(0, Math.floor(maior / 60000));
}

export type CelulaDestino = { dia: string; escala: number; folga: number; cabe: boolean };

export type LinhaDestino = {
  worker_id: string;
  score: number;
  eligible: boolean;
  /** Por que o agente não o considerou elegível, quando não considerou. */
  motivos: string[];
  celulas: CelulaDestino[];
  cabeEmAlgum: boolean;
};

/**
 * A grade de destinos: os candidatos que o agente avaliou × os dias do
 * período. Elegíveis primeiro, e entre eles quem tem onde caber; o score do
 * agente desempata. É uma leitura para escolher — a prévia é quem diz o que de
 * fato acontece, com a disponibilidade do servidor.
 */
export function destinosDaInclusao(
  item: Enriched,
  dias: string[],
  assignments: Assignment[],
  capacidades: Capacity[],
  minutos: number,
): LinhaDestino[] {
  return item.executants
    .map((candidato): LinhaDestino => {
      const slots = capacidades.find((c) => c.worker_id === candidato.worker_id)?.slots ?? [];
      const celulas = dias.map((dia): CelulaDestino => {
        const escalaDoDia = slots.filter((s) => diaDe(s.window.start) === dia).map((s) => s.window);
        const ocupadas = assignments
          .filter((a) => a.worker_ids.includes(candidato.worker_id) && diaDe(a.window.start) === dia)
          .map((a) => a.window);
        const escala = escalaDoDia.reduce(
          (soma, j) => soma + (new Date(j.end).getTime() - new Date(j.start).getTime()) / 60000,
          0,
        );
        const folga = maiorFolga(escalaDoDia, ocupadas);
        return { dia, escala, folga, cabe: folga >= minutos };
      });
      return {
        worker_id: candidato.worker_id,
        score: candidato.score,
        eligible: candidato.eligible,
        motivos: candidato.reason_codes,
        celulas,
        cabeEmAlgum: celulas.some((c) => c.cabe),
      };
    })
    .sort((a, b) => (
      Number(b.eligible) - Number(a.eligible)
      || Number(b.cabeEmAlgum) - Number(a.cabeEmAlgum)
      || b.score - a.score
      || a.worker_id.localeCompare(b.worker_id)
    ));
}
