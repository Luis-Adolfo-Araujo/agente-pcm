import { describe, expect, it } from 'vitest';
import { colunasDoDia, inserirPeloRelogio } from '@/lib/quadro';
import type { Assignment, Capacity } from '@/lib/api';

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

const capacidade = (worker: string, inicio: string, fim: string): Capacity => ({
  worker_id: worker,
  gross_minutes: 0,
  committed_minutes: 0,
  net_minutes: 0,
  slots: [{ worker_id: worker, window: { start: inicio, end: fim } }],
});

const DIA = '2026-08-18';
const t = (hora: string) => `${DIA}T${hora}:00-03:00`;

describe('colunasDoDia', () => {
  it('dá coluna a quem tem escala no dia mesmo sem nenhuma ordem', () => {
    const colunas = colunasDoDia([], [capacidade('ana', t('07:00'), t('16:00'))], DIA, []);
    expect(colunas.map((c) => c.tecnico)).toEqual(['ana']);
    expect(colunas[0].ordens).toEqual([]);
    expect(colunas[0].escala).toBe(540);
  });

  it('dá coluna a quem tem ordem no dia sem escala declarada', () => {
    const colunas = colunasDoDia([alocacao('op-1', ['bruno'], t('08:00'), t('09:00'))], [], DIA, []);
    expect(colunas.map((c) => c.tecnico)).toEqual(['bruno']);
    expect(colunas[0].escala).toBe(0);
    expect(colunas[0].estourou).toBe(false);
  });

  it('ignora ordem de outro dia', () => {
    const colunas = colunasDoDia(
      [alocacao('op-1', ['ana'], '2026-08-19T08:00:00-03:00', '2026-08-19T09:00:00-03:00')],
      [capacidade('ana', t('07:00'), t('16:00'))],
      DIA,
      [],
    );
    expect(colunas[0].ordens).toEqual([]);
  });

  it('ordena as colunas por número de ordens e desempata por nome', () => {
    const colunas = colunasDoDia(
      [
        alocacao('op-1', ['bruno'], t('08:00'), t('09:00')),
        alocacao('op-2', ['bruno'], t('09:00'), t('10:00')),
        alocacao('op-3', ['ana'], t('08:00'), t('09:00')),
        alocacao('op-4', ['carla'], t('08:00'), t('09:00')),
      ],
      [],
      DIA,
      [],
    );
    expect(colunas.map((c) => c.tecnico)).toEqual(['bruno', 'ana', 'carla']);
  });

  it('põe as ordens da coluna em ordem de relógio e soma a carga', () => {
    const colunas = colunasDoDia(
      [
        alocacao('op-tarde', ['ana'], t('14:00'), t('15:30')),
        alocacao('op-manha', ['ana'], t('08:00'), t('09:00')),
      ],
      [capacidade('ana', t('07:00'), t('16:00'))],
      DIA,
      [],
    );
    expect(colunas[0].ordens.map((a) => a.operation_id)).toEqual(['op-manha', 'op-tarde']);
    expect(colunas[0].minutos).toBe(150);
  });

  it('marca estouro de escala e escala impossível', () => {
    const colunas = colunasDoDia(
      [alocacao('op-1', ['ana'], t('07:00'), t('20:00'))],
      [capacidade('ana', t('07:00'), t('19:30'))],
      DIA,
      [],
    );
    expect(colunas[0].estourou).toBe(true);
    expect(colunas[0].impossivel).toBe(true);
  });

  it('conta as ordens que vieram de troca da sessão', () => {
    const colunas = colunasDoDia(
      [alocacao('op-1', ['ana'], t('08:00'), t('09:00'))],
      [capacidade('ana', t('07:00'), t('16:00'))],
      DIA,
      [{ operation_id: 'op-1', de: 'bruno', para: 'ana', motivo: '', em: t('09:00') }],
    );
    expect(colunas[0].trocadas).toBe(1);
  });

  it('conta as ordens que vieram de outro dia', () => {
    const colunas = colunasDoDia(
      [alocacao('op-1', ['ana'], t('08:00'), t('09:00'))],
      [capacidade('ana', t('07:00'), t('16:00'))], DIA, [],
      [{
        operation_id: 'op-1',
        deDia: '2026-08-17', deInicio: '2026-08-17T08:00:00-03:00', deTecnico: 'bruno',
        paraDia: DIA, paraInicio: t('08:00'), paraTecnico: 'ana',
        motivo: '', em: t('09:00'),
      }],
    );
    expect(colunas[0].movidas).toBe(1);
  });

  it('mostra a ordem de dois executantes nas duas colunas', () => {
    const colunas = colunasDoDia([alocacao('op-1', ['ana', 'bruno'], t('08:00'), t('09:00'))], [], DIA, []);
    expect(colunas.map((c) => c.tecnico).sort()).toEqual(['ana', 'bruno']);
  });
});

describe('inserirPeloRelogio', () => {
  const ordens = [
    alocacao('op-manha', ['ana'], t('08:00'), t('09:00')),
    alocacao('op-tarde', ['ana'], t('14:00'), t('15:00')),
    alocacao('op-nova', ['ana'], t('10:00'), t('11:00')),
    alocacao('op-cedo', ['ana'], t('06:00'), t('07:00')),
  ];

  it('entra entre as duas quando o horário dela fica no meio', () => {
    expect(inserirPeloRelogio(['op-manha', 'op-tarde'], ordens, 'op-nova'))
      .toEqual(['op-manha', 'op-nova', 'op-tarde']);
  });

  it('entra na frente quando é a mais cedo', () => {
    expect(inserirPeloRelogio(['op-manha', 'op-tarde'], ordens, 'op-cedo'))
      .toEqual(['op-cedo', 'op-manha', 'op-tarde']);
  });

  it('vai para o fim quando é a mais tarde', () => {
    expect(inserirPeloRelogio(['op-cedo', 'op-manha'], ordens, 'op-tarde'))
      .toEqual(['op-cedo', 'op-manha', 'op-tarde']);
  });

  it('não duplica quem já está na sequência', () => {
    expect(inserirPeloRelogio(['op-manha', 'op-tarde'], ordens, 'op-manha'))
      .toEqual(['op-manha', 'op-tarde']);
  });

  // A sequência pendente é justamente uma lista fora da ordem do relógio: se a
  // inserção assumisse que ela está ordenada, a recém-chegada duplicaria uma
  // vizinha em vez de entrar entre elas.
  it('não duplica ninguém quando a sequência está fora da ordem do relógio', () => {
    const nova = inserirPeloRelogio(['op-tarde', 'op-manha'], ordens, 'op-nova');
    expect(new Set(nova).size).toBe(nova.length);
    expect(nova).toContain('op-nova');
    expect(nova.length).toBe(3);
  });

  it('põe no fim a ordem que não está na semana', () => {
    expect(inserirPeloRelogio(['op-manha'], ordens, 'op-fantasma'))
      .toEqual(['op-manha', 'op-fantasma']);
  });
});
