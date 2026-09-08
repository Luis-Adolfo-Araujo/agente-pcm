'use client';
import type { ReactNode } from 'react';
import { CelulaDia } from '@/components/semana/CelulaDia';
import { ordensVisiveis, type LinhaSemana } from '@/lib/matriz';
import { horas } from '@/lib/semana';

/**
 * Uma pessoa, a semana inteira dela.
 *
 * O cabeçalho da linha carrega a ocupação da semana — soma das cargas sobre soma
 * das escalas, e não a média das células: uma pessoa com oito horas de escala na
 * segunda e quatro na terça não pode ter os dois dias pesando igual.
 */
export function LinhaExecutante({
  linha, aberta, alvo, arrastando, titulos, inicioOriginal, trocadas, movidas, ativa, popoverEm,
  onAlternar, onAbrirDia, onAbrirOrdem, onArrastarInicio, onArrastarFim, onMirar, onSair, onSoltar,
}: {
  linha: LinhaSemana;
  aberta: boolean;
  /** A célula sob o cursor durante o arraste, se for desta linha. */
  alvo: string | null;
  arrastando: string | null;
  titulos: Map<string, string>;
  inicioOriginal: Map<string, string>;
  trocadas: Set<string>;
  movidas: Set<string>;
  ativa: string | null;
  /** O dia cuja célula está com o popover aberto, e o popover. */
  popoverEm: { dia: string; conteudo: ReactNode } | null;
  onAlternar: () => void;
  onAbrirDia: (dia: string) => void;
  onAbrirOrdem: (operationId: string) => void;
  onArrastarInicio: (operationId: string, posicao: number) => void;
  onArrastarFim: () => void;
  onMirar: (dia: string) => void;
  onSair: (dia: string) => void;
  onSoltar: (dia: string) => void;
}) {
  const visiveis = ordensVisiveis(linha);
  const semanaVazia = linha.escala === 0;
  const preenchimento = linha.ocupacao === null
    ? (linha.minutos > 0 ? 100 : 0)
    : Math.min(100, linha.ocupacao);
  const numero = linha.ocupacao === null ? 'sem escala' : `${Math.round(linha.ocupacao)}%`;

  return (
    <tr className="matriz-linha" data-aberta={aberta ? 'sim' : undefined}>
      <th scope="row" className="matriz-pessoa">
        <button
          type="button"
          className="pessoa-abrir"
          aria-expanded={aberta}
          onClick={onAlternar}
        >
          <svg className="pessoa-chevron" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M2 3.5 5 6.5 8 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="pessoa-nome">{linha.tecnico}</span>
        </button>
        <div className="pessoa-semana" data-estourou={linha.estourou ? 'sim' : undefined}>
          <span className="ocupacao" aria-hidden="true"><i style={{ width: `${preenchimento}%` }} /></span>
          <span className="ocupacao-num">{numero}</span>
        </div>
        <div className="pessoa-nota">
          {semanaVazia
            ? `${horas(linha.minutos)} sem escala declarada`
            : `${horas(linha.minutos)} de ${horas(linha.escala)}`}
          {' · '}
          {visiveis} {visiveis === 1 ? 'ordem' : 'ordens'}
        </div>
      </th>

      {linha.celulas.map((celula) => (
        <CelulaDia
          key={celula.dia}
          celula={celula}
          tecnico={linha.tecnico}
          aberta={aberta}
          recebendo={alvo === celula.dia}
          arrastando={arrastando}
          titulos={titulos}
          inicioOriginal={inicioOriginal}
          trocadas={trocadas}
          movidas={movidas}
          ativa={ativa}
          popover={popoverEm?.dia === celula.dia ? popoverEm.conteudo : null}
          onAbrirDia={() => onAbrirDia(celula.dia)}
          onAbrirOrdem={onAbrirOrdem}
          onArrastarInicio={onArrastarInicio}
          onArrastarFim={onArrastarFim}
          onMirar={() => onMirar(celula.dia)}
          onSair={() => onSair(celula.dia)}
          onSoltar={() => onSoltar(celula.dia)}
        />
      ))}
    </tr>
  );
}
