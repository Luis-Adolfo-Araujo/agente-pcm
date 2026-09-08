import { describe, expect, it } from 'vitest';
import {
  aplicarReordens, instanteEm, motivoDaReordenacao, mover, mudancas, ordensDoDia, reempacotar,
  trocasDePosicao,
  type Reordenacao,
} from '@/lib/reordenar';
import { diaDe } from '@/lib/semana';
import type { Assignment, Schedule } from '@/lib/api';

function alocacao(op: string, inicio: string, fim: string, workers = ['ana']): Assignment {
  return {
    work_order_id: `WO-${op}`,
    operation_id: op,
    worker_ids: workers,
    window: { start: inicio, end: fim },
    priority_score: 70,
    reason_codes: [],
  };
}

/** Um dia com intervalo entre a segunda e a terceira, como o otimizador produz. */
const dia = [
  alocacao('a', '2026-08-18T04:00:00-03:00', '2026-08-18T04:30:00-03:00'),
  alocacao('b', '2026-08-18T04:30:00-03:00', '2026-08-18T07:30:00-03:00'),
  alocacao('c', '2026-08-18T08:00:00-03:00', '2026-08-18T09:00:00-03:00'),
];

const hhmm = (iso: string) => iso.slice(11, 16);

function semana(assignments: Assignment[]): Schedule {
  return {
    status: 'ready', assignments, unscheduled: [],
    coverage: {
      total_operations: assignments.length, scheduled_operations: assignments.length,
      unscheduled_operations: 0, capacity_limited_operations: 0,
      demand_minutes: 0, available_minutes: 0, coverage_percent: 100, reasons: {},
    },
  };
}

describe('instanteEm', () => {
  it('formata no fuso da janela de origem, não em UTC', () => {
    const ms = Date.parse('2026-08-18T04:00:00-03:00');
    expect(instanteEm(ms, '-03:00')).toBe('2026-08-18T04:00:00-03:00');
    expect(instanteEm(ms, 'Z')).toBe('2026-08-18T07:00:00Z');
  });

  it('mantém a madrugada no dia certo, que é o defeito que motiva a função', () => {
    // Em UTC isto seria 2026-08-18T07:00, mas o dia do recorte é o local.
    const ms = Date.parse('2026-08-18T04:00:00-03:00');
    expect(diaDe(instanteEm(ms, '-03:00'))).toBe('2026-08-18');
  });

  it('vira o dia quando o horário passa da meia-noite local', () => {
    const ms = Date.parse('2026-08-18T23:30:00-03:00') + 60 * 60000;
    expect(instanteEm(ms, '-03:00')).toBe('2026-08-19T00:30:00-03:00');
  });
});

describe('reempacotar', () => {
  it('cola as ordens a partir do primeiro início e come os intervalos', () => {
    const novo = reempacotar(dia, ['a', 'b', 'c']);
    expect(novo.map((a) => hhmm(a.window.start))).toEqual(['04:00', '04:30', '07:30']);
    expect(novo.map((a) => hhmm(a.window.end))).toEqual(['04:30', '07:30', '08:30']);
  });

  it('preserva a duração de cada ordem ao mudar a sequência', () => {
    const novo = reempacotar(dia, ['c', 'a', 'b']);
    expect(novo.map((a) => a.operation_id)).toEqual(['c', 'a', 'b']);
    expect(novo.map((a) => hhmm(a.window.start))).toEqual(['04:00', '05:00', '05:30']);
    expect(novo.map((a) => hhmm(a.window.end))).toEqual(['05:00', '05:30', '08:30']);
  });

  it('nunca produz sobreposição: cada início é o fim do anterior', () => {
    const novo = reempacotar(dia, ['b', 'c', 'a']);
    novo.slice(1).forEach((a, i) => expect(a.window.start).toBe(novo[i].window.end));
  });

  it('põe no fim quem não estava na sequência, sem perder ninguém', () => {
    const novo = reempacotar(dia, ['c']);
    expect(novo.map((a) => a.operation_id)).toEqual(['c', 'a', 'b']);
  });

  it('ignora id que não existe mais no dia', () => {
    const novo = reempacotar(dia, ['sumiu', 'b', 'a', 'c']);
    expect(novo.map((a) => a.operation_id)).toEqual(['b', 'a', 'c']);
  });

  it('não altera as alocações originais', () => {
    reempacotar(dia, ['c', 'b', 'a']);
    expect(hhmm(dia[2].window.start)).toBe('08:00');
  });

  it('devolve a lista vazia intacta', () => {
    expect(reempacotar([], ['a'])).toEqual([]);
  });
});

