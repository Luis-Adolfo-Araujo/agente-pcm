import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { demoApi } from '@/lib/demo';
import type { Run } from '@/lib/api';

const RUN: Run = {
  run_id: 'demo-1',
  snapshot_id: 'snap-1',
  status: 'completed',
  created_at: '2026-08-24T09:00:00Z',
  current_stage: null,
  trace_events: [
    { sequence: 1, stage: 'snapshot_validated', elapsed_ms: 100, counts: {} },
    { sequence: 2, stage: 'skills_parallel', elapsed_ms: 300, counts: {} },
    { sequence: 3, stage: 'optimization', elapsed_ms: 400, counts: {} },
    { sequence: 4, stage: 'proposal_ready', elapsed_ms: 200, counts: {} },
  ],
  request: { period: { start: '2026-08-24', end: '2026-08-30' } },
  summary: {
    assignments: 469, unscheduled: 731, violations: 0,
    verification_valid: true, proposal_status: 'draft',
  },
  decision: null,
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => RUN })));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('a montagem simulada', () => {
  it('começa em andamento, sem etapa nenhuma acesa', async () => {
    const run = await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });

    expect(run.status).toBe('running');
    expect(run.trace_events).toHaveLength(0);
    expect(run.summary).toBeNull();
  });

  it('acende as etapas na ordem conforme o tempo passa', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });

    vi.advanceTimersByTime(1500);
    const meio = await demoApi.run('demo-1');

    expect(meio.status).toBe('running');
    expect(meio.trace_events.map((e) => e.stage)).toEqual(['snapshot_validated']);
    expect(meio.current_stage).toBe('snapshot_validated');
  });

  it('termina com a semana pronta e o resumo do agente', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });

    vi.advanceTimersByTime(30000);
    const fim = await demoApi.run('demo-1');

    expect(fim.status).toBe('completed');
    expect(fim.trace_events).toHaveLength(4);
    expect(fim.summary?.assignments).toBe(469);
  });

  it('não revela uma etapa antes da anterior', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });

    vi.advanceTimersByTime(5000);
    const quase = await demoApi.run('demo-1');

    const sequencias = quase.trace_events.map((e) => e.sequence);
    expect(sequencias).toEqual([...sequencias].sort((a, b) => a - b));
  });
});

describe('a decisão de quem está olhando', () => {
  it('fica gravada na execução devolvida', async () => {
    const run = await demoApi.decide('demo-1', {
      decision: 'approve', decided_by: 'visitante', reason: 'parece boa',
    });

    expect(run.decision?.decision).toBe('approve');
    expect(run.decision?.decided_by).toBe('visitante');
  });
});

describe('o feedback', () => {
  it('devolve um registro por item, amarrado à execução', async () => {
    const registros = await demoApi.feedback('demo-1', {
      recorded_by: 'visitante',
      items: [{ operation_id: 'op-1', skill: 'ranking', verdict: 'correct', reason: 'ok' }],
    });

    expect(registros).toHaveLength(1);
    expect(registros[0].run_id).toBe('demo-1');
    expect(registros[0].snapshot_id).toBe('snap-1');
  });
});
