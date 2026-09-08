/**
 * A mesma interface, sem API atrás.
 *
 * A demonstração pública existe para olhar e ajustar a tela, não para provar o
 * servidor. Então a rodada já aconteceu: os artefatos foram gerados uma vez
 * pelo agente de verdade, sobre a planta fictícia, e ficam como arquivo
 * estático ao lado da página.
 *
 * O que este módulo não faz é entregar tudo pronto de imediato. A montagem
 * revela as etapas na ordem e no ritmo em que elas realmente levaram, porque a
 * espera é parte do que se está avaliando: o chevron precisa acender estágio a
 * estágio para alguém julgar se ele comunica progresso.
 */

import { asset } from '@/lib/caminhos';
import type {
  Backlog,
  FeedbackItem,
  FeedbackRecord,
  Run,
  Schedule,
  Snapshot,
  Verification,
} from '@/lib/api';

/** O trace real dura cerca de um segundo; a tela pesquisa a cada 1,2 s.
 *  Sem esticar, a semana ficaria pronta antes do primeiro pedido e nenhum
 *  estágio apareceria aceso. */
const DURACAO_SIMULADA_MS = 7000;

async function carregar<T>(nome: string): Promise<T> {
  const resposta = await fetch(asset(`/demo-api/${nome}.json`), { cache: 'force-cache' });
  if (!resposta.ok) throw new Error(`demo: faltou ${nome}.json`);
  return resposta.json() as Promise<T>;
}

let pronta: Run | null = null;
let inicio = 0;

async function base(): Promise<Run> {
  if (!pronta) pronta = await carregar<Run>('run');
  return pronta;
}

/** O quanto do trace já teria acontecido, do começo até agora. */
function decorrido(): number {
  return Date.now() - inicio;
}

function emAndamento(completa: Run, passado: number): Run {
  const total = completa.trace_events.reduce((soma, evento) => soma + evento.elapsed_ms, 0) || 1;
  const escala = DURACAO_SIMULADA_MS / total;

  const revelados: Run['trace_events'] = [];
  let acumulado = 0;
  for (const evento of completa.trace_events) {
    acumulado += evento.elapsed_ms * escala;
    if (acumulado > passado) break;
    revelados.push(evento);
  }

  if (revelados.length === completa.trace_events.length) return completa;

  return {
    ...completa,
    status: 'running',
    current_stage: revelados.at(-1)?.stage ?? null,
    trace_events: revelados,
    summary: null,
    decision: null,
  };
}

export const demoApi = {
  snapshots: () => carregar<Snapshot[]>('snapshots'),
  runs: async () => (inicio === 0 ? [] : [await demoApi.run('')]),
  run: async (_id: string) => emAndamento(await base(), decorrido()),
  backlog: (_id: string) => carregar<Backlog>('backlog'),
  schedule: (_id: string) => carregar<Schedule>('schedule'),
  verification: (_id: string) => carregar<Verification>('verification'),

  startRun: async (_body: { snapshot_id: string; period_start: string; period_end: string }) => {
    const completa = await base();
    inicio = Date.now();
    return emAndamento(completa, 0);
  },

  /** A decisão é de quem está olhando, e some quando a aba fecha. */
  decide: async (_id: string, body: { decision: string; decided_by: string; reason: string }) => {
    const completa = await base();
    pronta = {
      ...completa,
      decision: {
        decision: body.decision,
        decided_by: body.decided_by,
        reason: body.reason,
        decided_at: new Date().toISOString(),
      },
    };
    return pronta;
  },

  feedback: async (id: string, body: { recorded_by: string; items: FeedbackItem[] }) => {
    const completa = await base();
    return body.items.map<FeedbackRecord>((item, indice) => ({
      ...item,
      feedback_id: `demo-${Date.now()}-${indice}`,
      run_id: id || completa.run_id,
      snapshot_id: completa.snapshot_id,
      recorded_by: body.recorded_by,
      recorded_at: new Date().toISOString(),
    }));
  },
};
