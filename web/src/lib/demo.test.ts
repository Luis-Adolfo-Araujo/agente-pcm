import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { demoApi } from '@/lib/demo';
import type { Backlog, Run, Schedule, Verification } from '@/lib/api';

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

const SCHEDULE: Schedule = {
  status: 'valid',
  assignments: [{
    work_order_id: 'wo-1', operation_id: 'op-1', worker_ids: ['tecnico-01'],
    window: { start: '2026-08-24T08:00:00-03:00', end: '2026-08-24T09:00:00-03:00' },
    priority_score: 80, reason_codes: [],
  }],
  unscheduled: [{ work_order_id: 'wo-2', operation_id: 'op-2', reason: 'no_capacity', details: [] }],
  coverage: {
    total_operations: 1, scheduled_operations: 1, unscheduled_operations: 0,
    capacity_limited_operations: 0, demand_minutes: 60, available_minutes: 480,
    coverage_percent: 100, reasons: {},
  },
};

const BACKLOG: Backlog = {
  backlog: [{
    operation: {
      work_order_id: 'wo-1', operation_id: 'op-1', title: 'Termografia', priority_level: 1,
      criticality: 1, asset_id: 'motor-1', location_id: 'linha-1',
      planned_duration_minutes: 60, due_at: null,
    },
    priority: { score: 80, band: 'high', model: 'demo', reason_codes: [], missing_fields: [], components: [] },
    duration: { minutes: 60, p50_minutes: 60, p80_minutes: 60, source: 'planned', sample_size: 1, confidence: 1 },
    materials: { status: 'available', blocking: false, reason_codes: [] },
    executants: [{ worker_id: 'tecnico-01', score: 90, eligible: true, available_minutes: 480, reason_codes: [] }],
    scheduled: true,
  }, {
    operation: {
      work_order_id: 'wo-2', operation_id: 'op-2', title: 'Lubrificação', priority_level: 2,
      criticality: 1, asset_id: 'motor-2', location_id: 'linha-1',
      planned_duration_minutes: 90, due_at: null,
    },
    priority: { score: 70, band: 'medium', model: 'demo', reason_codes: [], missing_fields: [], components: [] },
    duration: { minutes: 90, p50_minutes: 90, p80_minutes: 90, source: 'planned', sample_size: 1, confidence: 1 },
    materials: { status: 'available', blocking: false, reason_codes: [] },
    executants: [{ worker_id: 'tecnico-02', score: 85, eligible: true, available_minutes: 480, reason_codes: [] }],
    scheduled: false,
  }],
  capacities: [{
    worker_id: 'tecnico-01', gross_minutes: 480, committed_minutes: 0, net_minutes: 480,
    slots: [{
      worker_id: 'tecnico-01',
      window: { start: '2026-08-24T08:00:00-03:00', end: '2026-08-24T16:00:00-03:00' },
    }],
  }, {
    worker_id: 'tecnico-02', gross_minutes: 480, committed_minutes: 0, net_minutes: 480,
    slots: [
      { worker_id: 'tecnico-02', window: { start: '2026-08-24T08:00:00-03:00', end: '2026-08-24T16:00:00-03:00' } },
      { worker_id: 'tecnico-02', window: { start: '2026-08-25T08:00:00-03:00', end: '2026-08-25T16:00:00-03:00' } },
    ],
  }],
};

const VERIFICATION: Verification = { valid: true, input_hash: 'demo', violations: [] };

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('fetch', vi.fn(async (entrada: string | URL | Request) => {
    const url = String(entrada);
    const conteudo = url.includes('schedule.json') ? SCHEDULE
      : url.includes('backlog.json') ? BACKLOG
        : url.includes('verification.json') ? VERIFICATION
          : RUN;
    return { ok: true, json: async () => structuredClone(conteudo) };
  }));
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

