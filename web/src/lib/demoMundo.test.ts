import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { confirmarAjustesDemo, criarRevisaoDemo, preverAjustesDemo } from '@/lib/demoRevisao';
import { diaDe, minutosDe } from '@/lib/semana';
import type { Backlog, Schedule, Verification } from '@/lib/api';

const ler = <T>(nome: string): T =>
  JSON.parse(readFileSync(`public/demo-api/${nome}.json`, 'utf8')) as T;

const schedule = ler<Schedule>('schedule');
const backlog = ler<Backlog>('backlog');
const verification = ler<Verification>('verification');

const revisao = () => criarRevisaoDemo('demo', schedule, backlog, verification);

describe('sobre o mundo congelado da demonstração', () => {
  it('parte das 469 alocadas e das 731 de fora', () => {
    const base = revisao();
    expect(base.solution.assignments).toHaveLength(469);
    expect(base.solution.unscheduled).toHaveLength(731);
    expect(base.capacities).toHaveLength(22);
  });

  it('a retirada devolve a carga do dia de quem a tinha', () => {
    const base = revisao();
    const alvo = base.solution.assignments[0];
    const previa = preverAjustesDemo(base, backlog, {
      actions: [{ kind: 'remove', operation_id: alvo.operation_id }],
      rejected: [], accepted: [], expected_revision: 0,
    });
    expect(previa.load).toHaveLength(alvo.worker_ids.length);
    expect(previa.load[0]).toMatchObject({ date: diaDe(alvo.window.start) });
    expect(previa.load[0].before_minutes - previa.load[0].after_minutes).toBe(minutosDe(alvo));
  });

  it('a inclusão não empilha a ordem nova em cima de quem já está no dia', () => {
    const base = revisao();
    const ocupada = base.solution.assignments[0];
    const dia = diaDe(ocupada.window.start);
    const tecnico = ocupada.worker_ids[0];
    const fora = backlog.backlog.find((item) => !item.scheduled)!;

    const depois = confirmarAjustesDemo(base, backlog, {
      actions: [{
        kind: 'include', operation_id: fora.operation.operation_id,
        target_worker_id: tecnico, target_date: dia,
      }],
      rejected: [], accepted: [], expected_revision: 0,
      recorded_by: 'fumaça', reason: null, feedback: [],
    });

    const janelas = depois.solution.assignments
      .filter((item) => item.worker_ids.includes(tecnico) && diaDe(item.window.start) === dia)
      .map((item) => [new Date(item.window.start).getTime(), new Date(item.window.end).getTime()])
      .sort((a, b) => a[0] - b[0]);
    janelas.slice(1).forEach(([inicio], indice) => {
      expect(inicio).toBeGreaterThanOrEqual(janelas[indice][1]);
    });
    expect(depois.solution.assignments).toHaveLength(470);
  });
});
