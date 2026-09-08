'use client';
import { useCallback, useMemo, useState } from 'react';
import { Badge, Card, CardContent, CardHeader, EmptyState, PageHead, Stat, Table, TabPanel, Tabs } from '@/components/ui';
import { PorDia } from '@/components/stages/PorDia';
import { Matriz } from '@/components/semana/Matriz';
import { FiltrosSemana } from '@/components/semana/FiltrosSemana';
import { DetalheModal, type Alvo } from '@/components/detalhe/DetalheModal';
import { useArraste } from '@/components/quadro/useArraste';
import { useReordens } from '@/components/sessao/useReordens';
import { useRemanejos } from '@/components/sessao/useRemanejos';
import { useTrocas } from '@/components/sessao/useTrocas';
import { diasDoPeriodo, indexar, rotuloDia } from '@/lib/semana';
import { filtrarLinhas, linhasDaSemana, locaisDoBacklog, type FiltroSemana } from '@/lib/matriz';
import { REASON_NAMES, dia, hhmm, hora, type Backlog, type Run, type Schedule, type Verification } from '@/lib/api';

const SEM_FILTRO: FiltroSemana = { busca: '', soEstouro: false, local: '' };

export function Semana({ run, schedule, backlog, verification, onVerViolacoes }: {
  run: Run;
  schedule: Schedule;
  backlog: Backlog;
  verification: Verification;
  onVerViolacoes: () => void;
}) {
  const [aba, setAba] = useState('semana');
  const [alvo, setAlvo] = useState<Alvo | null>(null);
  const [filtro, setFiltro] = useState<FiltroSemana>(SEM_FILTRO);
  const c = schedule.coverage;
  const violacoes = verification.violations.length;

  // As trocas da sessão moram aqui, acima das abas: se cada aba tivesse a sua,
  // elas discordariam entre si sobre quem está com qual ordem.
  const { trocas, efetivo, trocar, gravando, erro, limparErro } = useTrocas(run.run_id, schedule);
  const comTrocas = efetivo ?? schedule;
  // O movimento de dia grava a pessoa final, então ele lê a semana já com as
  // trocas aplicadas.
  const remanejo = useRemanejos(run.run_id, comTrocas);
  const comRemanejos = remanejo.efetivo ?? comTrocas;
  // A sequência do dia vem por último: quem foi passado para outra pessoa ou
  // para outro dia já precisa estar lá antes de ser reordenado.
  const reordenacao = useReordens(run.run_id, comRemanejos);
  const semana = useMemo(() => reordenacao.aplicar(comRemanejos), [reordenacao, comRemanejos]);

  const indice = useMemo(() => indexar(backlog, semana), [backlog, semana]);
  const abrirOrdem = useCallback((operationId: string) => setAlvo({ tipo: 'ordem', operationId }), []);

  const dias = useMemo(
    () => diasDoPeriodo(run.request.period.start, run.request.period.end),
    [run],
  );

  // O dia aberto e o arraste moram acima das duas telas: a matriz manda para o
  // quadro do dia, e o cartão no ar precisa ser o mesmo dos dois lados.
  const [diaAberto, setDiaAberto] = useState('');
  const arraste = useArraste();

  const linhas = useMemo(
    () => linhasDaSemana(semana.assignments, backlog.capacities, dias),
    [semana, backlog, dias],
  );

  const locais = useMemo(() => locaisDoBacklog(backlog), [backlog]);
  const indicesDoFiltro = useMemo(() => ({
    titulos: indice.titulos,
    ids: new Map(backlog.backlog.map((item) => [
      item.operation.operation_id, item.operation.work_order_id,
    ])),
    locais: locais.porOrdem,
  }), [indice, backlog, locais]);

  const linhasFiltradas = useMemo(
    () => filtrarLinhas(linhas, filtro, indicesDoFiltro),
    [linhas, filtro, indicesDoFiltro],
  );

  const irParaDia = useCallback((d: string) => { setDiaAberto(d); setAba('dia'); }, []);

  const porPessoa = useMemo(() => {
    const mapa = new Map<string, typeof semana.assignments>();
    semana.assignments.forEach((a) => {
      a.worker_ids.forEach((w) => {
        if (!mapa.has(w)) mapa.set(w, []);
        mapa.get(w)!.push(a);
      });
    });
    return [...mapa.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [semana]);

  const foraOrdenada = useMemo(
    () => [...semana.unscheduled].sort((a, b) => a.reason.localeCompare(b.reason)),
    [semana],
  );

  const periodo = dias.length > 0
    ? `${rotuloDia(dias[0]).numero} a ${rotuloDia(dias[dias.length - 1]).numero}`
    : '—';

  return (
    <>
      <PageHead
        title="Ver a semana"
        lead="O que o agente conseguiu encaixar, e o que ficou de fora — com o motivo de cada exclusão. Qualquer linha abre a conta por trás dela."
      />

      <div className="ui-grid ui-grid-4" style={{ marginBottom: 20 }}>
        <Stat label="Alocadas" value={c.scheduled_operations.toLocaleString('pt-BR')} note={`de ${c.total_operations.toLocaleString('pt-BR')} no backlog`} tone="good" />
        <Stat label="Fora da semana" value={c.unscheduled_operations.toLocaleString('pt-BR')} note={`${c.capacity_limited_operations.toLocaleString('pt-BR')} por falta de HH`} tone="warn" />
        <Stat label="Cobertura de capacidade" value={`${c.coverage_percent.toFixed(1)}%`} note={`${hhmm(c.available_minutes)} para ${hhmm(c.demand_minutes)}`} tone="warn" />
        <Stat
          label="Violações duras"
          value={violacoes.toLocaleString('pt-BR')}
          note={violacoes === 0 ? 'conferência não achou violação' : 'aprovação bloqueada até resolver'}
          tone={violacoes === 0 ? 'good' : 'bad'}
        />
      </div>

      {violacoes > 0 && (
        <div className="note" data-tone="bad" style={{ marginBottom: 20 }}>
          A conferência independente encontrou <strong>{violacoes}</strong> violações duras nesta proposta.
          Enquanto elas existirem, só é possível rejeitar.{' '}
          <button type="button" className="btn" style={{ marginTop: 8 }} onClick={onVerViolacoes}>
            Ver a lista de violações
          </button>
        </div>
      )}

      <div className="note" style={{ marginBottom: 24 }}>
        A capacidade disponível cobre <strong>{c.coverage_percent.toFixed(1)}%</strong> da demanda do backlog.{' '}
        <strong>{c.capacity_limited_operations.toLocaleString('pt-BR')}</strong> das{' '}
        {c.unscheduled_operations.toLocaleString('pt-BR')} que ficaram de fora são limite de
        capacidade da equipe, não falha de recomendação.
      </div>

      {trocas.length > 0 && (
        <div className="note" data-tone="bad" style={{ marginBottom: 24 }}>
          Você passou <strong>{trocas.length}</strong>{' '}
          {trocas.length === 1 ? 'ordem' : 'ordens'} para outra pessoa. A tela abaixo já mostra a
          semana com essas trocas; a <strong>proposta gravada continua a do agente</strong>, e o que
          ficou registrado foi a sua discordância, com o motivo.
        </div>
      )}

      {remanejo.remanejos.length > 0 && (
        <div className="note" data-tone="bad" style={{ marginBottom: 24 }}>
          Você moveu <strong>{remanejo.remanejos.length}</strong>{' '}
          {remanejo.remanejos.length === 1 ? 'ordem' : 'ordens'} de dia. A tela mostra a semana
          com esses movimentos; a <strong>proposta gravada continua a do agente</strong>.
        </div>
      )}

      <Tabs
        label="Ordens da semana"
        ativa={aba}
        onChange={setAba}
        abas={[
          { id: 'semana', rotulo: 'Semana' },
          { id: 'dia', rotulo: 'Por dia' },
          { id: 'dentro', rotulo: 'Por pessoa', contagem: semana.assignments.length },
          { id: 'fora', rotulo: 'Fora da semana', contagem: semana.unscheduled.length },
        ]}
      />

      <TabPanel id="semana" ativa={aba}>
        {dias.length === 0 || linhas.length === 0 ? (
          <EmptyState
            title="Nenhuma escala neste recorte"
            description="Sem escala declarada e sem ordem alocada não há semana para mostrar. Confira o período da execução."
          />
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              Ocupação de cada pessoa, dia a dia, no período de <strong>{periodo}</strong>. Quem
              estourou a escala vem no topo. Arraste um cartão até outra célula para passar a ordem
              para outra pessoa ou outro dia; clique numa barra para abrir o quadro daquele dia.
            </p>

            <FiltrosSemana
              filtro={filtro}
              locais={locais.distintos}
              onMudar={setFiltro}
              resultado={{ linhas: linhasFiltradas.length, total: linhas.length }}
            />

            {linhasFiltradas.length === 0 ? (
              <EmptyState
                title="Nada casa com esse recorte"
                description="Nenhuma pessoa tem ordem que atenda ao filtro. Limpe a busca ou troque o local."
              />
            ) : (
              <Matriz
                dias={dias}
                linhas={linhasFiltradas}
                todas={linhas}
                schedule={semana}
                base={comRemanejos}
                titulos={indice.titulos}
                trocas={trocas}
                remanejos={remanejo.remanejos}
                ativa={alvo?.tipo === 'ordem' ? alvo.operationId : null}
                total={semana.assignments.length}
                onAbrirOrdem={abrirOrdem}
                onAbrirDia={irParaDia}
                arraste={arraste}
                remanejo={remanejo}
                trocar={trocar}
                gravando={gravando}
                erro={erro}
                limparErro={limparErro}
              />
            )}
          </>
        )}
      </TabPanel>

      <TabPanel id="dia" ativa={aba}>
        <PorDia
          run={run}
          schedule={semana}
          base={comRemanejos}
          backlog={backlog}
          trocas={trocas}
          titulos={indice.titulos}
          ativa={alvo?.tipo === 'ordem' ? alvo.operationId : null}
          onAbrirOrdem={abrirOrdem}
          dia={diaAberto}
          onMudarDia={setDiaAberto}
          arraste={arraste}
          reordenacao={reordenacao}
          remanejo={remanejo}
          trocar={trocar}
          gravando={gravando}
          erro={erro}
          limparErro={limparErro}
        />
      </TabPanel>

      <TabPanel id="dentro" ativa={aba}>
        <Card>
          <CardHeader>Alocações por pessoa</CardHeader>
          <CardContent>
            <Table head={<><th scope="col">Executante</th><th scope="col" className="num">Ordens</th><th scope="col">Quando</th></>}>
              {porPessoa.map(([pessoa, ordens]) => (
                <tr key={pessoa}>
                  <td className="mono" style={{ color: 'var(--color-text)' }}>{pessoa}</td>
                  <td className="num">{ordens.length}</td>
                  <td className="muted" style={{ fontSize: '.82rem' }}>
                    {[...new Set(ordens.map((o) => dia(o.window.start)))].sort().join(' · ')}
                  </td>
                </tr>
              ))}
            </Table>

            <h2 style={{ margin: '28px 0 12px', fontSize: '1rem' }}>Ordens alocadas</h2>
            <Table className="tabela-clicavel" head={<><th scope="col">OS</th><th scope="col">Serviço</th><th scope="col">Executante</th><th scope="col">Dia</th><th scope="col">Horário</th><th scope="col" className="num">Score</th></>}>
              {semana.assignments.slice(0, 120).map((a) => (
                <tr
                  key={a.operation_id}
                  tabIndex={0}
                  role="button"
                  style={{ cursor: 'pointer' }}
                  aria-label={`Abrir ${indice.titulos.get(a.operation_id) || a.work_order_id}`}
                  onClick={() => abrirOrdem(a.operation_id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      abrirOrdem(a.operation_id);
                    }
                  }}
                >
                  <td className="mono" title={a.work_order_id}>{a.work_order_id.slice(-6)}</td>
                  <td>{indice.titulos.get(a.operation_id) ?? '—'}</td>
                  <td className="mono">{a.worker_ids.join(', ')}</td>
                  <td>{dia(a.window.start)}</td>
                  <td className="mono">{hora(a.window.start)}–{hora(a.window.end)}</td>
                  <td className="num">{a.priority_score.toFixed(0)}</td>
                </tr>
              ))}
            </Table>
            {semana.assignments.length > 120 && (
              <p className="muted" style={{ fontSize: '.84rem' }}>
                Mostrando as 120 primeiras de {semana.assignments.length}.
              </p>
            )}
          </CardContent>
        </Card>
      </TabPanel>

      <TabPanel id="fora" ativa={aba}>
        <Card>
          <CardHeader>Por que cada ordem ficou de fora</CardHeader>
          <CardContent>
            <div className="ui-grid ui-grid-4" style={{ marginBottom: 20 }}>
              {Object.entries(c.reasons).sort((a, b) => b[1] - a[1]).map(([motivo, quantas]) => (
                <Stat
                  key={motivo}
                  label={REASON_NAMES[motivo] ?? motivo}
                  value={quantas.toLocaleString('pt-BR')}
                  tone={motivo === 'no_capacity' ? 'warn' : 'bad'}
                />
              ))}
            </div>
            <Table className="tabela-clicavel" head={<><th scope="col">OS</th><th scope="col">Serviço</th><th scope="col">Motivo</th><th scope="col">O que travou</th></>}>
              {foraOrdenada.slice(0, 120).map((u) => (
                <tr
                  key={u.operation_id}
                  tabIndex={0}
                  role="button"
                  style={{ cursor: 'pointer' }}
                  aria-label={`Abrir ${indice.titulos.get(u.operation_id) || u.work_order_id}`}
                  onClick={() => abrirOrdem(u.operation_id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      abrirOrdem(u.operation_id);
                    }
                  }}
                >
                  <td className="mono" title={u.work_order_id}>{u.work_order_id.slice(-6)}</td>
                  <td>{indice.titulos.get(u.operation_id) ?? '—'}</td>
                  <td>
                    <Badge tone={u.reason === 'no_capacity' ? 'warn' : 'bad'}>
                      {REASON_NAMES[u.reason] ?? u.reason}
                    </Badge>
                  </td>
                  <td className="muted" style={{ fontSize: '.84rem' }}>{(u.details ?? []).join(' · ') || '—'}</td>
                </tr>
              ))}
            </Table>
            {foraOrdenada.length > 120 && (
              <p className="muted" style={{ fontSize: '.84rem' }}>
                Mostrando as 120 primeiras de {foraOrdenada.length}.
              </p>
            )}
          </CardContent>
        </Card>
      </TabPanel>

      <DetalheModal
        alvo={alvo}
        onFechar={() => setAlvo(null)}
        indice={indice}
        backlog={backlog}
        schedule={semana}
        trocas={trocas}
        trocar={trocar}
        gravando={gravando}
        erro={erro}
        limparErro={limparErro}
      />
    </>
  );
}
