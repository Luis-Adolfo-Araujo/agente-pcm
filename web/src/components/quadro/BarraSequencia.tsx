'use client';
import { useState } from 'react';
import { quemSalvo } from '@/lib/api';
import type { Mudanca } from '@/lib/reordenar';

export type Pendencia = {
  tecnico: string;
  /** As ordens que a pessoa de fato tirou do lugar. */
  decididas: Mudanca[];
  /** As que só andaram de horário porque o dia foi reempacotado. */
  empurradas: number;
};

/**
 * A sequência de um dia é várias arrastadas até ficar boa, não uma decisão por
 * movimento — por isso ela se acumula aqui embaixo e é registrada de uma vez.
 * Cada coluna pendente tem a sua linha: registrar a de uma pessoa não pode
 * gravar a discordância sobre o dia de outra.
 */
export function BarraSequencia({ pendencias, gravando, erro, onRegistrar, onDesfazer }: {
  pendencias: Pendencia[];
  gravando: boolean;
  erro: string | null;
  onRegistrar: (tecnico: string, quem: string, motivo: string) => void;
  onDesfazer: (tecnico: string) => void;
}) {
  if (pendencias.length === 0) return null;

  return (
    <div className="quadro-rodape">
      {erro && <div className="note" data-tone="bad">{erro}</div>}
      {pendencias.map((pendencia) => (
        <LinhaPendencia
          key={pendencia.tecnico}
          pendencia={pendencia}
          gravando={gravando}
          onRegistrar={onRegistrar}
          onDesfazer={onDesfazer}
        />
      ))}
    </div>
  );
}

function LinhaPendencia({ pendencia, gravando, onRegistrar, onDesfazer }: {
  pendencia: Pendencia;
  gravando: boolean;
  onRegistrar: (tecnico: string, quem: string, motivo: string) => void;
  onDesfazer: (tecnico: string) => void;
}) {
  const [quem, setQuem] = useState(quemSalvo);
  const [motivo, setMotivo] = useState('');
  const quantas = pendencia.decididas.length;

  return (
    <div className="pendencia">
      <div className="pendencia-resumo">
        <strong>{pendencia.tecnico}</strong> · {quantas}{' '}
        {quantas === 1 ? 'ordem mudou' : 'ordens mudaram'} de posição
        {pendencia.empurradas > 0 && (
          <>; o horário de {pendencia.empurradas}{' '}
          {pendencia.empurradas === 1 ? 'outra' : 'outras'} andou junto</>
        )} e os intervalos sumiram. Não reescreve a proposta: grava a sequência que você quer.
      </div>
      <div className="pendencia-campos">
        <div className="field">
          <label htmlFor={`seq-quem-${pendencia.tecnico}`}>Quem está reordenando</label>
          <input
            id={`seq-quem-${pendencia.tecnico}`}
            value={quem}
            onChange={(e) => setQuem(e.target.value)}
            placeholder="seu nome"
          />
        </div>
        <div className="field">
          <label htmlFor={`seq-motivo-${pendencia.tecnico}`}>
            Por que esta sequência <span className="field-opcional">opcional</span>
          </label>
          <input
            id={`seq-motivo-${pendencia.tecnico}`}
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="a parada da linha é de manhã, o material só chega à tarde…"
          />
        </div>
        <button
          type="button"
          className="btn"
          disabled={gravando}
          onClick={() => onDesfazer(pendencia.tecnico)}
        >
          Desfazer
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={gravando || quem.trim().length === 0}
          onClick={() => onRegistrar(pendencia.tecnico, quem, motivo)}
        >
          {gravando ? 'Registrando…' : 'Registrar a sequência'}
        </button>
      </div>
    </div>
  );
}
