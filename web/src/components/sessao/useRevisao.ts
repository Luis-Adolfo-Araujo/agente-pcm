'use client';
import { useCallback, useEffect, useState } from 'react';
import {
  ApiError, api, salvarQuem,
  type FeedbackDoAjuste, type Previa, type RascunhoDeAjuste, type Revisao,
} from '@/lib/api';
import type { Remanejo } from '@/lib/remanejos';

/** Uma troca de executante pedida pela tela — pelo arraste, pelo teclado ou pelo modal. */
export type Pedido = { operation_id: string; de: string; para: string; motivo: string; quem: string };

/** Um movimento de dia pedido pelo trilho ou pela matriz. */
export type PedidoDeRemanejo = {
  operation_id: string;
  deDia: string;
  deInicio: string;
  deTecnico: string;
  paraDia: string;
  paraInicio: string;
  paraTecnico: string;
  motivo: string;
  quem: string;
};

/** O que o quadro e a matriz precisam para mover uma ordem de dia. */
export type Remanejador = {
  remanejos: Remanejo[];
  remanejar: (pedido: PedidoDeRemanejo) => Promise<boolean>;
  gravando: boolean;
  erro: string | null;
  limparErro: () => void;
};

/** Uma confirmação: as ações, as escolhas da prévia, quem, por quê e o que o agente aprende. */
export type Confirmacao = {
  acoes: RascunhoDeAjuste[];
  rejeitadas?: string[];
  aceitas?: string[];
  quem: string;
  motivo: string;
  feedback: FeedbackDoAjuste[];
};

function revisaoAtualDoErro(causa: ApiError): number | null {
  const detalhe = causa.detalhe;
  if (typeof detalhe !== 'object' || detalhe === null || !('current_revision' in detalhe)) return null;
  const atual = (detalhe as { current_revision: unknown }).current_revision;
  return typeof atual === 'number' ? atual : null;
}

/** A frase de uma recusa da API. O 409 de concorrência diz o que aconteceu, não só o número. */
export function mensagemDaApi(causa: unknown, acao: string): string {
  if (!(causa instanceof ApiError)) return `Não foi possível ${acao}. Nada mudou.`;
  if (revisaoAtualDoErro(causa) !== null) {
    return 'Outra sessão ajustou esta semana desde que você abriu. A tela foi atualizada; confira antes de tentar de novo.';
  }
  const detalhe = typeof causa.detalhe === 'string' ? ` ${causa.detalhe}.` : '';
  return `A API recusou (${causa.status}).${detalhe} Nada mudou.`;
}

/**
 * A revisão da semana: a proposta do agente mais os ajustes gravados. Mora
 * acima das etapas porque a semana e a decisão precisam ler a mesma.
 *
 * Grava primeiro, repinta depois: a tela só troca de revisão com a que a API
 * devolveu. Um 409 de concorrência recarrega, para ninguém seguir mexendo numa
 * semana que já não é a do banco.
 */
export function useRevisao(runId: string | null) {
  const [revisao, setRevisao] = useState<Revisao | null>(null);
  const [gravando, setGravando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const limparErro = useCallback(() => setErro(null), []);

  const recarregar = useCallback(async () => {
    if (!runId) { setRevisao(null); return; }
    try {
      setRevisao(await api.revision(runId));
    } catch (causa) {
      setErro(mensagemDaApi(causa, 'carregar a revisão'));
    }
  }, [runId]);

  useEffect(() => {
    setRevisao(null);
    setErro(null);
    void recarregar();
  }, [recarregar]);

  const previa = useCallback(async (
    acoes: RascunhoDeAjuste[], rejeitadas: string[], aceitas: string[],
  ): Promise<Previa> => {
    if (!runId || !revisao) throw new Error('a revisão ainda não carregou');
    return api.previewAdjustments(runId, {
      actions: acoes, rejected: rejeitadas, accepted: aceitas, expected_revision: revisao.revision_sequence,
    });
  }, [runId, revisao]);

  const confirmar = useCallback(async (pedido: Confirmacao): Promise<boolean> => {
    if (!runId || !revisao) return false;
    setGravando(true);
    setErro(null);
    try {
      const nova = await api.confirmAdjustments(runId, {
        actions: pedido.acoes,
        rejected: pedido.rejeitadas ?? [],
        accepted: pedido.aceitas ?? [],
        expected_revision: revisao.revision_sequence,
        recorded_by: pedido.quem.trim(),
        reason: pedido.motivo.trim() || null,
        feedback: pedido.feedback,
      });
      salvarQuem(pedido.quem);
      setRevisao(nova);
      return true;
    } catch (causa) {
      setErro(mensagemDaApi(causa, 'gravar o ajuste'));
      if (causa instanceof ApiError && revisaoAtualDoErro(causa) !== null) await recarregar();
      return false;
    } finally {
      setGravando(false);
    }
  }, [runId, revisao, recarregar]);

  const desfazer = useCallback(async (): Promise<boolean> => {
    if (!runId) return false;
    setGravando(true);
    setErro(null);
    try {
      setRevisao(await api.undoAdjustments(runId));
      return true;
    } catch (causa) {
      setErro(mensagemDaApi(causa, 'desfazer'));
      return false;
    } finally {
      setGravando(false);
    }
  }, [runId]);

  return { revisao, previa, confirmar, desfazer, recarregar, gravando, erro, limparErro };
}

export type Revisor = ReturnType<typeof useRevisao>;
