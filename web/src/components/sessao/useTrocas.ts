'use client';
import { useCallback, useMemo, useState } from 'react';
import { ApiError, api, salvarQuem } from '@/lib/api';
import { aplicarTrocas, motivoDoFeedback, type Troca } from '@/lib/trocas';
import type { Schedule } from '@/lib/api';

export type Pedido = { operation_id: string; de: string; para: string; motivo: string; quem: string };

/**
 * A troca só repinta a tela depois que o feedback está gravado. A ordem importa:
 * repintar primeiro e gravar depois deixaria a tela afirmando uma coisa que o
 * banco não tem — que é exatamente o defeito que este piloto existe para não ter.
 */
export function useTrocas(runId: string | null, schedule: Schedule | null) {
  const [trocas, setTrocas] = useState<Troca[]>([]);
  const [gravando, setGravando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const trocar = useCallback(async (pedido: Pedido): Promise<boolean> => {
    if (!runId) return false;
    setGravando(true);
    setErro(null);
    try {
      await api.feedback(runId, {
        recorded_by: pedido.quem.trim(),
        items: [{
          operation_id: pedido.operation_id,
          skill: 'executants',
          verdict: 'incorrect',
          reason: motivoDoFeedback(pedido),
        }],
      });
      salvarQuem(pedido.quem);
      setTrocas((atuais) => [
        ...atuais.filter((t) => t.operation_id !== pedido.operation_id),
        {
          operation_id: pedido.operation_id,
          de: pedido.de,
          para: pedido.para,
          motivo: pedido.motivo.trim(),
          em: new Date().toISOString(),
        },
      ]);
      return true;
    } catch (causa) {
      setErro(
        causa instanceof ApiError
          ? `A API recusou o registro (${causa.status}). A troca não foi feita.`
          : 'Não foi possível registrar a troca. Nada mudou.',
      );
      return false;
    } finally {
      setGravando(false);
    }
  }, [runId]);

  const efetivo = useMemo(
    () => (schedule ? aplicarTrocas(schedule, trocas) : null),
    [schedule, trocas],
  );

  return { trocas, efetivo, trocar, gravando, erro, limparErro: () => setErro(null) };
}
