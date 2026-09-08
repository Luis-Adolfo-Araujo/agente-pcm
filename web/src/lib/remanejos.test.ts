import { describe, expect, it } from 'vitest';
import {
  aplicarRemanejos, inicioNoDia, motivoDoRemanejo, remanejoDaOrdem, remanejosNoConjunto,
  type Remanejo,
} from '@/lib/remanejos';
import { diaDe, minutosDe } from '@/lib/semana';
import type { Assignment, Schedule } from '@/lib/api';

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

const remanejo = (over: Partial<Remanejo> = {}): Remanejo => ({
  operation_id: 'op-1',
  deDia: '2026-08-18', deInicio: '2026-08-18T07:30:00-03:00', deTecnico: 'ana',
  paraDia: '2026-08-19', paraInicio: '2026-08-19T09:00:00-03:00', paraTecnico: 'bruno',
  motivo: 'parada da linha só na quarta', em: '2026-08-18T12:00:00-03:00',
  ...over,
});

describe('inicioNoDia', () => {
  it('monta o instante no dia pedido, mantendo o fuso da janela original', () => {
    expect(inicioNoDia('2026-08-18T07:30:00-03:00', '2026-08-19', '09:00'))
      .toBe('2026-08-19T09:00:00-03:00');
  });

  it('mantém o fuso mesmo quando a janela vem em UTC', () => {
    expect(inicioNoDia('2026-08-18T07:30:00Z', '2026-08-19', '09:00'))
      .toBe('2026-08-19T09:00:00Z');
  });
});

describe('aplicarRemanejos', () => {
  const base = semana([
    alocacao('op-1', ['ana'], '2026-08-18T07:30:00-03:00', '2026-08-18T09:00:00-03:00'),
    alocacao('op-2', ['ana'], '2026-08-18T09:00:00-03:00', '2026-08-18T10:00:00-03:00'),
  ]);

  it('devolve o mesmo objeto quando não há remanejo, para não invalidar memo à toa', () => {
    expect(aplicarRemanejos(base, [])).toBe(base);
  });

  it('leva a ordem para o dia novo, na hora escolhida', () => {
    const nova = aplicarRemanejos(base, [remanejo()]);
    const movida = nova.assignments.find((a) => a.operation_id === 'op-1')!;
    expect(diaDe(movida.window.start)).toBe('2026-08-19');
    expect(movida.window.start).toBe('2026-08-19T09:00:00-03:00');
  });

  it('preserva a duração: o fim é recalculado a partir do início novo', () => {
    const nova = aplicarRemanejos(base, [remanejo()]);
    const movida = nova.assignments.find((a) => a.operation_id === 'op-1')!;
    expect(minutosDe(movida)).toBe(90);
    expect(movida.window.end).toBe('2026-08-19T10:30:00-03:00');
  });

  it('põe a ordem com quem foi escolhido, mesmo que ela fosse dividida', () => {
    const dividida = semana([
      alocacao('op-1', ['ana', 'carla'], '2026-08-18T07:30:00-03:00', '2026-08-18T09:00:00-03:00'),
    ]);
    const nova = aplicarRemanejos(dividida, [remanejo()]);
    expect(nova.assignments[0].worker_ids).toEqual(['bruno']);
  });

  it('não mexe em quem não foi remanejado', () => {
    const nova = aplicarRemanejos(base, [remanejo()]);
    const parada = nova.assignments.find((a) => a.operation_id === 'op-2')!;
    expect(parada.window.start).toBe('2026-08-18T09:00:00-03:00');
    expect(parada.worker_ids).toEqual(['ana']);
  });

  it('ignora remanejo de ordem que não está na semana', () => {
    const nova = aplicarRemanejos(base, [remanejo({ operation_id: 'op-fantasma' })]);
    expect(nova.assignments).toEqual(base.assignments);
  });
});

describe('remanejoDaOrdem e remanejosNoConjunto', () => {
  it('acha o remanejo de uma ordem', () => {
    expect(remanejoDaOrdem([remanejo()], 'op-1')?.paraTecnico).toBe('bruno');
    expect(remanejoDaOrdem([remanejo()], 'op-2')).toBeUndefined();
  });

  it('conta quantas ordens de um conjunto foram movidas de dia', () => {
    const ordens = [
      alocacao('op-1', ['bruno'], '2026-08-19T09:00:00-03:00', '2026-08-19T10:30:00-03:00'),
      alocacao('op-3', ['bruno'], '2026-08-19T11:00:00-03:00', '2026-08-19T12:00:00-03:00'),
    ];
    expect(remanejosNoConjunto([remanejo()], ordens)).toBe(1);
    expect(remanejosNoConjunto([], ordens)).toBe(0);
  });
});

describe('motivoDoRemanejo', () => {
  const movimento = {
    deDia: '2026-08-18', deInicio: '2026-08-18T07:30:00-03:00', deTecnico: 'ana',
    paraDia: '2026-08-19', paraInicio: '2026-08-19T09:00:00-03:00', paraTecnico: 'bruno',
  };

  it('leva dia, hora e pessoa dos dois lados para o texto do feedback', () => {
    expect(motivoDoRemanejo({ ...movimento, motivo: 'parada da linha só na quarta' }))
      .toBe('passar de 18/08 07:30 com ana para 19/08 09:00 com bruno · parada da linha só na quarta');
  });

  it('sem justificativa, termina no movimento', () => {
    expect(motivoDoRemanejo({ ...movimento, motivo: '   ' }))
      .toBe('passar de 18/08 07:30 com ana para 19/08 09:00 com bruno');
  });
});
