'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Chevron, type EstadoEtapa, type Metrica } from '@/components/Chevron';
import { Base } from '@/components/stages/Base';
import { Decidir } from '@/components/stages/Decidir';
import { Montar } from '@/components/stages/Montar';
import { Semana } from '@/components/stages/Semana';
import { EmptyState } from '@/components/ui';
import {
  ApiError,
  BASE,
  api,
  composicaoDoBacklog,
  segundos,
  type Backlog,
  type Run,
  type Schedule,
  type Snapshot,
  type Verification,
} from '@/lib/api';

const ETAPAS = [
  { id: 1, nome: 'Escolher a base' },
  { id: 2, nome: 'Montar a semana' },
  { id: 3, nome: 'Ver a semana' },
  { id: 4, nome: 'Decidir' },
] as const;

/** Uma falha de rede e um 401 não são o mesmo problema, e não podem virar a mesma frase. */
function mensagem(erro: unknown): string {
  if (erro instanceof ApiError) {
    if (erro.status === 401) {
      return 'A API recusou a credencial. Configure NEXT_PUBLIC_API_TOKEN com a senha do ambiente e recarregue.';
    }
    if (erro.status === 404) return 'A API não achou esse recorte ou essa execução.';
    if (erro.status === 409) return 'A execução ainda não tem esse artefato pronto.';
    if (erro.status === 422) return 'A API recusou o período. Confira o primeiro e o último dia.';
    return `A API respondeu ${erro.status} em ${erro.path}.`;
  }
  return `Não foi possível falar com a API do piloto em ${BASE}.`;
}

/**
 * Espaço da assinatura oficial: 36 px de altura (redução mínima do manual do
 * Sistema Indústria para desktop) com a área de proteção à esquerda. Enquanto o
 * arquivo oficial não estiver em /public/senai.svg, o lugar fica marcado — o
 * logotipo não é redesenhado à mão.
 */
function Assinatura() {
  const [temArquivo, setTemArquivo] = useState(false);

  // Renderizar a <img> direto e esperar o onError não funciona: o browser pede o
  // arquivo enquanto lê o HTML do servidor, e o erro acontece antes de o React
  // hidratar — o handler nunca roda e sobra o ícone de imagem quebrada. Então o
  // arquivo é testado depois da montagem, e o espaço marcado é o estado inicial.
  useEffect(() => {
    const teste = new window.Image();
    teste.onload = () => setTemArquivo(true);
    teste.src = '/senai.svg';
  }, []);

  return (
    <div className="brand-signature">
      {temArquivo ? (
        <img src="/senai.svg" alt="SENAI" />
      ) : (
        <span className="brand-slot" title="Coloque o SVG oficial em public/senai.svg">
          assinatura senai · 36px
        </span>
      )}
    </div>
  );
}

