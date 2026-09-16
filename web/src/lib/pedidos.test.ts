import { describe, expect, it } from 'vitest';
import { pedidoDeDuracao, pedidoDeInclusao, pedidoDeIndisponibilidade } from '@/lib/pedidos';

const DIAS = ['2026-08-18', '2026-08-19', '2026-08-20'];

describe('pedidoDeIndisponibilidade', () => {
  it('monta a ausência quando dias e causa estão completos', () => {
    expect(pedidoDeIndisponibilidade('ana', '2026-08-18', '2026-08-19', 'sick_leave', DIAS)).toEqual([{
      kind: 'unavailable', worker_id: 'ana', date_from: '2026-08-18', date_to: '2026-08-19', cause: 'sick_leave',
    }]);
  });

  it('sem causa, com intervalo invertido ou fora do período, ainda não há pedido', () => {
    expect(pedidoDeIndisponibilidade('ana', '2026-08-18', '2026-08-19', '', DIAS)).toBeNull();
    expect(pedidoDeIndisponibilidade('ana', '2026-08-20', '2026-08-19', 'other', DIAS)).toBeNull();
    expect(pedidoDeIndisponibilidade('ana', '2026-08-18', '2026-08-25', 'other', DIAS)).toBeNull();
  });
});

describe('pedidoDeDuracao', () => {
  it('pede a duração nova quando ela é válida e diferente da atual', () => {
    expect(pedidoDeDuracao('op-1', '1:30', 60)).toEqual([{ kind: 'duration', operation_id: 'op-1', minutes: 90 }]);
    expect(pedidoDeDuracao('op-1', '1:30', null)).toEqual([{ kind: 'duration', operation_id: 'op-1', minutes: 90 }]);
  });

  it('sem mudança, ou com texto inválido, ainda não há pedido', () => {
    expect(pedidoDeDuracao('op-1', '1:00', 60)).toBeNull();
    expect(pedidoDeDuracao('op-1', '1h', 60)).toBeNull();
  });
});

describe('pedidoDeInclusao', () => {
  const escolha = { tecnico: 'ana', dia: '2026-08-19' };
  const incluir = { kind: 'include', operation_id: 'op-1', target_date: '2026-08-19', target_worker_id: 'ana' };

  it('sem destino escolhido, ainda não há pedido', () => {
    expect(pedidoDeInclusao('op-1', null, null, false)).toBeNull();
  });

  it('com duração, é só a inclusão', () => {
    expect(pedidoDeInclusao('op-1', escolha, null, false)).toEqual([incluir]);
  });

  it('sem duração, pede o tempo junto e só depois de ele ser válido', () => {
    expect(pedidoDeInclusao('op-1', escolha, null, true)).toBeNull();
    expect(pedidoDeInclusao('op-1', escolha, 90, true)).toEqual([
      { kind: 'duration', operation_id: 'op-1', minutes: 90 },
      incluir,
    ]);
  });
});
