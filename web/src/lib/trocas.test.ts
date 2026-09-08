import { describe, expect, it } from 'vitest';
import { aplicarTrocas, motivoDoFeedback, trocaDaOrdem, trocasNoConjunto, type Troca } from '@/lib/trocas';
import { carga, escalaDoDia, escalaImpossivel, indexar } from '@/lib/semana';
import type { Assignment, Backlog, Capacity, Schedule } from '@/lib/api';

function alocacao(op: string, workers: string[], inicio: string, fim: string): Assignment {
  return {
    work_order_id: `WO-${op}`,
    operation_id: op,
    worker_ids: workers,
    window: { start: inicio, end: fim },
    priority_score: 70,
    reason_codes: [],
  };
}

function semana(assignments: Assignment[]): Schedule {
  return {
    status: 'ready',
    assignments,
    unscheduled: [],
    coverage: {
      total_operations: assignments.length, scheduled_operations: assignments.length,
      unscheduled_operations: 0, capacity_limited_operations: 0,
      demand_minutes: 0, available_minutes: 0, coverage_percent: 100, reasons: {},
    },
  };
}

const troca = (over: Partial<Troca> = {}): Troca => ({
  operation_id: 'op-1', de: 'ana', para: 'bruno', motivo: 'conhece o ativo',
  em: '2026-08-19T10:00:00-03:00', ...over,
});

