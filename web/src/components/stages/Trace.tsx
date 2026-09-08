'use client';
import { useMemo, useState } from 'react';
import { Badge, Table } from '@/components/ui';
import { BANDA, FONTE, MATERIAL } from '@/lib/rotulos';
import {
  REASON_NAMES,
  SKILLS_PARALELAS,
  STAGE_NAMES,
  hhmm,
  resumoContagens,
  segundos,
  type Backlog,
  type Enriched,
  type Run,
  type Schedule,
  type Snapshot,
  type Verification,
} from '@/lib/api';

/* A escala é do azul da marca para o cinza: fundamento forte no azul cheio,
   valor assumido no azul claro, ausência no vermelho de estado. O laranja da
   marca não entra aqui — ele marca a etapa atual e nada mais. */
const COR = {
  forte: 'var(--senai-azul)',
  assumido: 'var(--senai-azul-claro)',
  ausente: 'var(--color-blocked)',
  neutro: 'var(--cinza-300)',
  frio: 'var(--azul-100)',
} as const;


type Segmento = { chave: string; rotulo: string; cor: string; itens: Enriched[] };
type Filtro = { skill: string; chave: string } | null;

function agrupar(
  itens: Enriched[],
  chaveDe: (item: Enriched) => string,
  ordem: { chave: string; rotulo: string; cor: string }[],
): Segmento[] {
  const mapa = new Map<string, Enriched[]>();
  itens.forEach((item) => {
    const chave = chaveDe(item);
    if (!mapa.has(chave)) mapa.set(chave, []);
    mapa.get(chave)!.push(item);
  });
  const conhecidas = ordem
    .map((spec) => ({ ...spec, itens: mapa.get(spec.chave) ?? [] }))
    .filter((seg) => seg.itens.length > 0);
  const restantes = [...mapa.entries()]
    .filter(([chave]) => !ordem.some((spec) => spec.chave === chave))
    .map(([chave, itens]) => ({ chave, rotulo: chave, cor: COR.neutro, itens }));
  return [...conhecidas, ...restantes].sort((a, b) => b.itens.length - a.itens.length);
}

function Barra({ skill, segmentos, filtro, onPick }: {
  skill: string; segmentos: Segmento[]; filtro: Filtro; onPick: (f: Filtro) => void;
}) {
  const total = segmentos.reduce((soma, seg) => soma + seg.itens.length, 0);
  if (total === 0) return null;
  return (
    <>
      <div className="dist">
        {segmentos.map((seg) => {
          const ativo = filtro?.skill === skill && filtro.chave === seg.chave;
          return (
            <button
              key={seg.chave}
              type="button"
              className="dist-seg"
              style={{ width: `${(seg.itens.length / total) * 100}%`, background: seg.cor }}
              aria-pressed={ativo}
              title={`${seg.rotulo}: ${seg.itens.length.toLocaleString('pt-BR')}`}
              onClick={() => onPick(ativo ? null : { skill, chave: seg.chave })}
            >
              <span className="sr-only">{`${seg.rotulo}: ${seg.itens.length} ordens`}</span>
            </button>
          );
        })}
      </div>
      <div className="dist-legend">
        {segmentos.map((seg) => (
          <span key={seg.chave} className="dist-key">
            <i style={{ background: seg.cor }} />
            {seg.rotulo} <b>{seg.itens.length.toLocaleString('pt-BR')}</b>
          </span>
        ))}
      </div>
    </>
  );
}

function TabelaOrdens({ itens, coluna, valor, bruto }: {
  itens: Enriched[];
  coluna: string;
  valor: (item: Enriched) => string;
  bruto: (item: Enriched) => unknown;
}) {
  const visiveis = itens.slice(0, 40);
  return (
    <div style={{ marginTop: 'var(--space-md)' }}>
      <Table head={<><th>OS</th><th>Serviço</th><th>{coluna}</th><th>Na semana</th><th /></>}>
        {visiveis.map((item) => (
          <tr key={item.operation.operation_id}>
            <td className="mono" title={item.operation.work_order_id}>{item.operation.work_order_id.slice(-6)}</td>
            <td>{item.operation.title || '—'}</td>
            <td>{valor(item)}</td>
            <td>{item.scheduled ? <Badge tone="good">sim</Badge> : <Badge tone="mute">não</Badge>}</td>
            <td>
              <details className="trace-json">
                <summary>saída crua</summary>
                <pre>{JSON.stringify(bruto(item), null, 2)}</pre>
              </details>
            </td>
          </tr>
        ))}
      </Table>
      {itens.length > visiveis.length && (
        <p className="muted" style={{ fontSize: '.84rem' }}>
          Mostrando 40 de {itens.length.toLocaleString('pt-BR')}.
        </p>
      )}
    </div>
  );
}

