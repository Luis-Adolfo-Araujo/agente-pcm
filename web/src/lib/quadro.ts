import type { Assignment, Capacity } from '@/lib/api';
import { carga, diaDe, escalaDoDia, escalaImpossivel } from '@/lib/semana';
import { remanejosNoConjunto, type Remanejo } from '@/lib/remanejos';
import { trocasNoConjunto, type Troca } from '@/lib/trocas';

/** Uma coluna do quadro: o dia de uma pessoa, com o que a escala dela permite. */
export type Coluna = {
  tecnico: string;
  /** Em ordem de relógio — é assim que a coluna é lida de cima para baixo. */
  ordens: Assignment[];
  minutos: number;
  escala: number;
  estourou: boolean;
  impossivel: boolean;
  trocadas: number;
  /** Quantas chegaram de outro dia, por remanejo da sessão. */
  movidas: number;
};

/**
 * As colunas do dia: quem tem escala declarada, mais quem tem ordem sem escala.
 * Esconder o segundo caso apagaria da tela justamente a alocação que não deveria
 * existir; deixar a coluna vazia de quem tem escala é o que dá para onde arrastar.
 */
export function colunasDoDia(
  assignments: Assignment[],
  capacidades: Capacity[],
  dia: string,
  trocas: Troca[],
  remanejos: Remanejo[] = [],
): Coluna[] {
  const porTecnico = new Map<string, Assignment[]>();
  capacidades.forEach((c) => {
    if (c.slots.some((slot) => diaDe(slot.window.start) === dia)) porTecnico.set(c.worker_id, []);
  });
  assignments
    .filter((a) => diaDe(a.window.start) === dia)
    .forEach((a) => a.worker_ids.forEach((w) => porTecnico.set(w, [...(porTecnico.get(w) ?? []), a])));

  return [...porTecnico.entries()]
    .map(([tecnico, ordens]): Coluna => {
      const emOrdem = [...ordens].sort((a, b) => a.window.start.localeCompare(b.window.start));
      const minutos = carga(emOrdem);
      const escala = escalaDoDia(capacidades, tecnico, dia);
      return {
        tecnico,
        ordens: emOrdem,
        minutos,
        escala,
        estourou: escala > 0 && minutos > escala,
        impossivel: escalaImpossivel(escala),
        trocadas: trocasNoConjunto(trocas, emOrdem),
        movidas: remanejosNoConjunto(remanejos, emOrdem),
      };
    })
    .sort((a, b) => b.ordens.length - a.ordens.length || a.tecnico.localeCompare(b.tecnico));
}

/**
 * Onde entra, numa sequência já remexida, a ordem que acabou de chegar por troca.
 *
 * Ela entra pelo relógio: a troca não mexe na janela, e `reempacotar` joga para o
 * fim da fila quem não está na sequência. Como a sequência pendente é justamente
 * uma lista fora da ordem do relógio, a posição é a primeira cujo horário de
 * origem é mais tarde que o dela — nunca uma contagem de quem vem antes, que
 * duplicaria vizinhas numa lista desordenada.
 */
export function inserirPeloRelogio(
  sequencia: string[],
  ordens: Assignment[],
  entrando: string,
): string[] {
  if (sequencia.includes(entrando)) return sequencia;
  const inicio = new Map(ordens.map((a) => [a.operation_id, a.window.start]));
  const dela = inicio.get(entrando);
  if (dela === undefined) return [...sequencia, entrando];
  const posicao = sequencia.findIndex((id) => (inicio.get(id) ?? '') > dela);
  if (posicao === -1) return [...sequencia, entrando];
  return [...sequencia.slice(0, posicao), entrando, ...sequencia.slice(posicao)];
}
