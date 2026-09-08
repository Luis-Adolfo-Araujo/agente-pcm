'use client';
import { useEffect, useMemo, useState } from 'react';
import { Badge, Modal } from '@/components/ui';
import { DetalheOrdem } from '@/components/detalhe/DetalheOrdem';
import { TrocarTecnico, type Destino } from '@/components/detalhe/TrocarTecnico';
import type { Pedido } from '@/components/sessao/useTrocas';
import { REASON_NAMES, hora, type Backlog, type Schedule } from '@/lib/api';
import { carga, diaDe, escalaDoDia, minutosDe, tecnicosComEscala, type Indice } from '@/lib/semana';
import { trocaDaOrdem, type Troca } from '@/lib/trocas';

/**
 * O alvo é sempre uma ordem. O dia de uma pessoa não abre mais aqui: ele é o
 * quadro, que mostra as colunas inteiras sem tirar ninguém da tela.
 */
export type Alvo = { tipo: 'ordem'; operationId: string };

export function DetalheModal({
  alvo, onFechar, indice, backlog, schedule, trocas, trocar, gravando, erro, limparErro,
}: {
  alvo: Alvo | null;
  onFechar: () => void;
  indice: Indice;
  backlog: Backlog;
  /** A semana com trocas e sequências da sessão por cima. */
  schedule: Schedule;
  trocas: Troca[];
  trocar: (pedido: Pedido) => Promise<boolean>;
  gravando: boolean;
  erro: string | null;
  limparErro: () => void;
}) {
  // `null` = não está trocando. String vazia = trocando sem destino pré-escolhido.
  const [trocandoPara, setTrocandoPara] = useState<string | null>(null);
  const ordemId = alvo?.operationId ?? null;

  useEffect(() => {
    setTrocandoPara(null);
    limparErro();
  }, [alvo, limparErro]);

  const item = ordemId ? indice.enriched.get(ordemId) ?? null : null;
  const alocada = ordemId ? schedule.assignments.find((a) => a.operation_id === ordemId) ?? null : null;
  const fora = ordemId ? indice.fora.get(ordemId) ?? null : null;
  const troca = ordemId ? trocaDaOrdem(trocas, ordemId) ?? null : null;
  const diaDaOrdem = alocada ? diaDe(alocada.window.start) : null;

  /**
   * Para quem dá para passar: todo mundo com escala declarada naquele dia, menos
   * quem já está com a ordem. Os candidatos que o agente avaliou vêm primeiro,
   * ordenados pelo score dele; o resto vem depois, em ordem de nome.
   */
  const destinos = useMemo((): Destino[] => {
    if (!alocada || !diaDaOrdem || !item) return [];
    const ocupados = new Set(alocada.worker_ids);
    const avaliados = new Map(item.executants.map((e) => [e.worker_id, e]));
    return tecnicosComEscala(backlog.capacities, diaDaOrdem)
      .filter((w) => !ocupados.has(w))
      .map((worker_id): Destino => {
        const suas = schedule.assignments.filter(
          (a) => diaDe(a.window.start) === diaDaOrdem && a.worker_ids.includes(worker_id),
        );
        const avaliado = avaliados.get(worker_id);
        return {
          worker_id,
          score: avaliado?.score ?? null,
          eligible: avaliado?.eligible ?? null,
          carga: carga(suas),
          escala: escalaDoDia(backlog.capacities, worker_id, diaDaOrdem),
        };
      })
      .sort((a, b) => {
        if ((a.score === null) !== (b.score === null)) return a.score === null ? 1 : -1;
        if (a.score !== null && b.score !== null && a.score !== b.score) return b.score - a.score;
        return a.worker_id.localeCompare(b.worker_id);
      });
  }, [alocada, diaDaOrdem, item, backlog, schedule]);

  if (!alvo) return null;

  const titulo = item ? item.operation.title || item.operation.operation_id : '';

  /** O que ocupa o corpo do modal: a ordem aberta, ou a troca dela. */
  function painelDaOrdem() {
    if (!item) return null;

    if (trocandoPara !== null && alocada) {
      return (
        <>
          <button
            type="button"
            className="btn btn-menor"
            style={{ marginBottom: 'var(--space-md)' }}
            onClick={() => { limparErro(); setTrocandoPara(null); }}
          >
            Voltar para a ordem
          </button>
          <h2 className="detalhe-titulo">Passar para outra pessoa</h2>
          <div className="detalhe-marcas">
            <Badge tone="good">hoje com {alocada.worker_ids.join(', ')}</Badge>
            <span className="detalhe-nota">
              {hora(alocada.window.start)}–{hora(alocada.window.end)} · {minutosDe(alocada)} min
            </span>
          </div>
          <TrocarTecnico
            de={alocada.worker_ids[0] ?? ''}
            duracao={minutosDe(alocada)}
            destinos={destinos}
            inicial={trocandoPara || undefined}
            gravando={gravando}
            erro={erro}
            onConfirmar={async (pedido) => {
              const ok = await trocar({ ...pedido, operation_id: item!.operation.operation_id });
              if (ok) setTrocandoPara(null);
            }}
            onCancelar={() => { limparErro(); setTrocandoPara(null); }}
          />
        </>
      );
    }

    return (
      <>
        <h2 className="detalhe-titulo" title={titulo}>{titulo}</h2>
        <div className="detalhe-marcas">
          {fora
            ? <Badge tone="bad">fora da semana · {REASON_NAMES[fora.reason] ?? fora.reason}</Badge>
            : alocada && <Badge tone="good">{alocada.worker_ids.join(', ')}</Badge>}
          {troca && <Badge tone="warn">passada por você</Badge>}
          <span className="detalhe-nota">
            {alocada && `${hora(alocada.window.start)}–${hora(alocada.window.end)} · `}
            {item.duration.minutes ? `${item.duration.minutes} min` : 'sem duração'}
            {' · '}score {item.priority.score.toFixed(1)}
          </span>
        </div>
        <DetalheOrdem
          item={item}
          alocada={alocada}
          fora={fora}
          troca={troca}
          podeTrocar={!!alocada}
          onAbrirTroca={(destino) => { limparErro(); setTrocandoPara(destino ?? ''); }}
        />
      </>
    );
  }

  return (
    <Modal aberto onFechar={onFechar} expandido titulo={item ? titulo : 'Ordem não encontrada'}>
      {item ? painelDaOrdem() : (
        <p className="muted" style={{ margin: 0 }}>
          Esta operação não está no backlog desta execução. Monte a semana de novo para vê-la.
        </p>
      )}
    </Modal>
  );
}
