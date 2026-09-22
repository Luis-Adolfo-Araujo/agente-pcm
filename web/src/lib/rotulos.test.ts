import { describe, expect, it } from 'vitest';
import {
  identidadeDoTecnico, jsonComNomesDosTecnicos, nomeDoTecnico, nomesDosTecnicos,
} from '@/lib/rotulos';

describe('nomeDoTecnico', () => {
  it('troca o código do técnico pelo nome próprio definido para a demonstração', () => {
    expect(nomeDoTecnico('tecnico-01')).toBe('Carlos Medeiros');
    expect(nomeDoTecnico('tecnico-09')).toBe('Carlos Barbosa');
    expect(nomeDoTecnico('tecnico-22')).toBe('Patrícia Nogueira');
  });

  it('preserva nomes e identificadores que não pertencem à demonstração', () => {
    expect(nomeDoTecnico('Ana Souza')).toBe('Ana Souza');
    expect(nomeDoTecnico('worker-42')).toBe('worker-42');
  });
});

describe('nomesDosTecnicos', () => {
  it('formata uma equipe sem expor os códigos', () => {
    expect(nomesDosTecnicos(['tecnico-01', 'tecnico-10'])).toBe('Carlos Medeiros, Adriana Barbosa');
  });
});

describe('identidadeDoTecnico', () => {
  it('mantém o id para registros e oferece o nome próprio para a tela', () => {
    expect(identidadeDoTecnico('tecnico-01')).toEqual({
      id: 'tecnico-01',
      nome: 'Carlos Medeiros',
    });
  });
});

describe('jsonComNomesDosTecnicos', () => {
  it('troca ids de pessoa também em estruturas aninhadas sem alterar outros códigos', () => {
    const json = jsonComNomesDosTecnicos({
      worker_id: 'tecnico-01',
      reason_code: 'EXECUTANT_SCORE',
      slots: [{ worker_id: 'tecnico-09' }],
      worker_ids: ['tecnico-22'],
    });

    expect(json).toContain('Carlos Medeiros');
    expect(json).toContain('Carlos Barbosa');
    expect(json).toContain('Patrícia Nogueira');
    expect(json).toContain('EXECUTANT_SCORE');
    expect(json).not.toContain('tecnico-');
  });
});
