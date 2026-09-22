'use client';
import { useCallback, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, EmptyState, PageHead, Stat, Table, TabPanel, Tabs } from '@/components/ui';
import { PorDia } from '@/components/stages/PorDia';
import { Matriz } from '@/components/semana/Matriz';
import { FiltrosSemana } from '@/components/semana/FiltrosSemana';
import { DetalheModal, type Alvo } from '@/components/detalhe/DetalheModal';
import { AcaoDeAjuste, type AcaoAberta } from '@/components/ajuste/AcaoDeAjuste';
import { ForaDaSemana } from '@/components/backlog/ForaDaSemana';
import { RodapeAjustes } from '@/components/ajuste/RodapeAjustes';
import { useArraste } from '@/components/quadro/useArraste';
import { useReordens } from '@/components/sessao/useReordens';
import type { Pedido, PedidoDeRemanejo, Remanejador, Revisor } from '@/components/sessao/useRevisao';
import { diaDe, diasDoPeriodo, indexar, rotuloDia } from '@/lib/semana';
import { filtrarLinhas, linhasDaSemana, locaisDoBacklog, type FiltroSemana } from '@/lib/matriz';
import { motivoDoRemanejo } from '@/lib/remanejos';
import {
  backlogRevisado, duracoesAntes, incluidasDaRevisao, indisponiveisDaRevisao, remanejosDaRevisao,
  semanaRevisada, trocasDaRevisao, type MarcasDaRevisao,
} from '@/lib/revisao';
import { motivoDoFeedback } from '@/lib/trocas';
import { nomesDosTecnicos } from '@/lib/rotulos';
import { dia, hhmm, hora, type Backlog, type Run, type Schedule, type Verification } from '@/lib/api';

const SEM_FILTRO: FiltroSemana = { busca: '', soEstouro: false, local: '' };

