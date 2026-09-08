'use client';
import { useCallback, useMemo, useState } from 'react';
import { ApiError, api, hora, salvarQuem, type FeedbackItem, type Schedule } from '@/lib/api';
import {
  aplicarReordens, motivoDaReordenacao, reordenacaoDe, type Mudanca, type Reordenacao,
} from '@/lib/reordenar';

/**
 * A sequência só sai da sessão quando alguém a registra com um motivo — e a
 * ordem importa: gravar primeiro, marcar como registrada depois. O contrário
 * deixaria a tela dizendo que o agente aprendeu algo que não saiu daqui.
 */
export function useReordens(runId: string | null, schedule: Schedule | null) {
  const [reordens, setReordens] = useState<Reordenacao[]>([]);
  const [gravando, setGravando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const definir = useCallback((tecnico: string, dia: string, sequencia: string[]) => {
    setErro(null);
    setReordens((atuais) => [
      ...atuais.filter((r) => !(r.tecnico === tecnico && r.dia === dia)),
      { tecnico, dia, sequencia, registrada: false },
    ]);
  }, []);

  const desfazer = useCallback((tecnico: string, dia: string) => {
    setErro(null);
    setReordens((atuais) => atuais.filter((r) => !(r.tecnico === tecnico && r.dia === dia)));
  }, []);

  const registrar = useCallback(async (
    { tecnico, dia, motivo, quem, mudancas }:
    { tecnico: string; dia: string; motivo: string; quem: string; mudancas: Mudanca[] },
  ): Promise<boolean> => {
    if (!runId || mudancas.length === 0) return false;
    setGravando(true);
    setErro(null);
    try {
      const itens: FeedbackItem[] = mudancas.map((m) => ({
        operation_id: m.operation_id,
        skill: 'schedule',
        verdict: 'incorrect',
        reason: motivoDaReordenacao(m, hora, motivo.trim()),
      }));
      await api.feedback(runId, { recorded_by: quem.trim(), items: itens });
      salvarQuem(quem);
      setReordens((atuais) => atuais.map((r) => (
        r.tecnico === tecnico && r.dia === dia ? { ...r, registrada: true } : r
      )));
      return true;
    } catch (causa) {
      setErro(
        causa instanceof ApiError
          ? `A API recusou o registro (${causa.status}). A sequência continua só nesta tela.`
          : 'Não foi possível registrar a sequência. Ela continua só nesta tela.',
      );
      return false;
    } finally {
      setGravando(false);
    }
  }, [runId]);

  /**
   * A sequência recebe uma ordem que chegou por troca depois de ela ter sido
   * desenhada. Isto não é uma decisão nova: `registrada` fica como estava, ou a
   * tela pediria para registrar de novo uma sequência que a pessoa não mexeu.
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
    erro,
    limparErro: () => setErro(null),
    pendenteEm: (tecnico: string, dia: string) => {
      const r = reordenacaoDe(reordens, tecnico, dia);
      return !!r && !r.registrada;
    },
    schedule,
  };
}
