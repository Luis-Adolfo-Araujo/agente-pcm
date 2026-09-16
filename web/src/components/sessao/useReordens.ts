'use client';
import { useCallback, useMemo, useState } from 'react';
import { hora, type FeedbackDoAjuste, type RascunhoDeAjuste, type Schedule } from '@/lib/api';
import type { Confirmacao } from '@/components/sessao/useRevisao';
import {
  aplicarReordens, motivoDaReordenacao, reordenacaoDe, trocasDePosicao, type Mudanca, type Reordenacao,
} from '@/lib/reordenar';

/**
 * O rascunho da sequência de cada dia. Remexer a ordem de um dia são várias
 * arrastadas até ficar bom, então ele vive só na tela até alguém registrar — e
 * registrar grava um grupo na revisão, um `move` com hora para cada ordem cujo
 * horário mudou. Gravado, o rascunho some: a revisão já tem as horas novas.
 */
export function useReordens(confirmar: (pedido: Confirmacao) => Promise<boolean>) {
  const [reordens, setReordens] = useState<Reordenacao[]>([]);
  const [gravando, setGravando] = useState(false);

  const definir = useCallback((tecnico: string, dia: string, sequencia: string[]) => {
    setReordens((atuais) => [
      ...atuais.filter((r) => !(r.tecnico === tecnico && r.dia === dia)),
      { tecnico, dia, sequencia, registrada: false },
    ]);
  }, []);

  const desfazer = useCallback((tecnico: string, dia: string) => {
    setReordens((atuais) => atuais.filter((r) => !(r.tecnico === tecnico && r.dia === dia)));
  }, []);

  const registrar = useCallback(async (
    { tecnico, dia, motivo, quem, remexidas }:
    { tecnico: string; dia: string; motivo: string; quem: string; remexidas: Mudanca[] },
  ): Promise<boolean> => {
    if (remexidas.length === 0) return false;
    setGravando(true);
    try {
      // `replace_worker_id` igual a quem já faz: a ordem dividida mantém a
      // outra pessoa, e só a hora muda.
      const acoes = remexidas.map((m): RascunhoDeAjuste => ({
        kind: 'move', operation_id: m.operation_id, target_date: dia,
        target_worker_id: tecnico, replace_worker_id: tecnico, target_start: m.paraInicio,
      }));
      // Só vira feedback quem a pessoa tirou do lugar: as empurradas andaram de
      // horário por consequência, não por discordância.
      const feedback = trocasDePosicao(remexidas).map((m): FeedbackDoAjuste => ({
        operation_id: m.operation_id, skill: 'schedule', reason: motivoDaReordenacao(m, hora, motivo.trim()),
      }));
      const ok = await confirmar({ acoes, quem, motivo, feedback });
      if (ok) desfazer(tecnico, dia);
      return ok;
    } finally {
      setGravando(false);
    }
  }, [confirmar, desfazer]);

  /**
   * A sequência recebe uma ordem que chegou por troca depois de ela ter sido
   * desenhada. Isto não é uma decisão nova: o rascunho só ganha a ordem, na
   * posição que o relógio dela pede.
   */
  const absorver = useCallback((tecnico: string, dia: string, sequencia: string[]) => {
    setReordens((atuais) => atuais.map((r) => (
      r.tecnico === tecnico && r.dia === dia ? { ...r, sequencia } : r
    )));
  }, []);

  const aplicar = useMemo(
    () => (base: Schedule) => aplicarReordens(base, reordens),
    [reordens],
  );

  return {
    reordens,
    aplicar,
    definir,
    absorver,
    desfazer,
    registrar,
    gravando,
    pendenteEm: (tecnico: string, dia: string) => {
      const r = reordenacaoDe(reordens, tecnico, dia);
      return !!r && !r.registrada;
    },
  };
}
