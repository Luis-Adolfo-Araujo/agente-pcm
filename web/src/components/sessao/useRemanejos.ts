'use client';
import { useCallback, useMemo, useState } from 'react';
import { ApiError, api, salvarQuem, type Schedule } from '@/lib/api';
import { aplicarRemanejos, motivoDoRemanejo, type Remanejo } from '@/lib/remanejos';

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

/**
 * Mover de dia é uma discordância só — a do encaixe — mesmo quando a pessoa muda
 * junto: quem recebe no dia novo é consequência do dia, não erro de escolha de
 * executante. Gravar também um `executants` ensinaria o agente a desconfiar de
 * uma escolha que estava certa para o dia original.
 *
 * Como a troca, o movimento só repinta a tela depois de gravado.
 */
export function useRemanejos(runId: string | null, schedule: Schedule | null) {
  const [remanejos, setRemanejos] = useState<Remanejo[]>([]);
  const [gravando, setGravando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const remanejar = useCallback(async (pedido: PedidoDeRemanejo): Promise<boolean> => {
    if (!runId) return false;
    setGravando(true);
    setErro(null);
    try {
      await api.feedback(runId, {
        recorded_by: pedido.quem.trim(),
        items: [{
          operation_id: pedido.operation_id,
          skill: 'schedule',
          verdict: 'incorrect',
          reason: motivoDoRemanejo(pedido),
        }],
      });
      salvarQuem(pedido.quem);
      // Um remanejo por ordem: mover a mesma duas vezes substitui o de antes. O
      // histórico completo fica na API, que é quem tem memória.
      setRemanejos((atuais) => [
        ...atuais.filter((r) => r.operation_id !== pedido.operation_id),
        {
          operation_id: pedido.operation_id,
          deDia: pedido.deDia,
          deInicio: pedido.deInicio,
          deTecnico: pedido.deTecnico,
          paraDia: pedido.paraDia,
          paraInicio: pedido.paraInicio,
          paraTecnico: pedido.paraTecnico,
          motivo: pedido.motivo.trim(),
          em: new Date().toISOString(),
        },
      ]);
      return true;
    } catch (causa) {
      setErro(
        causa instanceof ApiError
          ? `A API recusou o registro (${causa.status}). A ordem não mudou de dia.`
          : 'Não foi possível registrar o movimento. Nada mudou.',
      );
      return false;
    } finally {
      setGravando(false);
    }
  }, [runId]);

  const efetivo = useMemo(
    () => (schedule ? aplicarRemanejos(schedule, remanejos) : null),
    [schedule, remanejos],
  );

  return { remanejos, efetivo, remanejar, gravando, erro, limparErro: () => setErro(null) };
}
