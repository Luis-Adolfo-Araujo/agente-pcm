import { describe, expect, it } from 'vitest';
import {
  inicioNoDia, motivoDoRemanejo, remanejoDaOrdem, remanejosNoConjunto,
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
