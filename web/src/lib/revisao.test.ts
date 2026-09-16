import { describe, expect, it } from 'vitest';
import {
  backlogRevisado, duracoesAntes, gruposDaRevisao, incluidasDaRevisao, indisponiveisDaRevisao,
  motivoDeAjuste, remanejosDaRevisao, resumoDoGrupo, semanaRevisada, trocasDaRevisao,
} from '@/lib/revisao';
import type { Ajuste, Assignment, Backlog, Enriched, Revisao, Schedule, Unscheduled } from '@/lib/api';

const t = (dia: string, hora: string) => `${dia}T${hora}:00-03:00`;

function alocacao(op: string, workers: string[], inicio: string, fim: string): Assignment {
  return {
    work_order_id: `WO-${op}`, operation_id: op, worker_ids: workers,
    window: { start: inicio, end: fim }, priority_score: 70, reason_codes: [],
  };
}

function semana(assignments: Assignment[], unscheduled: Unscheduled[] = []): Schedule {
  return {
    status: 'partial', assignments, unscheduled,
    coverage: {
      total_operations: 9, scheduled_operations: 9, unscheduled_operations: 0,
      capacity_limited_operations: 0, demand_minutes: 0, available_minutes: 0,
      coverage_percent: 100, reasons: {},
    },
  };
}

function ajuste(over: Partial<Ajuste>): Ajuste {
  return {
    sequence: 1, group: 1, kind: 'move', operation_id: 'op-1', target_date: null,
    target_worker_id: null, target_start: null, replace_worker_id: null, minutes: null,
    worker_id: null, date_from: null, date_to: null, cause: null, reason: null,
    applied_by: 'ana', applied_at: '2026-08-19T12:00:00-03:00', ...over,
  };
}

function revisao(over: Partial<Revisao>): Revisao {
  return {
    run_id: 'run-1', revision_sequence: 1, groups: 1, adjustments: [],
    solution: { status: 'partial', assignments: [], unscheduled: [] },
    verification: { valid: true, input_hash: 'x', violations: [] },
    created_violations: [], inherited_violations: [], capacities: [], duration_overrides: {},
    ...over,
  };
}

function item(op: string, minutos: number | null): Enriched {
  return {
    operation: {
      work_order_id: `WO-${op}`, operation_id: op, title: `Ordem ${op}`, priority_level: 1,
      criticality: null, asset_id: null, location_id: null, planned_duration_minutes: null, due_at: null,
    },
    priority: { score: 70, band: 'high', model: 'x', reason_codes: [], missing_fields: [], components: [] },
    duration: {
      minutes: minutos, p50_minutes: minutos, p80_minutes: minutos, source: 'planned',
      sample_size: 1, confidence: 1,
    },
    materials: { status: 'available', blocking: false, reason_codes: [] },
    executants: [],
    scheduled: true,
  };
}

const PROPOSTA = semana([
  alocacao('op-1', ['ana'], t('2026-08-18', '07:00'), t('2026-08-18', '08:00')),
  alocacao('op-2', ['ana'], t('2026-08-18', '08:00'), t('2026-08-18', '09:00')),
]);

describe('semanaRevisada', () => {
  it('sem revisão, ou na revisão zero, devolve a proposta sem copiar', () => {
    expect(semanaRevisada(PROPOSTA, null)).toBe(PROPOSTA);
    expect(semanaRevisada(PROPOSTA, revisao({ revision_sequence: 0 }))).toBe(PROPOSTA);
  });

  it('com ajuste, troca alocações e fora da semana e mantém a cobertura do agente', () => {
    const fora: Unscheduled = { work_order_id: 'WO-op-2', operation_id: 'op-2', reason: 'manual', details: [] };
    const revisada = semanaRevisada(PROPOSTA, revisao({
      solution: { status: 'partial', assignments: [PROPOSTA.assignments[0]], unscheduled: [fora] },
    }));
    expect(revisada.assignments.map((a) => a.operation_id)).toEqual(['op-1']);
    expect(revisada.unscheduled).toEqual([fora]);
    expect(revisada.coverage).toBe(PROPOSTA.coverage);
  });
});

describe('backlogRevisado', () => {
  it('troca a capacidade e aplica a duração nova só onde ela mudou', () => {
    const backlog: Backlog = { backlog: [item('op-1', 60), item('op-2', 30)], capacities: [] };
    const capacidade = { worker_id: 'ana', gross_minutes: 0, committed_minutes: 0, net_minutes: 0, slots: [] };
    const revisado = backlogRevisado(backlog, revisao({
      capacities: [capacidade], duration_overrides: { 'op-2': 90 },
    }));
    expect(revisado.capacities).toEqual([capacidade]);
    expect(revisado.backlog[0]).toBe(backlog.backlog[0]);
    expect(revisado.backlog[1].duration.minutes).toBe(90);
  });
});

