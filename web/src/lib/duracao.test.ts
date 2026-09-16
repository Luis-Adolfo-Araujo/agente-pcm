import { describe, expect, it } from 'vitest';
import { escreverHhmm, lerHhmm } from '@/lib/duracao';

describe('lerHhmm', () => {
  it('lê horas e minutos', () => {
    expect(lerHhmm('1:30')).toBe(90);
    expect(lerHhmm(' 02:05 ')).toBe(125);
    expect(lerHhmm('24:00')).toBe(1440);
  });

  it('recusa o que não é h:mm, zero e mais de um dia', () => {
    ['90', '1:5', '1:60', '0:00', '24:01', 'uma hora', ''].forEach((texto) => {
      expect(lerHhmm(texto)).toBeNull();
    });
  });
});

describe('escreverHhmm', () => {
  it('escreve com dois dígitos nos minutos', () => {
    expect(escreverHhmm(90)).toBe('1:30');
    expect(escreverHhmm(5)).toBe('0:05');
  });
});
