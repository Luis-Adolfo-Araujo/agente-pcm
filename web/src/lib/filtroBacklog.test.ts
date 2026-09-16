import { describe, expect, it } from 'vitest';
import {
  SEM_FILTRO_BACKLOG, contagemPorMotivo, filtrando, filtrarBacklog, linhasDoBacklog, opcoesDoBacklog,
  type FiltroBacklog, type LinhaBacklog,
} from '@/lib/filtroBacklog';
import type { Backlog, Enriched, Schedule } from '@/lib/api';

type Detalhes = {
  titulo?: string; local?: string | null; faixa?: string; score?: number; material?: string;
  bloqueia?: boolean; vence?: string | null; candidatos?: [string, boolean][];
};

function item(op: string, d: Detalhes = {}): Enriched {
  return {
    operation: {
      work_order_id: `WO-${op}`, operation_id: op, title: d.titulo ?? `Ordem ${op}`, priority_level: 1,
      criticality: null, asset_id: null, location_id: d.local ?? null, planned_duration_minutes: null,
      due_at: d.vence ?? null,
    },
    priority: { score: d.score ?? 50, band: d.faixa ?? 'medium', model: 'x', reason_codes: [], missing_fields: [], components: [] },
    duration: { minutes: 60, p50_minutes: 60, p80_minutes: 60, source: 'planned', sample_size: 1, confidence: 1 },
    materials: { status: d.material ?? 'available', blocking: d.bloqueia ?? false, reason_codes: [] },
    executants: (d.candidatos ?? [['ana', true]]).map(([worker_id, eligible]) => ({
      worker_id, score: 70, eligible, available_minutes: 480, reason_codes: [],
    })),
    scheduled: false,
  };
}

const PERIODO = { start: '2026-08-18T00:00:00-03:00', end: '2026-08-25T00:00:00-03:00' };

function linhas(itens: Enriched[], motivos: Record<string, string> = {}): LinhaBacklog[] {
  const semana: Schedule = {
    status: 'partial',
    assignments: [],
    unscheduled: itens.map((i) => ({
      work_order_id: i.operation.work_order_id, operation_id: i.operation.operation_id,
      reason: motivos[i.operation.operation_id] ?? 'no_capacity', details: [],
    })),
    coverage: {
      total_operations: 0, scheduled_operations: 0, unscheduled_operations: 0,
      capacity_limited_operations: 0, demand_minutes: 0, available_minutes: 0, coverage_percent: 0, reasons: {},
    },
  };
  const backlog: Backlog = { backlog: itens, capacities: [] };
  return linhasDoBacklog(semana, backlog);
}

const com = (parcial: Partial<FiltroBacklog>): FiltroBacklog => ({ ...SEM_FILTRO_BACKLOG, ...parcial });
const ids = (lista: LinhaBacklog[]) => lista.map((l) => l.fora.operation_id);

describe('linhasDoBacklog', () => {
  it('lista quem ficou de fora, da maior prioridade para a menor', () => {
    const lista = linhas([item('a', { score: 30 }), item('b', { score: 90 }), item('c', { score: 60 })]);
    expect(ids(lista)).toEqual(['b', 'c', 'a']);
  });
});

describe('filtrarBacklog', () => {
  const todas = linhas(
    [
      item('op-1', { titulo: 'Troca de rolamento mecânico', local: 'L1', faixa: 'high', score: 80, material: 'available', vence: '2026-08-18T00:00:00-03:00', candidatos: [['ana', true]] }),
      item('op-2', { titulo: 'Inspeção elétrica', local: 'L2', faixa: 'low', score: 20, material: 'unavailable', bloqueia: true, vence: '2026-08-25T00:00:00-03:00', candidatos: [['bia', false]] }),
      item('op-3', { titulo: 'Lubrificação', local: 'L1', faixa: 'medium', score: 55, material: 'unknown', vence: null, candidatos: [['bia', true]] }),
    ],
    { 'op-2': 'material', 'op-3': 'manual' },
  );

  it('sem filtro, devolve tudo', () => {
    expect(ids(filtrarBacklog(todas, SEM_FILTRO_BACKLOG, PERIODO))).toEqual(['op-1', 'op-3', 'op-2']);
  });

  it('busca por título sem acento e por número da OS', () => {
    expect(ids(filtrarBacklog(todas, com({ busca: 'mecanico' }), PERIODO))).toEqual(['op-1']);
    expect(ids(filtrarBacklog(todas, com({ busca: 'wo-op-3' }), PERIODO))).toEqual(['op-3']);
  });

  it('filtra por motivo e por local', () => {
    expect(ids(filtrarBacklog(todas, com({ motivo: 'manual' }), PERIODO))).toEqual(['op-3']);
    expect(ids(filtrarBacklog(todas, com({ local: 'L1' }), PERIODO))).toEqual(['op-1', 'op-3']);
  });

  it('filtra por faixa e por score mínimo', () => {
    expect(ids(filtrarBacklog(todas, com({ faixa: 'low' }), PERIODO))).toEqual(['op-2']);
    expect(ids(filtrarBacklog(todas, com({ scoreMinimo: '55' }), PERIODO))).toEqual(['op-1', 'op-3']);
  });

  it('filtra por status de material e por bloqueador', () => {
    expect(ids(filtrarBacklog(todas, com({ material: 'unknown' }), PERIODO))).toEqual(['op-3']);
    expect(ids(filtrarBacklog(todas, com({ bloqueador: 'sim' }), PERIODO))).toEqual(['op-2']);
    expect(ids(filtrarBacklog(todas, com({ bloqueador: 'nao' }), PERIODO))).toEqual(['op-1', 'op-3']);
  });

  it('vence no período conta o início e deixa o fim de fora', () => {
    expect(ids(filtrarBacklog(todas, com({ venceNoPeriodo: true }), PERIODO))).toEqual(['op-1']);
  });

  it('técnico candidato só conta quem é elegível', () => {
    expect(ids(filtrarBacklog(todas, com({ tecnico: 'bia' }), PERIODO))).toEqual(['op-3']);
  });

  it('combina os filtros', () => {
    expect(ids(filtrarBacklog(todas, com({ local: 'L1', scoreMinimo: '60' }), PERIODO))).toEqual(['op-1']);
  });
});

describe('opcoesDoBacklog e contagemPorMotivo', () => {
  const todas = linhas(
    [item('a', { local: 'L2', faixa: 'high', candidatos: [['ana', true], ['caio', false]] }), item('b', { local: 'L1' })],
    { b: 'material' },
  );

  it('as opções saem só do que existe, e técnico só se for elegível', () => {
    expect(opcoesDoBacklog(todas)).toEqual({
      motivos: ['material', 'no_capacity'],
      locais: ['L1', 'L2'],
      faixas: ['high', 'medium'],
      materiais: ['available'],
      tecnicos: ['ana'],
    });
  });

  it('conta por motivo, do mais comum para o menos', () => {
    expect(contagemPorMotivo([...todas, ...linhas([item('c')])])).toEqual([['no_capacity', 2], ['material', 1]]);
  });

  it('diz se há algum filtro ligado', () => {
    expect(filtrando(SEM_FILTRO_BACKLOG)).toBe(false);
    expect(filtrando(com({ venceNoPeriodo: true }))).toBe(true);
  });
});
