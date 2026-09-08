'use client';
import type { KeyboardEvent, ReactNode } from 'react';
import { CartaoOrdem } from '@/components/quadro/CartaoOrdem';
import { horas } from '@/lib/semana';
import type { Coluna } from '@/lib/quadro';
import type { Remanejo } from '@/lib/remanejos';
import type { Troca } from '@/lib/trocas';

export type Arraste = { operationId: string; tecnico: string; posicao: number };
export type AlvoArraste = { tecnico: string; posicao: number | null };

/**
 * O dia de uma pessoa, de cima para baixo. O cabeçalho fica parado enquanto a
 * coluna rola: é ele que diz se o que está caindo ali cabe na escala dela.
 *
 * O realce ensina a regra do arraste. Na coluna de origem aparece a linha de
 * inserção, porque ali a posição é a decisão; numa coluna estranha acende a
 * coluna inteira, porque a troca não mexe no horário e a posição não conta.
 */
export function ColunaTecnico({
  coluna, titulos, trocas, remanejos, inicioOriginal, ativa, arraste, alvo, popover,
  onAbrirOrdem, onArrastarInicio, onArrastarSobre, onSoltar, onArrastarFim, onTeclado,
}: {
  coluna: Coluna;
  titulos: Map<string, string>;
  trocas: Troca[];
  remanejos: Remanejo[];
  /** Horário que cada ordem tinha antes de a sequência do dia ser remexida. */
  inicioOriginal: Map<string, string>;
  /** A ordem aberta no modal, para o cartão dela ficar marcado. */
  ativa: string | null;
  arraste: Arraste | null;
  alvo: AlvoArraste | null;
  /** A troca que caiu nesta coluna e ainda espera quem e por quê. */
  popover: ReactNode;
  onAbrirOrdem: (operationId: string) => void;
  onArrastarInicio: (operationId: string, posicao: number) => void;
  onArrastarSobre: (posicao: number | null) => void;
  onSoltar: (posicao: number | null) => void;
  onArrastarFim: () => void;
  onTeclado: (operationId: string, posicao: number, event: KeyboardEvent) => void;
}) {
  const recebidas = new Set(trocas.map((t) => t.operation_id));
  const vindasDeOutroDia = new Set(remanejos.map((r) => r.operation_id));
  const preenchimento = coluna.escala > 0
    ? Math.min(100, (coluna.minutos / coluna.escala) * 100)
    : 100;
  const daCasa = arraste?.tecnico === coluna.tecnico;
  const recebendo = !!arraste && !daCasa && alvo?.tecnico === coluna.tecnico;

  return (
    <section
      className="coluna"
      data-alvo={recebendo ? 'sim' : undefined}
      aria-label={`Dia de ${coluna.tecnico}`}
      onDragOver={(event) => {
        if (!arraste) return;
        event.preventDefault();
        onArrastarSobre(null);
      }}
      onDrop={(event) => {
        if (!arraste) return;
        event.preventDefault();
        onSoltar(null);
      }}
    >
      <header className="coluna-cabeca">
        <div className="coluna-nome">{coluna.tecnico}</div>
        <span className="carga" data-estourou={coluna.estourou ? 'sim' : undefined} aria-hidden="true">
          <i style={{ width: `${preenchimento}%` }} />
        </span>
        <div className="coluna-carga">
          {coluna.escala > 0
            ? `${horas(coluna.minutos)} de ${horas(coluna.escala)} de escala`
            : `${horas(coluna.minutos)} alocadas · sem escala declarada`}
          {' · '}{coluna.ordens.length} {coluna.ordens.length === 1 ? 'ordem' : 'ordens'}
        </div>
        {(coluna.impossivel || coluna.estourou || coluna.trocadas > 0 || coluna.movidas > 0) && (
          <div className="coluna-marcas">
            {coluna.impossivel && (
              <span className="badge" data-tone="bad">escala de {horas(coluna.escala)}</span>
            )}
            {coluna.estourou && <span className="badge" data-tone="bad">acima da escala</span>}
            {coluna.movidas > 0 && (
              <span className="badge" data-tone="warn">{coluna.movidas} de outro dia</span>
            )}
            {coluna.trocadas > 0 && (
              <span className="badge" data-tone="warn">
                {coluna.trocadas} {coluna.trocadas === 1 ? 'troca' : 'trocas'}
              </span>
            )}
          </div>
        )}
      </header>

      {popover}

      <div className="coluna-corpo">
        {coluna.ordens.length === 0 ? (
          <p className="coluna-vazia">
            {coluna.escala > 0 ? 'Nada alocado. Arraste uma ordem para cá.' : 'Nada alocado neste dia.'}
          </p>
        ) : (
          coluna.ordens.map((ordem, i) => (
            <div
              key={`${coluna.tecnico}-${ordem.operation_id}`}
              className="cartao-slot"
              draggable
              data-arrastando={
                arraste?.operationId === ordem.operation_id && daCasa ? 'sim' : undefined
              }
              data-insercao={daCasa && alvo?.tecnico === coluna.tecnico && alvo.posicao === i ? 'sim' : undefined}
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = 'move';
                // O Firefox não inicia o arraste sem carga no dataTransfer.
                event.dataTransfer.setData('text/plain', ordem.operation_id);
                onArrastarInicio(ordem.operation_id, i);
              }}
              onDragOver={(event) => {
                if (!arraste) return;
                event.preventDefault();
                event.stopPropagation();
                onArrastarSobre(i);
              }}
              onDrop={(event) => {
                if (!arraste) return;
                event.preventDefault();
                event.stopPropagation();
                onSoltar(i);
              }}
              onDragEnd={onArrastarFim}
            >
              <CartaoOrdem
                ordem={ordem}
                titulo={titulos.get(ordem.operation_id) ?? ''}
                original={inicioOriginal.get(ordem.operation_id)}
                trocada={recebidas.has(ordem.operation_id)}
                movida={vindasDeOutroDia.has(ordem.operation_id)}
                dividida={ordem.worker_ids.length > 1}
                ativa={ordem.operation_id === ativa}
                onAbrir={() => onAbrirOrdem(ordem.operation_id)}
                onTeclado={(event) => onTeclado(ordem.operation_id, i, event)}
              />
            </div>
          ))
        )}
      </div>
    </section>
  );
}
