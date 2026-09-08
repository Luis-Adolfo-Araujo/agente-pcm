'use client';
import { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, PageHead } from '@/components/ui';
import { Trace } from '@/components/stages/Trace';
import {
  ESTAGIOS_PRINCIPAIS,
  SKILLS_PARALELAS,
  STAGE_NAMES,
  resumoContagens,
  segundos,
  type Backlog,
  type Run,
  type Schedule,
  type Snapshot,
  type Verification,
} from '@/lib/api';

function proximaSemana(asOf: string): [string, string] {
  const inicio = new Date(asOf);
  inicio.setDate(inicio.getDate() + 1);
  const fim = new Date(inicio);
  fim.setDate(fim.getDate() + 6);
  return [inicio.toISOString().slice(0, 10), fim.toISOString().slice(0, 10)];
}

export function Montar({ snapshot, run, backlog, schedule, verification, onStart, abrirTrace, working, error }: {
  snapshot: Snapshot;
  run: Run | null;
  backlog: Backlog | null;
  schedule: Schedule | null;
  verification: Verification | null;
  onStart: (inicio: string, fim: string) => void;
  /** Sobe quando alguém pede o trace de outra tela; o pedido é consumido ao abrir. */
  abrirTrace: number;
  working: boolean;
  error: string | null;
}) {
  const [sugestaoInicio, sugestaoFim] = proximaSemana(snapshot.as_of);
  const [inicio, setInicio] = useState(sugestaoInicio);
  const [fim, setFim] = useState(sugestaoFim);
  const [traceAberto, setTraceAberto] = useState(false);
  const caixaTrace = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (abrirTrace === 0) return;
    setTraceAberto(true);
  }, [abrirTrace]);

  // Rolar só depois que o bloco existe na árvore, senão a âncora ainda é nada.
  useEffect(() => {
    if (traceAberto) caixaTrace.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [traceAberto]);

  const rodando = run && run.status !== 'completed' && run.status !== 'failed';
  const feitas = new Set((run?.trace_events ?? []).map((e) => e.stage));

  return (
    <>
      <PageHead
        title="Montar a semana"
        lead={`Escolha os dias. O agente vai olhar as ${snapshot.quality.operation_count.toLocaleString('pt-BR')} operações do backlog e propor quem faz o quê, em que dia.`}
      />

      <Card>
        <CardContent>
          <div className="row">
            <div className="field">
              <label htmlFor="inicio">Primeiro dia</label>
              <input id="inicio" type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="fim">Último dia</label>
              <input id="fim" type="date" value={fim} onChange={(e) => setFim(e.target.value)} />
            </div>
            <button className="btn btn-primary" disabled={working || !!rodando} onClick={() => onStart(inicio, fim)}>
              {working || rodando ? 'Montando…' : 'Montar a semana'}
            </button>
          </div>
          <p className="muted" style={{ marginTop: 14, marginBottom: 0, fontSize: '.86rem' }}>
            Sugestão: a primeira semana cheia depois do corte dos dados, em {new Date(snapshot.as_of).toLocaleDateString('pt-BR')}.
            Isso mantém a simulação perto do que estava valendo.
          </p>
          {error && <div className="note" data-tone="bad" style={{ marginTop: 16 }}>{error}</div>}
        </CardContent>
      </Card>

      {run && (
        <Card className="" >
          <CardHeader>Andamento</CardHeader>
          <CardContent>
            <ol className="trace" style={{ marginTop: 0 }}>
              {ESTAGIOS_PRINCIPAIS.map((etapa) => {
                const evento = run.trace_events.find((e) => e.stage === etapa);
                const pronta = feitas.has(etapa);
                return (
                  <li key={etapa} className="trace-stage" data-pendente={!pronta ? 'true' : undefined}>
                    <div className="trace-head">
                      <span className="trace-name" style={{ color: pronta ? undefined : 'var(--color-text-muted)' }}>
                        {STAGE_NAMES[etapa]}
                      </span>
                      {evento && <span className="trace-time">{segundos(evento.elapsed_ms)}</span>}
                      {evento && <span className="trace-counts">{resumoContagens(evento.counts)}</span>}
                    </div>

                    {/* As quatro skills rodam dentro desta janela: sem abrir aqui, o
                        estágio mais caro da execução fica sendo um número só. */}
                    {etapa === 'skills_parallel' && (
                      <ol className="trace-nested">
                        {SKILLS_PARALELAS.map((skill) => {
                          const passo = run.trace_events.find((e) => e.stage === skill);
                          return (
                            <li
                              key={skill}
                              className="trace-stage"
                              data-skill="true"
                              data-pendente={!passo ? 'true' : undefined}
                            >
                              <div className="trace-head">
                                <span className="trace-name" style={{ color: passo ? undefined : 'var(--color-text-muted)' }}>
                                  {STAGE_NAMES[skill]}
                                </span>
                                {passo && <span className="trace-time">{segundos(passo.elapsed_ms)}</span>}
                                {passo && <span className="trace-counts">{resumoContagens(passo.counts)}</span>}
                              </div>
                            </li>
                          );
                        })}
                      </ol>
                    )}
                  </li>
                );
              })}
            </ol>

            {run.status === 'completed' && !traceAberto && (
              <button
                type="button"
                className="btn"
                style={{ marginTop: 'var(--space-md)' }}
                onClick={() => setTraceAberto(true)}
              >
                Abrir o trace completo
              </button>
            )}
          </CardContent>
        </Card>
      )}

      {/* O trace é o relatório do que esta montagem fez: ele mora onde a montagem
          acontece, e não numa etapa própria que ninguém visita antes de precisar. */}
      {traceAberto && run?.status === 'completed' && backlog && schedule && verification && (
        <div ref={caixaTrace}>
          <Card>
            <CardHeader>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', width: '100%' }}>
                <span>Trace completo · o funil das skills sobre o backlog inteiro</span>
                <button type="button" className="btn btn-menor" onClick={() => setTraceAberto(false)}>
                  Fechar
                </button>
              </div>
            </CardHeader>
            <CardContent>
              <Trace
                run={run}
                snapshot={snapshot}
                backlog={backlog}
                schedule={schedule}
                verification={verification}
              />
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