describe('trocasDaRevisao', () => {
  it('lê a última troca de cada ordem', () => {
    const trocas = trocasDaRevisao([
      ajuste({ sequence: 2, target_worker_id: 'dora', replace_worker_id: 'bruno', reason: 'de novo' }),
      ajuste({ sequence: 1, target_worker_id: 'bruno', replace_worker_id: 'ana' }),
    ]);
    expect(trocas).toEqual([{
      operation_id: 'op-1', de: 'bruno', para: 'dora', motivo: 'de novo', em: '2026-08-19T12:00:00-03:00',
    }]);
  });

  it('o empurrão da cascata, com a mesma pessoa dos dois lados, não é troca', () => {
    expect(trocasDaRevisao([ajuste({ target_worker_id: 'ana', replace_worker_id: 'ana' })])).toEqual([]);
  });

  it('mover sem substituir ninguém não é troca', () => {
    expect(trocasDaRevisao([ajuste({ target_worker_id: 'bruno' })])).toEqual([]);
  });
});

describe('remanejosDaRevisao', () => {
  const movida = semana([
    alocacao('op-1', ['bruno'], t('2026-08-19', '09:00'), t('2026-08-19', '10:00')),
    PROPOSTA.assignments[1],
  ]);

  it('ordem num dia diferente do proposto vira remanejo, com o lugar de antes e o de agora', () => {
    const [remanejo] = remanejosDaRevisao(
      [ajuste({ target_date: '2026-08-19', target_worker_id: 'bruno', reason: 'parada' })],
      PROPOSTA, movida,
    );
    expect(remanejo).toMatchObject({
      operation_id: 'op-1', deDia: '2026-08-18', deTecnico: 'ana',
      paraDia: '2026-08-19', paraInicio: t('2026-08-19', '09:00'), paraTecnico: 'bruno', motivo: 'parada',
    });
  });

  it('ordem que voltou ao dia proposto deixa de ser remanejo', () => {
    expect(remanejosDaRevisao([ajuste({ target_date: '2026-08-18' })], PROPOSTA, PROPOSTA)).toEqual([]);
  });

  it('ordem tirada da semana não é remanejo', () => {
    const semOp1 = semana([PROPOSTA.assignments[1]]);
    expect(remanejosDaRevisao([ajuste({ target_date: '2026-08-19' })], PROPOSTA, semOp1)).toEqual([]);
  });
});

describe('incluidasDaRevisao', () => {
  it('marca quem entrou por inclusão e continua na semana', () => {
    const comOp3 = semana([
      ...PROPOSTA.assignments,
      alocacao('op-3', ['ana'], t('2026-08-18', '10:00'), t('2026-08-18', '11:00')),
    ]);
    const ajustes = [
      ajuste({ kind: 'include', operation_id: 'op-3' }),
      ajuste({ kind: 'include', operation_id: 'op-4' }),
    ];
    expect([...incluidasDaRevisao(ajustes, PROPOSTA, comOp3)]).toEqual(['op-3']);
  });
});

describe('duracoesAntes', () => {
  it('guarda a duração que o agente tinha estimado para cada ordem alterada', () => {
    const doAgente: Backlog = { backlog: [item('op-1', 120), item('op-2', null)], capacities: [] };
    const antes = duracoesAntes(revisao({ duration_overrides: { 'op-1': 90, 'op-2': 45 } }), doAgente);
    expect([...antes.entries()]).toEqual([['op-1', 120], ['op-2', null]]);
  });
});

describe('indisponiveisDaRevisao', () => {
  it('espalha o intervalo pelos dias do período, com a causa', () => {
    const dias = ['2026-08-18', '2026-08-19', '2026-08-20', '2026-08-21'];
    const mapa = indisponiveisDaRevisao([ajuste({
      kind: 'unavailable', operation_id: null, worker_id: 'ana',
      date_from: '2026-08-19', date_to: '2026-08-20', cause: 'sick_leave',
    })], dias);
    expect([...(mapa.get('ana')?.entries() ?? [])]).toEqual([
      ['2026-08-19', 'sick_leave'], ['2026-08-20', 'sick_leave'],
    ]);
  });
});

describe('gruposDaRevisao', () => {
  it('agrupa, conta por tipo e põe o grupo mais novo primeiro', () => {
    const grupos = gruposDaRevisao([
      ajuste({ sequence: 1, group: 1, kind: 'remove' }),
      ajuste({ sequence: 2, group: 2, kind: 'unavailable', applied_by: 'bia' }),
      ajuste({ sequence: 3, group: 2, kind: 'move' }),
      ajuste({ sequence: 4, group: 2, kind: 'move' }),
    ]);
    expect(grupos.map((g) => [g.grupo, g.quem, g.total, g.porTipo])).toEqual([
      [2, 'bia', 3, { unavailable: 1, move: 2 }],
      [1, 'ana', 1, { remove: 1 }],
    ]);
  });
});

describe('motivoDeAjuste', () => {
  it('leva o movimento sempre, e a justificativa quando houver', () => {
    expect(motivoDeAjuste('tirar da semana', ' parada da linha ')).toBe('tirar da semana · parada da linha');
    expect(motivoDeAjuste('tirar da semana', '   ')).toBe('tirar da semana');
  });
});

describe('resumoDoGrupo', () => {
  it('nomeia cada tipo com singular e plural, na ordem em que a ação acontece', () => {
    expect(resumoDoGrupo({ move: 5, unavailable: 1, remove: 2 }))
      .toBe('1 indisponibilidade, 5 movimentos, 2 tiradas da semana');
    expect(resumoDoGrupo({ duration: 1 })).toBe('1 duração alterada');
  });
});
