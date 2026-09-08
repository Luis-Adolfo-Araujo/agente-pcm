'use client';
import { useState } from 'react';
import type { AlvoArraste, Arraste } from '@/components/quadro/ColunaTecnico';

/**
 * O arraste em curso. Ele mora aqui, e não dentro do quadro, porque o trilho de
 * dias também é alvo: os dois precisam enxergar o mesmo cartão no ar.
 */
export function useArraste() {
  const [arraste, setArraste] = useState<Arraste | null>(null);
  const [alvo, setAlvo] = useState<AlvoArraste | null>(null);

  return {
    arraste,
    alvo,
    comecar: (operationId: string, tecnico: string, posicao: number) => {
      setArraste({ operationId, tecnico, posicao });
    },
    mirar: (tecnico: string, posicao: number | null) => setAlvo({ tecnico, posicao }),
    terminar: () => { setArraste(null); setAlvo(null); },
  };
}