function Estagio({ nome, tempo, resumo, aninhado, children }: {
  nome: string; tempo?: number; resumo?: string; aninhado?: boolean; children?: React.ReactNode;
}) {
  return (
    <li className="trace-stage" data-skill={aninhado ? 'true' : undefined}>
      <div className="trace-head">
        <span className="trace-name">{nome}</span>
        {tempo !== undefined && <span className="trace-time">{segundos(tempo)}</span>}
        {resumo && <span className="trace-counts">{resumo}</span>}
      </div>
      {children && <div className="trace-body">{children}</div>}
    </li>
  );
}

export function Trace({ run, snapshot, backlog, schedule, verification }: {
  run: Run; snapshot: Snapshot; backlog: Backlog; schedule: Schedule; verification: Verification;
}) {
  const [filtro, setFiltro] = useState<Filtro>(null);
  const itens = backlog.backlog;
  const tempoDe = (stage: string) => run.trace_events.find((e) => e.stage === stage)?.elapsed_ms;
  const contagemDe = (stage: string) => {
    const evento = run.trace_events.find((e) => e.stage === stage);
    return evento ? resumoContagens(evento.counts) : undefined;
  };

  const bandas = useMemo(() => agrupar(itens, (i) => i.priority.band, [
    { chave: 'very_high', rotulo: BANDA.very_high, cor: COR.ausente },
    { chave: 'high', rotulo: BANDA.high, cor: COR.assumido },
    { chave: 'medium', rotulo: BANDA.medium, cor: COR.neutro },
    { chave: 'low', rotulo: BANDA.low, cor: COR.frio },
  ]), [itens]);

  const fontes = useMemo(() => agrupar(itens, (i) => i.duration.source, [
    { chave: 'planned', rotulo: FONTE.planned, cor: COR.forte },
    { chave: 'same_activity_and_asset', rotulo: FONTE.same_activity_and_asset, cor: COR.forte },
    { chave: 'same_asset', rotulo: FONTE.same_asset, cor: COR.assumido },
    { chave: 'same_activity', rotulo: FONTE.same_activity, cor: COR.assumido },
    { chave: 'same_location', rotulo: FONTE.same_location, cor: COR.assumido },
    { chave: 'similar_title', rotulo: FONTE.similar_title, cor: COR.assumido },
    { chave: 'global_median', rotulo: FONTE.global_median, cor: COR.neutro },
    { chave: 'default', rotulo: FONTE.default, cor: COR.neutro },
    { chave: 'unavailable', rotulo: FONTE.unavailable, cor: COR.ausente },
  ]), [itens]);

  const materiais = useMemo(() => agrupar(itens, (i) => i.materials.status, [
    { chave: 'available', rotulo: MATERIAL.available[0], cor: COR.forte },
    { chave: 'partial', rotulo: MATERIAL.partial[0], cor: COR.assumido },
    { chave: 'unavailable', rotulo: MATERIAL.unavailable[0], cor: COR.ausente },
    { chave: 'unknown', rotulo: MATERIAL.unknown[0], cor: COR.neutro },
  ]), [itens]);

  const executantes = useMemo(() => agrupar(itens, (item) => {
    if (item.executants.length === 0) return 'nenhum';
    return item.executants.some((e) => e.eligible) ? 'elegivel' : 'inelegivel';
  }, [
    { chave: 'elegivel', rotulo: 'com candidato elegível', cor: COR.forte },
    { chave: 'inelegivel', rotulo: 'só candidatos inelegíveis', cor: COR.assumido },
    { chave: 'nenhum', rotulo: 'sem candidato', cor: COR.ausente },
  ]), [itens]);

  const semAmostra = itens.filter((i) => i.duration.sample_size === 0).length;
  const bloqueiam = itens.filter((i) => i.materials.blocking).length;
  const semFundamento = itens.filter((i) => i.priority.missing_fields.length > 0).length;
  const confianca = itens.length
    ? itens.reduce((soma, i) => soma + i.duration.confidence, 0) / itens.length
    : 0;

  const hhBruto = backlog.capacities.reduce((soma, c) => soma + c.gross_minutes, 0);
  const hhComprometido = backlog.capacities.reduce((soma, c) => soma + c.committed_minutes, 0);
  const hhLivre = backlog.capacities.reduce((soma, c) => soma + c.net_minutes, 0);

  const foraPorMotivo = useMemo(() => {
    const mapa = new Map<string, typeof schedule.unscheduled>();
    schedule.unscheduled.forEach((item) => {
      if (!mapa.has(item.reason)) mapa.set(item.reason, []);
      mapa.get(item.reason)!.push(item);
    });
    return mapa;
  }, [schedule]);

  const titulos = useMemo(() => {
    const mapa = new Map<string, string>();
    itens.forEach((item) => mapa.set(item.operation.operation_id, item.operation.title));
    return mapa;
  }, [itens]);

  const selecionados = (skill: string, segmentos: Segmento[]) =>
    filtro?.skill === skill ? segmentos.find((s) => s.chave === filtro.chave)?.itens ?? [] : [];

  const cfg = (run.config ?? {}) as Record<string, Record<string, unknown> | undefined>;
  const param = (grupo: string, chave: string) => {
    const valor = cfg[grupo]?.[chave];
    return valor === undefined ? '—' : String(valor);
  };

  return (
    <>
      <dl className="prov">
        <div>
          <dt>Recorte</dt>
          <dd title={snapshot.snapshot_id}>{snapshot.snapshot_id.slice(-24)}</dd>
        </div>
        <div>
          <dt>sha256 dos dados</dt>
          <dd>{snapshot.sha256.slice(0, 24)}…</dd>
        </div>
        <div>
          <dt>Período proposto</dt>
          <dd>
            {new Date(run.request.period.start).toLocaleDateString('pt-BR')} – {new Date(run.request.period.end).toLocaleDateString('pt-BR')}
          </dd>
        </div>
        <div>
          <dt>Versão das regras</dt>
          <dd>{run.request.ruleset_version ?? '—'}</dd>
        </div>
        <div>
          <dt>Versão dos pesos</dt>
          <dd>{(run.request.weights_version ?? '—').slice(0, 24)}…</dd>
        </div>
        <div>
          <dt>Impressão da entrada verificada</dt>
          <dd>{verification.input_hash.slice(0, 24)}…</dd>
        </div>
      </dl>

      <p className="muted" style={{ maxWidth: '68ch' }}>
        Cada etapa abaixo é uma execução real desta run: o tempo vem do trace, os números vêm da
        saída da skill. Clique numa faixa para ver as ordens que caíram naquele caso, e abra
        “saída crua” para o JSON que a skill devolveu.
      </p>

      <ol className="trace">
        <Estagio
          nome={STAGE_NAMES.snapshot_validated}
          tempo={tempoDe('snapshot_validated')}
          resumo={contagemDe('snapshot_validated')}
        />

        <Estagio
          nome={STAGE_NAMES.skills_parallel}
          tempo={tempoDe('skills_parallel')}
          resumo={`${SKILLS_PARALELAS.length} skills ao mesmo tempo`}
        >
          <ol className="trace-nested">
            <Estagio
              nome={STAGE_NAMES['skill.rank_backlog']}
              tempo={tempoDe('skill.rank_backlog')}
              resumo={`${itens.length.toLocaleString('pt-BR')} scores · ${semFundamento.toLocaleString('pt-BR')} com campo ausente`}
              aninhado
            >
              <Barra skill="rank" segmentos={bandas} filtro={filtro} onPick={setFiltro} />
              <p className="muted" style={{ fontSize: '.82rem', marginBottom: 0 }}>
                Pesos em uso: prioridade {param('ranking', 'priority_weight')} · prazo {param('ranking', 'sla_weight')} ·
                idade {param('ranking', 'age_weight')} · criticidade {param('ranking', 'criticality_weight')}.
              </p>
              {filtro?.skill === 'rank' && (
                <TabelaOrdens
                  itens={selecionados('rank', bandas)}
                  coluna="Score"
                  valor={(item) => item.priority.score.toFixed(0)}
                  bruto={(item) => item.priority}
                />
              )}
            </Estagio>

            <Estagio
              nome={STAGE_NAMES['skill.estimate_duration']}
              tempo={tempoDe('skill.estimate_duration')}
              resumo={`confiança média ${(confianca * 100).toFixed(0)}% · ${semAmostra.toLocaleString('pt-BR')} sem histórico comparável`}
              aninhado
            >
              <Barra skill="duracao" segmentos={fontes} filtro={filtro} onPick={setFiltro} />
              <p className="muted" style={{ fontSize: '.82rem', marginBottom: 0 }}>
                Amostra mínima {param('duration', 'minimum_sample_size')} execuções · valor assumido {param('duration', 'default_minutes')} min.
              </p>
              {filtro?.skill === 'duracao' && (
                <TabelaOrdens
                  itens={selecionados('duracao', fontes)}
                  coluna="Duração"
                  valor={(item) => (item.duration.minutes ? `${item.duration.minutes} min` : '—')}
                  bruto={(item) => item.duration}
                />
              )}
            </Estagio>

            <Estagio
              nome={STAGE_NAMES['skill.check_materials']}
              tempo={tempoDe('skill.check_materials')}
              resumo={`${bloqueiam.toLocaleString('pt-BR')} ordens bloqueadas por material`}
              aninhado
            >
              <Barra skill="material" segmentos={materiais} filtro={filtro} onPick={setFiltro} />
              {filtro?.skill === 'material' && (
                <TabelaOrdens
                  itens={selecionados('material', materiais)}
                  coluna="Material"
                  valor={(item) => MATERIAL[item.materials.status]?.[0] ?? item.materials.status}
                  bruto={(item) => item.materials}
                />
              )}
            </Estagio>

            <Estagio
              nome={STAGE_NAMES['skill.calculate_capacity']}
              tempo={tempoDe('skill.calculate_capacity')}
              resumo={`${backlog.capacities.length} pessoas · ${hhmm(hhLivre)} livres de ${hhmm(hhBruto)}`}
              aninhado
            >
              <div className="dist">
                <div className="dist-seg" style={{ width: `${hhBruto ? (hhComprometido / hhBruto) * 100 : 0}%`, background: COR.assumido }} />
                <div className="dist-seg" style={{ width: `${hhBruto ? (hhLivre / hhBruto) * 100 : 0}%`, background: COR.forte }} />
              </div>
              <div className="dist-legend">
                <span className="dist-key"><i style={{ background: COR.assumido }} />já comprometido <b>{hhmm(hhComprometido)}</b></span>
                <span className="dist-key"><i style={{ background: COR.forte }} />livre para a semana <b>{hhmm(hhLivre)}</b></span>
              </div>
              <div style={{ marginTop: 'var(--space-md)' }}>
                <Table head={<><th>Pessoa</th><th className="num">Bruto</th><th className="num">Comprometido</th><th className="num">Líquido</th><th /></>}>
                  {backlog.capacities.map((c) => (
                    <tr key={c.worker_id}>
                      <td className="mono">{c.worker_id}</td>
                      <td className="num">{hhmm(c.gross_minutes)}</td>
                      <td className="num">{hhmm(c.committed_minutes)}</td>
                      <td className="num">{hhmm(c.net_minutes)}</td>
                      <td>
                        <details className="trace-json">
                          <summary>saída crua</summary>
                          <pre>{JSON.stringify(c, null, 2)}</pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                </Table>
              </div>
            </Estagio>
          </ol>
        </Estagio>

        <Estagio
          nome={STAGE_NAMES.executant_candidates}
          tempo={tempoDe('executant_candidates')}
          resumo={contagemDe('executant_candidates')}
        >
          <Barra skill="executante" segmentos={executantes} filtro={filtro} onPick={setFiltro} />
          <p className="muted" style={{ fontSize: '.82rem', marginBottom: 0 }}>
            Até {param('executants', 'top_n')} candidatos por ordem · peso de ativo {param('executants', 'asset_weight')} ·
            atividade {param('executants', 'activity_weight')} · equipe {param('executants', 'team_weight')}.
          </p>
          {filtro?.skill === 'executante' && (
            <TabelaOrdens
              itens={selecionados('executante', executantes)}
              coluna="Melhor candidato"
              valor={(item) => (item.executants[0] ? `${item.executants[0].worker_id} · ${item.executants[0].score.toFixed(0)}` : '—')}
              bruto={(item) => item.executants}
            />
          )}
        </Estagio>

        <Estagio
          nome={STAGE_NAMES.optimization}
          tempo={tempoDe('optimization')}
          resumo={`${schedule.assignments.length.toLocaleString('pt-BR')} alocadas · ${schedule.unscheduled.length.toLocaleString('pt-BR')} fora`}
        >
          <div className="dist">
            <div
              className="dist-seg"
              style={{ width: `${schedule.coverage.total_operations ? (schedule.coverage.scheduled_operations / schedule.coverage.total_operations) * 100 : 0}%`, background: COR.forte }}
            />
            {Object.entries(schedule.coverage.reasons).sort((a, b) => b[1] - a[1]).map(([motivo, quantas], i) => (
              <button
                key={motivo}
                type="button"
                className="dist-seg"
                style={{
                  width: `${(quantas / Math.max(1, schedule.coverage.total_operations)) * 100}%`,
                  background: i === 0 ? COR.assumido : COR.ausente,
                }}
                aria-pressed={filtro?.skill === 'otimizacao' && filtro.chave === motivo}
                title={`${REASON_NAMES[motivo] ?? motivo}: ${quantas}`}
                onClick={() => setFiltro(
                  filtro?.skill === 'otimizacao' && filtro.chave === motivo
                    ? null
                    : { skill: 'otimizacao', chave: motivo },
                )}
              >
                <span className="sr-only">{`${REASON_NAMES[motivo] ?? motivo}: ${quantas} ordens`}</span>
              </button>
            ))}
          </div>
          <div className="dist-legend">
            <span className="dist-key"><i style={{ background: COR.forte }} />na semana <b>{schedule.coverage.scheduled_operations.toLocaleString('pt-BR')}</b></span>
            {Object.entries(schedule.coverage.reasons).sort((a, b) => b[1] - a[1]).map(([motivo, quantas]) => (
              <span key={motivo} className="dist-key">
                <i style={{ background: motivo === 'no_capacity' ? COR.assumido : COR.ausente }} />
                {REASON_NAMES[motivo] ?? motivo} <b>{quantas.toLocaleString('pt-BR')}</b>
              </span>
            ))}
          </div>
          {filtro?.skill === 'otimizacao' && (
            <div style={{ marginTop: 'var(--space-md)' }}>
              <Table head={<><th>OS</th><th>Serviço</th><th>O que travou</th></>}>
                {(foraPorMotivo.get(filtro.chave) ?? []).slice(0, 40).map((item) => (
                  <tr key={item.operation_id}>
                    <td className="mono" title={item.work_order_id}>{item.work_order_id.slice(-6)}</td>
                    <td>{titulos.get(item.operation_id) ?? '—'}</td>
                    <td className="muted">{item.details.length > 0 ? item.details.join(' · ') : REASON_NAMES[item.reason] ?? item.reason}</td>
                  </tr>
                ))}
              </Table>
              {(foraPorMotivo.get(filtro.chave)?.length ?? 0) > 40 && (
                <p className="muted" style={{ fontSize: '.84rem' }}>
                  Mostrando 40 de {foraPorMotivo.get(filtro.chave)!.length.toLocaleString('pt-BR')}.
                </p>
              )}
            </div>
          )}
        </Estagio>

        <Estagio
          nome={STAGE_NAMES.verification}
          tempo={tempoDe('verification')}
          resumo={verification.valid ? 'nenhuma violação dura' : `${verification.violations.length} violações`}
        >
          {verification.violations.length === 0 ? (
            <p className="muted" style={{ margin: 0 }}>
              A conferência independente refez as contas sobre a mesma entrada e não achou violação dura.
            </p>
          ) : (
            <Table head={<><th>Código</th><th>Gravidade</th><th>OS</th><th>Detalhe</th></>}>
              {verification.violations.map((v, i) => (
                <tr key={`${v.code}-${v.operation_id ?? i}`}>
                  <td className="mono">{v.code}</td>
                  <td><Badge tone={v.severity === 'error' ? 'bad' : 'warn'}>{v.severity}</Badge></td>
                  <td className="mono">{v.operation_id ? v.operation_id.slice(-6) : '—'}</td>
                  <td>{v.details}</td>
                </tr>
              ))}
            </Table>
          )}
        </Estagio>

        <Estagio
          nome={STAGE_NAMES.proposal_ready}
          tempo={tempoDe('proposal_ready')}
          resumo={run.summary ? `proposta ${run.summary.proposal_status}` : undefined}
        />
      </ol>
    </>
  );
}