describe('mudancas', () => {
  it('lista só quem saiu do lugar ou mudou de horário', () => {
    const novo = reempacotar(dia, ['c', 'a', 'b']);
    const lista = mudancas(dia, novo);
    expect(lista.map((m) => m.operation_id).sort()).toEqual(['a', 'b', 'c']);
    const c = lista.find((m) => m.operation_id === 'c')!;
    expect([c.dePosicao, c.paraPosicao]).toEqual([3, 1]);
    expect(hhmm(c.deInicio)).toBe('08:00');
    expect(hhmm(c.paraInicio)).toBe('04:00');
  });

  it('a primeira ordem não conta como mudança quando fica onde estava', () => {
    // 'a' segue em 1ª e às 04:00; 'b' também não se move; só 'c' antecipa.
    const novo = reempacotar(dia, ['a', 'b', 'c']);
    expect(mudancas(dia, novo).map((m) => m.operation_id)).toEqual(['c']);
  });

  it('não acusa mudança nenhuma quando nada muda', () => {
    expect(mudancas(dia.slice(0, 2), reempacotar(dia.slice(0, 2), ['a', 'b']))).toEqual([]);
  });
});

describe('aplicarReordens', () => {
  const base = semana([
    ...dia,
    alocacao('z', '2026-08-19T06:00:00-03:00', '2026-08-19T07:00:00-03:00'),
    alocacao('outro', '2026-08-18T05:00:00-03:00', '2026-08-18T06:00:00-03:00', ['bruno']),
  ]);

  it('devolve o mesmo objeto quando não há reordenação', () => {
    expect(aplicarReordens(base, [])).toBe(base);
  });

  it('mexe só no dia e na pessoa reordenados', () => {
    const r: Reordenacao[] = [{ tecnico: 'ana', dia: '2026-08-18', sequencia: ['c', 'a', 'b'], registrada: false }];
    const novo = aplicarReordens(base, r);
    const porId = new Map(novo.assignments.map((a) => [a.operation_id, a]));
    expect(hhmm(porId.get('c')!.window.start)).toBe('04:00');
    // Outro dia e outra pessoa ficam intactos.
    expect(porId.get('z')!.window.start).toBe('2026-08-19T06:00:00-03:00');
    expect(porId.get('outro')!.window.start).toBe('2026-08-18T05:00:00-03:00');
  });

  it('preserva a posição de cada alocação no array da semana', () => {
    const r: Reordenacao[] = [{ tecnico: 'ana', dia: '2026-08-18', sequencia: ['c', 'b', 'a'], registrada: false }];
    const novo = aplicarReordens(base, r);
    expect(novo.assignments.map((a) => a.operation_id))
      .toEqual(base.assignments.map((a) => a.operation_id));
  });

  it('não altera a semana original', () => {
    aplicarReordens(base, [{ tecnico: 'ana', dia: '2026-08-18', sequencia: ['c', 'b', 'a'], registrada: false }]);
    expect(hhmm(base.assignments[2].window.start)).toBe('08:00');
  });
});

