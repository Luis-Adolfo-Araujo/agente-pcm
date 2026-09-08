'use client';
import type { ReactNode } from 'react';
import { CartaoOrdem } from '@/components/quadro/CartaoOrdem';
import type { CelulaSemana } from '@/lib/matriz';
import { horas, rotuloDia } from '@/lib/semana';

/** Inteiro na célula; a casa decimal fica para o agregado do cabeçalho. */
function porcento(ocupacao: number): string {
  return `${Math.round(ocupacao)}%`;
}

/**
 * O dia de uma pessoa, visto de cima: uma barra de ocupação e o número dela.
 *
 * O número acompanha a barra em todos os estados porque a cor sozinha não pode
 * carregar a informação — e porque "sem escala" e "0%" são coisas diferentes que
 * o mesmo trilho vazio desenharia igual.
 */
export function CelulaDia({
  celula, tecnico, aberta, recebendo, arrastando, titulos, inicioOriginal,
  trocadas, movidas, ativa, popover,
  onAbrirDia, onAbrirOrdem, onArrastarInicio, onArrastarFim, onMirar, onSair, onSoltar,
}: {
  celula: CelulaSemana;
  tecnico: string;
  /** A linha está expandida, então os cartões aparecem. */
  aberta: boolean;
  /** Um cartão de outra célula está pairando aqui. */
  recebendo: boolean;
  /** A ordem que está no ar, para o cartão de origem apagar. */
  arrastando: string | null;
  titulos: Map<string, string>;
  inicioOriginal: Map<string, string>;
  trocadas: Set<string>;
  movidas: Set<string>;
  ativa: string | null;
  /** O pedido que caiu nesta célula e ainda espera quem e por quê. */
  popover: ReactNode;
  onAbrirDia: () => void;
  onAbrirOrdem: (operationId: string) => void;
  onArrastarInicio: (operationId: string, posicao: number) => void;
  onArrastarFim: () => void;
  onMirar: () => void;
  onSair: () => void;
  onSoltar: () => void;
}) {
  const rotulo = rotuloDia(celula.dia);
  const semEscala = celula.escala === 0;
  const preenchimento = celula.ocupacao === null
    ? (celula.minutos > 0 ? 100 : 0)
    : Math.min(100, celula.ocupacao);

  const numero = celula.ocupacao === null ? 'sem escala' : porcento(celula.ocupacao);
  const detalhe = semEscala
    ? `${horas(celula.minutos)} alocadas sem escala declarada`
    : `${horas(celula.minutos)} de ${horas(celula.escala)} de escala`;

  return (
    <td
      className="matriz-celula"
      data-estado={celula.estado}
      data-alvo={recebendo ? 'sim' : undefined}
      onDragOver={(event) => {
        if (!arrastando) return;
        event.preventDefault();
        onMirar();
      }}
      onDragLeave={onSair}
      onDrop={(event) => {
        if (!arrastando) return;
        event.preventDefault();
        onSoltar();
      }}
    >
      <button
        type="button"
        className="celula-medida"
        onClick={onAbrirDia}
        aria-label={`${tecnico}, ${rotulo.nome} ${rotulo.numero}: ${numero}, ${detalhe}. Abrir o quadro deste dia.`}
        title={detalhe}
      >
        <span className="ocupacao" aria-hidden="true">
          <i style={{ width: `${preenchimento}%` }} />
        </span>
        <span className="ocupacao-num">{numero}</span>
      </button>

      {popover}

      {aberta && celula.ordens.length > 0 && (
        <div className="celula-cartoes">
          {celula.ordens.map((ordem, i) => (
            <div
              key={`${tecnico}-${ordem.operation_id}`}
              className="cartao-slot"
              draggable
              data-arrastando={arrastando === ordem.operation_id ? 'sim' : undefined}
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = 'move';
                // O Firefox não inicia o arraste sem carga no dataTransfer.
                event.dataTransfer.setData('text/plain', ordem.operation_id);
                onArrastarInicio(ordem.operation_id, i);
              }}
              onDragEnd={onArrastarFim}
            >
              <CartaoOrdem
                ordem={ordem}
                titulo={titulos.get(ordem.operation_id) ?? ''}
                original={inicioOriginal.get(ordem.operation_id)}
                trocada={trocadas.has(ordem.operation_id)}
                movida={movidas.has(ordem.operation_id)}
                dividida={ordem.worker_ids.length > 1}
                ativa={ordem.operation_id === ativa}
                onAbrir={() => onAbrirOrdem(ordem.operation_id)}
                onTeclado={() => {}}
              />
            </div>
          ))}
        </div>
      )}

      {aberta && celula.ordens.length === 0 && (
        <p className="celula-vazia">{semEscala ? 'sem escala' : 'livre'}</p>
      )}
    </td>
  );
}
