import { describe, expect, it } from 'vitest';
import { descreverLugar, destinoEfetivo, quantosAjustes, resumoDasConsequencias } from '@/lib/previa';
import type { Ajuste, Consequencia, Previa } from '@/lib/api';

function ajuste(over: Partial<Ajuste>): Ajuste {
  return {
    sequence: 1, group: 1, kind: 'move', operation_id: 'op-1', target_date: null,
    target_worker_id: null, target_start: null, replace_worker_id: null, minutes: null,
    worker_id: null, date_from: null, date_to: null, cause: null, reason: null,
    applied_by: 'ana', applied_at: '2026-08-19T12:00:00-03:00', ...over,
  };
}

function consequencia(over: Partial<Consequencia>): Consequencia {
  return {
    id: 'move:op-1', adjustment: ajuste({}), default_accepted: true, accepted: true, locked: false,
    reason_code: 'SAME_DAY_OTHER_CANDIDATE', if_rejected: 'remove', from: null, to: null, ...over,
  };
}

function previa(consequences: Consequencia[]): Previa {
  return {
    run_id: 'run-1', base_revision: 0, consequences, load: [],
    violations: { created: [], resolved: [] }, notes: [],
  };
}

describe('destinoEfetivo', () => {
  it('aceita, a consequência faz o que o ajuste diz', () => {
    expect(destinoEfetivo(consequencia({}))).toBe('move');
    expect(destinoEfetivo(consequencia({ adjustment: ajuste({ kind: 'remove' }) }))).toBe('fora');
    expect(destinoEfetivo(consequencia({ adjustment: ajuste({ kind: 'include' }) }))).toBe('inclui');
  });

  it('recusada, ou vai para fora da semana, ou fica onde estava', () => {
    expect(destinoEfetivo(consequencia({ accepted: false }))).toBe('fora');
    expect(destinoEfetivo(consequencia({ accepted: false, if_rejected: 'stay' }))).toBe('fica');
  });
});

describe('quantosAjustes', () => {
  it('soma as ações e toda consequência que muda alguma coisa', () => {
    const lista = previa([
      consequencia({}),
      consequencia({ id: 'move:op-2', accepted: false }),
      consequencia({ id: 'include:op-3', accepted: false, if_rejected: 'stay' }),
    ]);
    expect(quantosAjustes([{ kind: 'unavailable' }], lista)).toBe(3);
  });
});

describe('resumoDasConsequencias', () => {
  it('conta cada destino com singular e plural', () => {
    const lista = previa([
      consequencia({}),
      consequencia({ id: 'move:op-2' }),
      consequencia({ id: 'remove:op-3', adjustment: ajuste({ kind: 'remove' }) }),
      consequencia({ id: 'include:op-4', adjustment: ajuste({ kind: 'include' }) }),
    ]);
    expect(resumoDasConsequencias(lista))
      .toBe('2 mudam de lugar · 1 vai para fora da semana · 1 entra na semana.');
  });

  it('sem consequência, diz que nada mais muda', () => {
    expect(resumoDasConsequencias(previa([]))).toBe('Nenhuma outra ordem muda.');
  });
});

describe('descreverLugar', () => {
  it('diz dia, hora e quem, na hora do fuso da própria janela', () => {
    const texto = descreverLugar({
      date: '2026-08-19', start: '2026-08-19T07:30:00-03:00', worker_ids: ['ana', 'bruno'],
    });
    expect(texto).toContain('19/08 07:30 ana, bruno');
  });

  it('sem lugar, é fora da semana', () => {
    expect(descreverLugar(null)).toBe('fora da semana');
  });
});
