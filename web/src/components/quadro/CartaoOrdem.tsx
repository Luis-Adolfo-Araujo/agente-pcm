'use client';
import type { KeyboardEvent } from 'react';
import { hora, type Assignment } from '@/lib/api';
import { horas, minutosDe } from '@/lib/semana';

/**
 * Uma ordem no dia de uma pessoa. O cartão carrega o que decide um remanejamento
 * — quando, o que é, quanto dura e o quanto o agente priorizou — porque quem
 * arrasta precisa disso na mão, não atrás de um clique.
 */
export function CartaoOrdem({
  ordem, titulo, original, trocada, movida, dividida, ativa, onAbrir, onTeclado,
}: {
  ordem: Assignment;
  titulo: string;
  /** Horário que a ordem tinha antes de a sequência ser remexida, se mudou. */
  original?: string;
  /** Veio de uma troca desta sessão. */
  trocada: boolean;
  /** Chegou de outro dia, por um movimento desta sessão. */
  movida: boolean;
  /** Tem mais de um executante, então aparece em mais de uma coluna. */
  dividida: boolean;
  ativa: boolean;
  onAbrir: () => void;
  onTeclado: (event: KeyboardEvent) => void;
}) {
  const mudouDeHora = !!original && original !== ordem.window.start;

  return (
    <button
      type="button"
      className="cartao"
      data-ativa={ativa ? 'sim' : undefined}
      aria-current={ativa ? 'true' : undefined}
      aria-label={
        `${titulo || ordem.work_order_id}, ${hora(ordem.window.start)} às ${hora(ordem.window.end)}. `
        + 'Alt com as setas move na coluna; Alt com as setas laterais passa para a pessoa ao lado.'
      }
      onClick={onAbrir}
      onKeyDown={onTeclado}
    >
      <span className="cartao-hora">
        {hora(ordem.window.start)}–{hora(ordem.window.end)}
        {mudouDeHora && <span className="cartao-antes">era {hora(original!)}</span>}
      </span>
      <span className="cartao-titulo">{titulo || '—'}</span>
      <span className="cartao-rodape">
        <span className="cartao-os" title={ordem.work_order_id}>{ordem.work_order_id.slice(-6)}</span>
        <span>{horas(minutosDe(ordem))}</span>
        {trocada && <span className="badge" data-tone="warn">trocada</span>}
        {movida && <span className="badge" data-tone="warn">movida</span>}
        {dividida && <span className="badge" data-tone="mute">dividida</span>}
        <span className="cartao-score" title="score de prioridade">{ordem.priority_score.toFixed(0)}</span>
      </span>
    </button>
  );
}
