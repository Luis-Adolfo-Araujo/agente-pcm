import { describe, expect, it } from 'vitest';
import { destinosDaInclusao, maiorFolga } from '@/lib/destinos';
import type { Assignment, Capacity, Enriched } from '@/lib/api';

const SEG = '2026-08-17';
const TER = '2026-08-18';
const t = (dia: string, hora: string) => `${dia}T${hora}:00-03:00`;
const janela = (dia: string, de: string, ate: string) => ({ start: t(dia, de), end: t(dia, ate) });

function alocacao(op: string, worker: string, dia: string, de: string, ate: string): Assignment {
  return {
    work_order_id: `WO-${op}`, operation_id: op, worker_ids: [worker],
    window: janela(dia, de, ate), priority_score: 50, reason_codes: [],
  };
}

const capacidade = (worker: string, dias: string[]): Capacity => ({
  worker_id: worker, gross_minutes: 0, committed_minutes: 0, net_minutes: 0,
  slots: dias.map((dia) => ({ worker_id: worker, window: janela(dia, '08:00', '16:00') })),
});

function item(candidatos: [string, number, boolean][]): Enriched {
  return {
    operation: {
      work_order_id: 'WO-x', operation_id: 'x', title: 'Ordem x', priority_level: 1, criticality: null,
      asset_id: null, location_id: null, planned_duration_minutes: null, due_at: null,
    },
    priority: { score: 70, band: 'high', model: 'x', reason_codes: [], missing_fields: [], components: [] },
    duration: { minutes: 120, p50_minutes: 120, p80_minutes: 120, source: 'planned', sample_size: 1, confidence: 1 },
    materials: { status: 'available', blocking: false, reason_codes: [] },
    executants: candidatos.map(([worker_id, score, eligible]) => ({
      worker_id, score, eligible, available_minutes: 480, reason_codes: eligible ? [] : ['TEAM_MISMATCH'],
    })),
    scheduled: false,
  };
}

describe('maiorFolga', () => {
  it('sem nada ocupado, é a escala inteira', () => {
    expect(maiorFolga([janela(SEG, '08:00', '16:00')], [])).toBe(480);
  });

  it('acha o maior buraco entre os compromissos', () => {
    const ocupadas = [janela(SEG, '09:00', '10:00'), janela(SEG, '13:00', '14:00')];
    expect(maiorFolga([janela(SEG, '08:00', '16:00')], ocupadas)).toBe(180);
  });

  it('sem escala, não há folga', () => {
    expect(maiorFolga([], [])).toBe(0);
  });
});

describe('destinosDaInclusao', () => {
  const capacidades = [capacidade('ana', [SEG, TER]), capacidade('bia', [SEG, TER]), capacidade('caio', [SEG])];
  const cheioDaBiaNaSegunda = alocacao('b1', 'bia', SEG, '08:00', '15:00');
  const cheioDaBiaNaTerca = alocacao('b2', 'bia', TER, '08:00', '15:00');

  it('elegíveis primeiro, os que cabem na frente, e o score desempata', () => {
    const linhas = destinosDaInclusao(
      item([['bia', 95, true], ['ana', 60, true], ['caio', 99, false]]),
      [SEG, TER],
      [cheioDaBiaNaSegunda, cheioDaBiaNaTerca],
      capacidades,
      120,
    );
    expect(linhas.map((l) => [l.worker_id, l.cabeEmAlgum])).toEqual([['ana', true], ['bia', false], ['caio', true]]);
  });

  it('diz a folga de cada dia e marca o dia sem escala', () => {
    const [caio] = destinosDaInclusao(item([['caio', 50, true]]), [SEG, TER], [], capacidades, 120);
    expect(caio.celulas).toEqual([
      { dia: SEG, escala: 480, folga: 480, cabe: true },
      { dia: TER, escala: 0, folga: 0, cabe: false },
    ]);
  });
});