describe('ordensDoDia', () => {
  it('filtra por pessoa e por dia, em ordem de relógio', () => {
    const base = semana([
      alocacao('tarde', '2026-08-18T09:00:00-03:00', '2026-08-18T10:00:00-03:00'),
      alocacao('cedo', '2026-08-18T04:00:00-03:00', '2026-08-18T05:00:00-03:00'),
      alocacao('outro-dia', '2026-08-19T04:00:00-03:00', '2026-08-19T05:00:00-03:00'),
      alocacao('outra-pessoa', '2026-08-18T06:00:00-03:00', '2026-08-18T07:00:00-03:00', ['bruno']),
    ]);
    expect(ordensDoDia(base, 'ana', '2026-08-18').map((a) => a.operation_id)).toEqual(['cedo', 'tarde']);
  });
});

describe('mover', () => {
  it('sobe, desce e ignora o que sai do intervalo', () => {
    expect(mover([1, 2, 3], 2, 0)).toEqual([3, 1, 2]);
    expect(mover([1, 2, 3], 0, 2)).toEqual([2, 3, 1]);
    expect(mover([1, 2, 3], 0, -1)).toEqual([1, 2, 3]);
    expect(mover([1, 2, 3], 2, 9)).toEqual([1, 2, 3]);
    expect(mover([1, 2, 3], 1, 1)).toEqual([1, 2, 3]);
  });

  it('não altera a lista de entrada', () => {
    const lista = [1, 2, 3];
    mover(lista, 0, 2);
    expect(lista).toEqual([1, 2, 3]);
  });
});

describe('trocasDePosicao', () => {
  it('separa quem saiu do lugar de quem só foi empurrado pelo reempacotamento', () => {
    // Subir 'c' para o topo muda a posição das três; a quarta, que não existe
    // aqui, seria o caso de horário deslocado sem mudança de posição.
    const comQuarta = [
      ...dia,
      alocacao('d', '2026-08-18T09:00:00-03:00', '2026-08-18T09:30:00-03:00'),
    ];
    const novo = reempacotar(comQuarta, ['c', 'a', 'b', 'd']);
    const todas = mudancas(comQuarta, novo);
    const decididas = trocasDePosicao(todas);

    expect(todas.map((m) => m.operation_id).sort()).toEqual(['a', 'b', 'c', 'd']);
    // 'd' segue em 4ª: o horário andou, a decisão não foi dela.
    expect(decididas.map((m) => m.operation_id).sort()).toEqual(['a', 'b', 'c']);
    const d = todas.find((m) => m.operation_id === 'd')!;
    expect(d.mudouPosicao).toBe(false);
    expect(d.dePosicao).toBe(d.paraPosicao);
    expect(d.deInicio).not.toBe(d.paraInicio);
  });

  it('devolve lista vazia quando ninguém trocou de posição', () => {
    const novo = reempacotar(dia, ['a', 'b', 'c']);
    expect(trocasDePosicao(mudancas(dia, novo))).toEqual([]);
  });
});

describe('motivoDaReordenacao', () => {
  const mudanca = {
    operation_id: 'op-1',
    dePosicao: 1,
    paraPosicao: 3,
    deInicio: '2026-08-18T08:00:00-03:00',
    paraInicio: '2026-08-18T10:00:00-03:00',
    mudouPosicao: true,
  };
  const hora = (iso: string) => iso.slice(11, 16);

  it('leva o movimento e a justificativa para o texto do feedback', () => {
    expect(motivoDaReordenacao(mudanca, hora, 'material só chega à tarde'))
      .toBe('reordenada: 1ª → 3ª posição do dia (08:00 → 10:00) · material só chega à tarde');
  });

  // Sem justificativa o texto termina no movimento: um separador sozinho no fim
  // entraria no golden set como se houvesse uma razão ilegível.
  it('sem justificativa, grava só o movimento', () => {
    expect(motivoDaReordenacao(mudanca, hora, ''))
      .toBe('reordenada: 1ª → 3ª posição do dia (08:00 → 10:00)');
  });

  it('trata justificativa em branco como ausente', () => {
    expect(motivoDaReordenacao(mudanca, hora, '   '))
      .toBe('reordenada: 1ª → 3ª posição do dia (08:00 → 10:00)');
  });
});