describe('a revisão mockada', () => {
  it('começa na proposta publicada, sem ajustes', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });

    const revisao = await demoApi.revision('demo-1');

    expect(revisao.revision_sequence).toBe(0);
    expect(revisao.solution.assignments).toEqual(SCHEDULE.assignments);
    expect(revisao.adjustments).toEqual([]);
  });

  it('mostra a queda de carga antes de tirar uma ordem da semana', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });
    await demoApi.revision('demo-1');

    const previa = await demoApi.previewAdjustments('demo-1', {
      actions: [{ kind: 'remove', operation_id: 'op-1' }],
      rejected: [], accepted: [], expected_revision: 0,
    });

    expect(previa.base_revision).toBe(0);
    expect(previa.load).toEqual([{
      worker_id: 'tecnico-01', date: '2026-08-24',
      before_minutes: 60, after_minutes: 0, shift_minutes: 480,
    }]);
    expect(previa.violations.created).toEqual([]);
  });

  it('confirma a retirada e desfaz o último grupo na memória', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });
    await demoApi.revision('demo-1');

    const alterada = await demoApi.confirmAdjustments('demo-1', {
      actions: [{ kind: 'remove', operation_id: 'op-1' }],
      rejected: [], accepted: [], expected_revision: 0,
      recorded_by: 'visitante', reason: 'teste do front', feedback: [],
    });
    expect(alterada.solution.assignments).toEqual([]);
    expect(alterada.solution.unscheduled.find((item) => item.operation_id === 'op-1'))
      .toMatchObject({ operation_id: 'op-1', reason: 'manual' });
    expect(alterada.revision_sequence).toBe(1);

    const restaurada = await demoApi.undoAdjustments('demo-1');
    expect(restaurada.solution.assignments).toEqual(SCHEDULE.assignments);
    expect(restaurada.revision_sequence).toBe(0);
  });

  it('inclui uma ordem de fora com a pessoa e o dia escolhidos', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });
    await demoApi.revision('demo-1');

    const alterada = await demoApi.confirmAdjustments('demo-1', {
      actions: [{ kind: 'include', operation_id: 'op-2', target_worker_id: 'tecnico-02', target_date: '2026-08-25' }],
      rejected: [], accepted: [], expected_revision: 0,
      recorded_by: 'visitante', reason: null, feedback: [],
    });

    expect(alterada.solution.assignments.find((a) => a.operation_id === 'op-2')).toMatchObject({
      worker_ids: ['tecnico-02'],
      window: { start: '2026-08-25T08:00:00-03:00' },
    });
    expect(alterada.solution.unscheduled.some((item) => item.operation_id === 'op-2')).toBe(false);
  });

  it('move uma ordem para a pessoa, o dia e a hora escolhidos', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });
    await demoApi.revision('demo-1');

    const alterada = await demoApi.confirmAdjustments('demo-1', {
      actions: [{
        kind: 'move', operation_id: 'op-1', replace_worker_id: 'tecnico-01',
        target_worker_id: 'tecnico-02', target_date: '2026-08-25',
        target_start: '2026-08-25T10:30:00-03:00',
      }],
      rejected: [], accepted: [], expected_revision: 0,
      recorded_by: 'visitante', reason: null, feedback: [],
    });

    expect(alterada.solution.assignments[0]).toMatchObject({
      worker_ids: ['tecnico-02'],
      window: { start: '2026-08-25T10:30:00-03:00' },
    });
  });

  it('altera a duração e conserva o começo da ordem', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });
    await demoApi.revision('demo-1');

    const alterada = await demoApi.confirmAdjustments('demo-1', {
      actions: [{ kind: 'duration', operation_id: 'op-1', minutes: 120 }],
      rejected: [], accepted: [], expected_revision: 0,
      recorded_by: 'visitante', reason: null, feedback: [],
    });

    expect(alterada.duration_overrides).toEqual({ 'op-1': 120 });
    expect(alterada.solution.assignments[0].window).toEqual({
      start: '2026-08-24T08:00:00-03:00', end: '2026-08-24T10:00:00-03:00',
    });
  });

  it('mostra e aplica o afastamento das ordens de uma pessoa indisponível', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });
    await demoApi.revision('demo-1');
    const action = {
      kind: 'unavailable' as const, worker_id: 'tecnico-01',
      date_from: '2026-08-24', date_to: '2026-08-24', cause: 'vacation' as const,
    };

    const previa = await demoApi.previewAdjustments('demo-1', {
      actions: [action], rejected: [], accepted: [], expected_revision: 0,
    });
    expect(previa.consequences).toHaveLength(1);
    expect(previa.consequences[0]).toMatchObject({
      default_accepted: true, from: { worker_ids: ['tecnico-01'] }, to: null,
    });

    const alterada = await demoApi.confirmAdjustments('demo-1', {
      actions: [action], rejected: [], accepted: [], expected_revision: 0,
      recorded_by: 'visitante', reason: 'férias', feedback: [],
    });
    expect(alterada.solution.assignments).toEqual([]);
    expect(alterada.capacities[0].slots).toEqual([]);
  });
  it('encaixa a ordem incluída na folga do dia, não em cima de quem já está lá', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });
    await demoApi.revision('demo-1');

    const alterada = await demoApi.confirmAdjustments('demo-1', {
      actions: [{ kind: 'include', operation_id: 'op-2', target_worker_id: 'tecnico-01', target_date: '2026-08-24' }],
      rejected: [], accepted: [], expected_revision: 0,
      recorded_by: 'visitante', reason: null, feedback: [],
    });

    expect(alterada.solution.assignments.find((a) => a.operation_id === 'op-2')?.window).toEqual({
      start: '2026-08-24T09:00:00-03:00', end: '2026-08-24T10:30:00-03:00',
    });
  });

  it('grava a consequência aceita junto da ação que a causou', async () => {
    await demoApi.startRun({ snapshot_id: 's', period_start: 'a', period_end: 'b' });
    await demoApi.revision('demo-1');

    const alterada = await demoApi.confirmAdjustments('demo-1', {
      actions: [{
        kind: 'unavailable', worker_id: 'tecnico-01',
        date_from: '2026-08-24', date_to: '2026-08-24', cause: 'vacation',
      }],
      rejected: [], accepted: [], expected_revision: 0,
      recorded_by: 'visitante', reason: 'férias', feedback: [],
    });

    expect(alterada.adjustments.map((item) => item.kind)).toEqual(['unavailable', 'remove']);
    expect(alterada.adjustments.map((item) => item.sequence)).toEqual([1, 2]);
    expect(alterada.revision_sequence).toBe(2);
    expect(alterada.adjustments[1].applied_by).toBe('visitante');
  });
});