describe('aplicarTrocas', () => {
  it('devolve o mesmo objeto quando não há troca, para não invalidar memo à toa', () => {
    const base = semana([alocacao('op-1', ['ana'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00')]);
    expect(aplicarTrocas(base, [])).toBe(base);
  });

  it('troca só o executante indicado e preserva o resto da alocação', () => {
    const base = semana([alocacao('op-1', ['ana'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00')]);
    const [depois] = aplicarTrocas(base, [troca()]).assignments;
    expect(depois.worker_ids).toEqual(['bruno']);
    expect(depois.window).toEqual(base.assignments[0].window);
    expect(depois.priority_score).toBe(70);
  });

  it('não mexe nas ordens que não foram trocadas', () => {
    const base = semana([
      alocacao('op-1', ['ana'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00'),
      alocacao('op-2', ['ana'], '2026-08-19T09:00:00-03:00', '2026-08-19T10:00:00-03:00'),
    ]);
    const depois = aplicarTrocas(base, [troca()]).assignments;
    expect(depois[0].worker_ids).toEqual(['bruno']);
    expect(depois[1]).toBe(base.assignments[1]);
  });

  it('preserva os outros executantes de uma ordem feita a quatro mãos', () => {
    const base = semana([alocacao('op-1', ['ana', 'carla'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00')]);
    expect(aplicarTrocas(base, [troca()]).assignments[0].worker_ids).toEqual(['bruno', 'carla']);
  });

  it('ignora uma troca cuja origem não está mais na ordem', () => {
    const base = semana([alocacao('op-1', ['carla'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00')]);
    expect(aplicarTrocas(base, [troca()]).assignments[0]).toBe(base.assignments[0]);
  });

  it('não altera o schedule original', () => {
    const base = semana([alocacao('op-1', ['ana'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00')]);
    aplicarTrocas(base, [troca()]);
    expect(base.assignments[0].worker_ids).toEqual(['ana']);
  });
});

describe('leitura das trocas', () => {
  it('acha a troca de uma ordem e devolve undefined para as outras', () => {
    const lista = [troca(), troca({ operation_id: 'op-9', para: 'dora' })];
    expect(trocaDaOrdem(lista, 'op-9')?.para).toBe('dora');
    expect(trocaDaOrdem(lista, 'op-5')).toBeUndefined();
  });

  it('conta quantas ordens de um conjunto vieram de troca manual', () => {
    const ordens = [
      alocacao('op-1', ['bruno'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00'),
      alocacao('op-2', ['bruno'], '2026-08-19T09:00:00-03:00', '2026-08-19T10:00:00-03:00'),
    ];
    expect(trocasNoConjunto([troca()], ordens)).toBe(1);
    expect(trocasNoConjunto([], ordens)).toBe(0);
  });

  it('leva o destino para dentro do texto do feedback, que é tudo o que a API guarda', () => {
    expect(motivoDoFeedback({ de: 'ana', para: 'bruno', motivo: 'certificação NR-10' }))
      .toBe('passar de ana para bruno · certificação NR-10');
  });

  // A justificativa é opcional, mas a API recusa `reason` vazio: é o movimento
  // que garante o mínimo, e ele sozinho não pode sair com separador pendurado.
  it('sem justificativa, grava só o movimento', () => {
    expect(motivoDoFeedback({ de: 'ana', para: 'bruno', motivo: '' }))
      .toBe('passar de ana para bruno');
  });

  it('trata justificativa em branco como ausente', () => {
    expect(motivoDoFeedback({ de: 'ana', para: 'bruno', motivo: '   ' }))
      .toBe('passar de ana para bruno');
  });
});

describe('carga e escala', () => {
  const slots = (worker: string, janelas: [string, string][]): Capacity => ({
    worker_id: worker, gross_minutes: 0, committed_minutes: 0, net_minutes: 0,
    slots: janelas.map(([start, end]) => ({ worker_id: worker, window: { start, end } })),
  });

  it('soma os minutos das ordens', () => {
    expect(carga([
      alocacao('op-1', ['ana'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:30:00-03:00'),
      alocacao('op-2', ['ana'], '2026-08-19T10:00:00-03:00', '2026-08-19T10:30:00-03:00'),
    ])).toBe(120);
  });

  it('conta só os slots do dia pedido', () => {
    const capacidades = [slots('ana', [
      ['2026-08-19T06:00:00-03:00', '2026-08-19T14:00:00-03:00'],
      ['2026-08-20T06:00:00-03:00', '2026-08-20T12:00:00-03:00'],
    ])];
    expect(escalaDoDia(capacidades, 'ana', '2026-08-19')).toBe(480);
    expect(escalaDoDia(capacidades, 'ana', '2026-08-20')).toBe(360);
    expect(escalaDoDia(capacidades, 'ana', '2026-08-21')).toBe(0);
  });

  it('a madrugada pertence ao dia da string ISO, não ao dia em UTC', () => {
    // 04:00 em -03:00 é 07:00Z; por `new Date` o slot cairia no mesmo dia, mas a
    // ordem das 23h cairia no dia seguinte. O corte é feito na string.
    const capacidades = [slots('ana', [['2026-08-19T23:00:00-03:00', '2026-08-20T03:00:00-03:00']])];
    expect(escalaDoDia(capacidades, 'ana', '2026-08-19')).toBe(240);
    expect(escalaDoDia(capacidades, 'ana', '2026-08-20')).toBe(0);
  });

  it('devolve zero para quem não tem capacidade declarada', () => {
    expect(escalaDoDia([], 'ana', '2026-08-19')).toBe(0);
  });

  it('marca como impossível a escala acima de 12h, que nenhuma jornada fecha', () => {
    expect(escalaImpossivel(12 * 60)).toBe(false);
    expect(escalaImpossivel(12 * 60 + 1)).toBe(true);
  });
});

describe('indexar', () => {
  it('deixa alocadas e fora da semana alcançáveis pela mesma chave de operação', () => {
    const backlog = {
      backlog: [
        { operation: { operation_id: 'op-1', title: 'Trocar rolamento' } },
        { operation: { operation_id: 'op-2', title: 'Lubrificar torre' } },
      ],
      capacities: [],
    } as unknown as Backlog;
    const base: Schedule = {
      ...semana([alocacao('op-1', ['ana'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00')]),
      unscheduled: [{ work_order_id: 'WO-op-2', operation_id: 'op-2', reason: 'no_capacity', details: [] }],
    };
    const indice = indexar(backlog, base);
    expect(indice.titulos.get('op-1')).toBe('Trocar rolamento');
    expect(indice.alocada.get('op-1')?.worker_ids).toEqual(['ana']);
    expect(indice.fora.get('op-2')?.reason).toBe('no_capacity');
    expect(indice.alocada.has('op-2')).toBe(false);
  });
});