export default function Home() {
  const [etapa, setEtapa] = useState(1);
  // Um contador, não um booleano: dois pedidos seguidos do trace precisam abrir
  // o bloco duas vezes, e um booleano já ligado não avisaria a segunda.
  const [pedidoDeTrace, setPedidoDeTrace] = useState(0);
  const [visitadas, setVisitadas] = useState<number[]>([1]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [snapshotId, setSnapshotId] = useState<string | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [backlog, setBacklog] = useState<Backlog | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [working, setWorking] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    api.snapshots()
      .then((lista) => {
        setSnapshots(lista);
        if (lista.length > 0) setSnapshotId(lista[0].snapshot_id);
      })
      .catch((causa) => setErro(mensagem(causa)))
      .finally(() => setCarregando(false));
  }, []);

  // Enquanto a montagem roda, buscamos o estado até terminar.
  useEffect(() => {
    if (!run || run.status === 'completed' || run.status === 'failed') return;
    const timer = setInterval(() => {
      api.run(run.run_id).then(setRun).catch((causa) => setErro(mensagem(causa)));
    }, 1200);
    return () => clearInterval(timer);
  }, [run]);

  // Uma execução que falhou precisa dizer isso na tela, não só na barra de cima.
  useEffect(() => {
    if (run?.status !== 'failed') return;
    setErro(run.error ?? 'A montagem falhou no agente. Nada foi gravado; dá para tentar de novo.');
  }, [run]);

  // Assim que a semana fica pronta, carregamos os artefatos.
  useEffect(() => {
    if (!run || run.status !== 'completed' || schedule) return;
    Promise.all([api.schedule(run.run_id), api.backlog(run.run_id), api.verification(run.run_id)])
      .then(([s, b, v]) => {
        setSchedule(s);
        setBacklog(b);
        setVerification(v);
        // Só puxa quem está esperando a montagem; quem foi ler outra etapa fica onde está.
        setEtapa((atual) => (atual === 2 ? 3 : atual));
        setVisitadas((lista) => (lista.includes(3) ? lista : [...lista, 3]));
      })
      .catch((causa) => setErro(mensagem(causa)));
  }, [run, schedule]);

  const montar = useCallback(async (inicio: string, fim: string) => {
    if (!snapshotId) return;
    setWorking(true);
    setErro(null);
    setSchedule(null);
    setBacklog(null);
    setVerification(null);
    try {
      setRun(await api.startRun({ snapshot_id: snapshotId, period_start: inicio, period_end: fim }));
    } catch (causa) {
      setErro(mensagem(causa));
    } finally {
      setWorking(false);
    }
  }, [snapshotId]);

  const decidir = useCallback(async (decisao: 'approve' | 'reject', quem: string, motivo: string) => {
    if (!run) return;
    setWorking(true);
    setErro(null);
    try {
      setRun(await api.decide(run.run_id, { decision: decisao, decided_by: quem, reason: motivo }));
    } catch (causa) {
      setErro(mensagem(causa));
    } finally {
      setWorking(false);
    }
  }, [run]);

  const snapshot = snapshots.find((s) => s.snapshot_id === snapshotId) ?? null;
  const rodando = !!run && run.status !== 'completed' && run.status !== 'failed';
  const falhou = run?.status === 'failed';
  const pronta = run?.status === 'completed' && !!schedule;
  const tempoTotal = useMemo(
    () => (run?.trace_events ?? [])
      .filter((evento) => !evento.stage.startsWith('skill.'))
      .reduce((soma, evento) => soma + evento.elapsed_ms, 0),
    [run],
  );

  function irPara(id: number) {
    setEtapa(id);
    setVisitadas((lista) => (lista.includes(id) ? lista : [...lista, id]));
  }

  function estadoDe(id: number): EstadoEtapa {
    if (id === etapa) return 'current';
    if (id === 1) return snapshot ? 'done' : 'available';
    if (id === 2) return pronta ? 'done' : 'available';
    if (!pronta) return 'locked';
    if (id === 4) return run?.decision ? 'done' : 'available';
    return visitadas.includes(id) ? 'done' : 'available';
  }

  function metricaDe(id: number): Metrica {
    if (id === 1) {
      // A métrica da etapa é o que dá para programar, não quantas linhas vieram.
      if (!snapshot) return { value: '—' };
      const b = composicaoDoBacklog(snapshot.quality);
      return b.parcial
        ? { value: `${b.total.toLocaleString('pt-BR')} OS` }
        : { value: `${b.available.toLocaleString('pt-BR')} disponíveis` };
    }
    if (id === 2) {
      if (rodando) return { value: 'montando…', tone: 'warn' };
      if (falhou) return { value: 'falhou', tone: 'bad' };
      return run && tempoTotal > 0 ? { value: segundos(tempoTotal) } : { value: '—' };
    }
    if (id === 3) {
      if (!schedule) return { value: '—' };
      // A violação dura decide se dá para aprovar: ela ganha a métrica quando existe.
      if (verification && verification.violations.length > 0) {
        return { value: `${verification.violations.length} violações`, tone: 'bad' };
      }
      const c = schedule.coverage;
      return {
        value: `${c.scheduled_operations.toLocaleString('pt-BR')}/${c.total_operations.toLocaleString('pt-BR')}`,
        tone: 'good',
      };
    }
    if (!run?.decision) return pronta ? { value: 'pendente', tone: 'warn' } : { value: '—' };
    const quando = new Date(run.decision.decided_at).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
    return run.decision.decision === 'approve'
      ? { value: `aprovada ${quando}`, tone: 'good' }
      : { value: `rejeitada ${quando}`, tone: 'bad' };
  }

  const etapas = ETAPAS.map((e) => ({
    id: e.id,
    nome: e.nome,
    estado: estadoDe(e.id),
    metrica: metricaDe(e.id),
  }));

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-head">
          <div className="brand">
            <div className="brand-name">
              MAIA
              <span>Programação de manutenção</span>
            </div>
            <Assinatura />
          </div>
          <div className="topbar-state">
            <div className="topbar-guarantee">somente leitura · nada escreve na Tractian</div>
            <div>
              {run
                ? <>execução <strong>{run.status}</strong>{run.summary ? ` · ${run.summary.assignments.toLocaleString('pt-BR')} alocadas · ${run.summary.unscheduled.toLocaleString('pt-BR')} fora` : ''}</>
                : 'nenhuma semana montada'}
            </div>
          </div>
        </div>
        <div className="rail-band">
          <Chevron etapas={etapas} onSelect={irPara} />
        </div>
      </header>

      <main className="shell-main">
        <div className="shell-inner">
          {carregando && <EmptyState title="Carregando o piloto" />}

          {!carregando && erro && !snapshot && (
            <EmptyState title="Sem conexão com o piloto" description={erro} />
          )}

          {!carregando && snapshot && (
            <>
              {etapa === 1 && (
                <Base
                  snapshots={snapshots}
                  selected={snapshot}
                  onSelect={setSnapshotId}
                  onNext={() => irPara(2)}
                />
              )}
              {etapa === 2 && (
                <Montar
                  snapshot={snapshot}
                  run={run}
                  backlog={backlog}
                  schedule={schedule}
                  verification={verification}
                  onStart={montar}
                  abrirTrace={pedidoDeTrace}
                  working={working}
                  error={erro}
                />
              )}
              {etapa === 3 && (run && schedule && backlog && verification
                ? <Semana
                    run={run}
                    schedule={schedule}
                    backlog={backlog}
                    verification={verification}
                    onVerViolacoes={() => { setPedidoDeTrace((n) => n + 1); irPara(2); }}
                  />
                : <EmptyState title="Nenhuma semana montada ainda" description="Volte à etapa 2 e monte a primeira." />)}
              {etapa === 4 && (run && verification
                ? <Decidir run={run} verification={verification} onDecide={decidir} working={working} error={erro} />
                : <EmptyState title="Nada para decidir ainda" description="Monte a semana primeiro." />)}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