export function Semana({ run, schedule, backlog, verification, revisor, onVerViolacoes }: {
  run: Run;
  /** A proposta do agente, como a montagem devolveu. */
  schedule: Schedule;
  backlog: Backlog;
  verification: Verification;
  /** A revisão da run: a proposta mais os ajustes gravados. */
  revisor: Revisor;
  onVerViolacoes: () => void;
}) {
  const [aba, setAba] = useState('semana');
  const [alvo, setAlvo] = useState<Alvo | null>(null);
  const [filtro, setFiltro] = useState<FiltroSemana>(SEM_FILTRO);
  const c = schedule.coverage;

  // A tela mostra a revisão. Ela mora acima das abas: se cada aba lesse a sua,
  // elas discordariam entre si sobre quem está com qual ordem.
  const rev = revisor.revisao;
  const revisada = useMemo(() => semanaRevisada(schedule, rev), [schedule, rev]);
  const backlogVisto = useMemo(() => backlogRevisado(backlog, rev), [backlog, rev]);
  const ajustes = rev?.adjustments;
  const trocas = useMemo(() => trocasDaRevisao(ajustes ?? []), [ajustes]);
  const remanejos = useMemo(
    () => remanejosDaRevisao(ajustes ?? [], schedule, revisada),
    [ajustes, schedule, revisada],
  );
  const marcas = useMemo((): MarcasDaRevisao => ({
    incluidas: incluidasDaRevisao(ajustes ?? [], schedule, revisada),
    duracaoAntes: duracoesAntes(rev, backlog),
  }), [ajustes, schedule, revisada, rev, backlog]);
  const violacoes = (rev?.verification ?? verification).violations.length;
  const { confirmar, gravando, erro, limparErro } = revisor;

  /** Passar para outra pessoa mantém a hora: só troca quem faz. */
  const trocar = useCallback(async (pedido: Pedido): Promise<boolean> => {
    const ordem = revisada.assignments.find((a) => a.operation_id === pedido.operation_id);
    if (!ordem) return false;
    return confirmar({
      acoes: [{
        kind: 'move', operation_id: pedido.operation_id, target_date: diaDe(ordem.window.start),
        target_worker_id: pedido.para, replace_worker_id: pedido.de, target_start: ordem.window.start,
      }],
      quem: pedido.quem,
      motivo: pedido.motivo,
      feedback: [{ operation_id: pedido.operation_id, skill: 'executants', reason: motivoDoFeedback(pedido) }],
    });
  }, [revisada, confirmar]);

  /**
   * Mover de dia continua sendo uma discordância só — a do encaixe —, mesmo
   * quando a pessoa muda junto. Sem `replace_worker_id`, a ordem fica com quem
   * recebe e só com ela, como o popover avisa.
   */
  const remanejo = useMemo((): Remanejador => ({
    remanejos,
    remanejar: (pedido: PedidoDeRemanejo) => confirmar({
      acoes: [{
        kind: 'move', operation_id: pedido.operation_id, target_date: pedido.paraDia,
        target_worker_id: pedido.paraTecnico, target_start: pedido.paraInicio,
      }],
      quem: pedido.quem,
      motivo: pedido.motivo,
      feedback: [{ operation_id: pedido.operation_id, skill: 'schedule', reason: motivoDoRemanejo(pedido) }],
    }),
    gravando,
    erro,
    limparErro,
  }), [remanejos, confirmar, gravando, erro, limparErro]);

  // A sequência do dia é rascunho até ser registrada, e vem por último: ela
  // reempacota a revisão que já está gravada.
  const reordenacao = useReordens(confirmar);
  const semana = useMemo(() => reordenacao.aplicar(revisada), [reordenacao, revisada]);

  const indice = useMemo(() => indexar(backlogVisto, semana), [backlogVisto, semana]);
  const abrirOrdem = useCallback((operationId: string) => setAlvo({ tipo: 'ordem', operationId }), []);

  // Um modal por vez: abrir uma ação fecha o detalhe da ordem que a chamou.
  const [acao, setAcao] = useState<AcaoAberta | null>(null);
  const [anuncio, setAnuncio] = useState<string | null>(null);
  const abrirAcao = useCallback((nova: AcaoAberta) => {
    setAlvo(null);
    setAnuncio(null);
    setAcao(nova);
  }, []);
  const tirarDaSemana = useCallback(
    (operationId: string) => abrirAcao({ tipo: 'remover', operationId }),
    [abrirAcao],
  );
  const marcarIndisponivel = useCallback(
    (tecnico: string, dia: string) => abrirAcao({ tipo: 'indisponivel', tecnico, dia }),
    [abrirAcao],
  );
  const alterarDuracao = useCallback(
    (operationId: string) => abrirAcao({ tipo: 'duracao', operationId }),
    [abrirAcao],
  );
  const incluir = useCallback(
    (operationId: string) => abrirAcao({ tipo: 'incluir', operationId }),
    [abrirAcao],
  );

  const dias = useMemo(
    () => diasDoPeriodo(run.request.period.start, run.request.period.end),
    [run],
  );

  const indisponiveis = useMemo(() => indisponiveisDaRevisao(ajustes ?? [], dias), [ajustes, dias]);

  // O dia aberto e o arraste moram acima das duas telas: a matriz manda para o
  // quadro do dia, e o cartão no ar precisa ser o mesmo dos dois lados.
  const [diaAberto, setDiaAberto] = useState('');
  const arraste = useArraste();

  const linhas = useMemo(
    () => linhasDaSemana(semana.assignments, backlogVisto.capacities, dias, indisponiveis),
    [semana, backlogVisto, dias, indisponiveis],
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
        <Stat label="Alocadas" value={semana.assignments.length.toLocaleString('pt-BR')} note={`de ${c.total_operations.toLocaleString('pt-BR')} no backlog`} tone="good" />
        <Stat label="Fora da semana" value={semana.unscheduled.length.toLocaleString('pt-BR')} note={`${c.capacity_limited_operations.toLocaleString('pt-BR')} por falta de HH na proposta`} tone="warn" />
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
          A conferência independente encontrou <strong>{violacoes}</strong> violações duras nesta semana.
          Enquanto elas existirem, só é possível rejeitar.{' '}
          <button type="button" className="btn" style={{ marginTop: 8 }} onClick={onVerViolacoes}>
            Ver a lista de violações
          </button>
        </div>
      )}

      <div className="note" style={{ marginBottom: 24 }}>
        A capacidade disponível cobre <strong>{c.coverage_percent.toFixed(1)}%</strong> da demanda do backlog.{' '}
        <strong>{c.capacity_limited_operations.toLocaleString('pt-BR')}</strong> das{' '}
        {c.unscheduled_operations.toLocaleString('pt-BR')} que ficaram de fora da proposta são limite de
        capacidade da equipe, não falha de recomendação.
      </div>

      {rev && rev.revision_sequence > 0 && (
        <div className="note" style={{ marginBottom: 24 }}>
          A semana abaixo é a <strong>revisão {rev.revision_sequence}</strong>: a proposta do agente com os
          seus ajustes. A proposta do agente continua gravada ao lado.
        </div>
      )}

      {anuncio && (
        <div className="note anuncio-ajuste" role="status" style={{ marginBottom: 24 }}>
          <span>{anuncio}</span>
          <button type="button" className="btn btn-menor" onClick={() => setAnuncio(null)}>Dispensar</button>
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
                base={revisada}
                titulos={indice.titulos}
                trocas={trocas}
                remanejos={remanejos}
                ativa={alvo?.tipo === 'ordem' ? alvo.operationId : null}
                total={semana.assignments.length}
                onAbrirOrdem={abrirOrdem}
                onTirarDaSemana={tirarDaSemana}
                onMarcarIndisponivel={marcarIndisponivel}
                marcas={marcas}
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
          base={revisada}
          backlog={backlogVisto}
          trocas={trocas}
          titulos={indice.titulos}
          ativa={alvo?.tipo === 'ordem' ? alvo.operationId : null}
          onAbrirOrdem={abrirOrdem}
          onTirarDaSemana={tirarDaSemana}
          indisponiveis={indisponiveis}
          onMarcarIndisponivel={marcarIndisponivel}
          marcas={marcas}
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
                  <td className="mono">{nomesDosTecnicos(a.worker_ids)}</td>
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
        <ForaDaSemana
          semana={semana}
          backlog={backlogVisto}
          periodo={run.request.period}
          titulos={indice.titulos}
          onAbrirOrdem={abrirOrdem}
          onIncluir={incluir}
        />
      </TabPanel>

      <RodapeAjustes
        revisao={rev}
        gravando={gravando}
        onDesfazer={() => { void revisor.desfazer(); }}
      />

      {acao && (
        <AcaoDeAjuste
          acao={acao}
          revisor={revisor}
          indice={indice}
          dias={dias}
          marcas={marcas}
          semana={semana}
          capacidades={backlogVisto.capacities}
          onFechar={() => setAcao(null)}
          onConfirmado={setAnuncio}
        />
      )}

      <DetalheModal
        alvo={alvo}
        onFechar={() => setAlvo(null)}
        indice={indice}
        backlog={backlogVisto}
        schedule={semana}
        trocas={trocas}
        trocar={trocar}
        onTirarDaSemana={tirarDaSemana}
        onAlterarDuracao={alterarDuracao}
        onIncluir={incluir}
        gravando={gravando}
        erro={erro}
        limparErro={limparErro}
      />
    </>
  );
}
