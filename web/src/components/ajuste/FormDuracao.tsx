'use client';
import type { Enriched } from '@/lib/api';
import { escreverHhmm, lerHhmm } from '@/lib/duracao';
import { FONTE } from '@/lib/rotulos';

/**
 * O tempo novo, com o de hoje e de onde ele veio ao lado. Quem corrige precisa
 * saber se está corrigindo o cadastro, uma estimativa do histórico ou um valor
 * assumido — são três conversas diferentes.
 */
export function FormDuracao({ item, antes, valor, onMudar }: {
  item: Enriched;
  /** O que o agente tinha estimado, se a duração já foi alterada por ajuste. */
  antes: number | null | undefined;
  valor: string;
  onMudar: (valor: string) => void;
}) {
  const d = item.duration;
  const invalido = valor.trim() !== '' && lerHhmm(valor) === null;
  const hoje = d.minutes === null ? 'sem duração' : escreverHhmm(d.minutes);

  return (
    <>
      <div className="field">
        <label htmlFor="duracao-nova">Tempo previsto <span className="field-opcional">h:mm</span></label>
        <input
          id="duracao-nova"
          inputMode="numeric"
          placeholder="1:30"
          value={valor}
          aria-invalid={invalido || undefined}
          onChange={(e) => onMudar(e.target.value)}
        />
      </div>
      <p className="duracao-fonte">
        Hoje: <strong>{hoje}</strong>
        {antes !== undefined
          ? ` · alterada por ajuste; o agente estimou ${antes === null ? 'sem duração' : escreverHhmm(antes)}`
          : ` · ${FONTE[d.source] ?? d.source}`}
        {antes === undefined && d.sample_size > 1 && ` · ${d.sample_size} execuções`}
        {antes === undefined && d.p50_minutes !== null && d.p80_minutes !== null
          && ` · p50 ${escreverHhmm(d.p50_minutes)}, p80 ${escreverHhmm(d.p80_minutes)}`}
      </p>
      {antes === undefined && d.source === 'planned' && (
        <p className="note">
          Esta duração veio do cadastro da OS. Alterar aqui muda a semana e ensina o agente; a Tractian
          não é atualizada.
        </p>
      )}
      {invalido && (
        <p className="note" data-tone="bad">Use horas e minutos, como 1:30. O máximo é 24:00.</p>
      )}
    </>
  );
}
