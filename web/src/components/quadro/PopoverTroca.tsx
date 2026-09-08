'use client';
import { useEffect, useRef, useState } from 'react';
import { quemSalvo } from '@/lib/api';
import { escalaImpossivel, horas } from '@/lib/semana';

/**
 * O que a troca pergunta na hora em que ela acontece: quem está passando, e por
 * quê. O destino não é perguntado — ele é a coluna onde o cartão caiu.
 *
 * O motivo é recomendado, não obrigatório: exigi-lo faria a pessoa inventar
 * texto para destravar o botão. O nome é obrigatório porque a API recusa
 * feedback sem autor.
 */
export function PopoverTroca({
  de, para, duracao, cargaDestino, escalaDestino, gravando, erro, onConfirmar, onCancelar,
}: {
  de: string;
  para: string;
  /** Minutos da ordem, para dizer o que ela faz com a escala de quem recebe. */
  duracao: number;
  cargaDestino: number;
  escalaDestino: number;
  gravando: boolean;
  erro: string | null;
  onConfirmar: (quem: string, motivo: string) => void;
  onCancelar: () => void;
}) {
  const [quem, setQuem] = useState(quemSalvo);
  const [motivo, setMotivo] = useState('');
  const primeiro = useRef<HTMLInputElement>(null);

  // O arraste termina com o cursor longe do formulário, e o teclado chega aqui
  // sem ter clicado em nada: sem foco programático, não haveria onde digitar.
  useEffect(() => { primeiro.current?.focus(); }, []);

  const depois = cargaDestino + duracao;
  const estoura = escalaDestino > 0 && depois > escalaDestino;
  const semEscala = escalaDestino === 0;

  return (
    <div
      className="popover-troca"
      role="dialog"
      aria-label={`Passar de ${de} para ${para}`}
      onKeyDown={(event) => { if (event.key === 'Escape') onCancelar(); }}
    >
      <p className="popover-titulo">
        <strong>{de}</strong> → <strong>{para}</strong>
      </p>

      <div className="field">
        <label htmlFor="popover-quem">Quem está passando</label>
        <input
          id="popover-quem"
          ref={primeiro}
          value={quem}
          onChange={(e) => setQuem(e.target.value)}
          placeholder="seu nome"
        />
      </div>

      <div className="field">
        <label htmlFor="popover-motivo">
          Por que esta pessoa <span className="field-opcional">opcional, mas é o que o agente aprende</span>
        </label>
        <input
          id="popover-motivo"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          placeholder="conhece o equipamento, já está na área…"
        />
      </div>

      {(estoura || semEscala || escalaImpossivel(escalaDestino)) && (
        <div className="note" data-tone="bad">
          {semEscala && <>{para} não tem escala declarada neste dia.</>}
          {estoura && (
            <>
              {para} fica com {horas(depois)} num dia de {horas(escalaDestino)} de escala —
              {' '}{horas(depois - escalaDestino)} acima.
            </>
          )}
          {!estoura && !semEscala && escalaImpossivel(escalaDestino) && (
            <>A escala declarada de {para} é de {horas(escalaDestino)}, que nenhuma jornada fecha.</>
          )}
        </div>
      )}

      <p className="popover-nota">
        A ordem mantém o horário dela e entra pelo relógio. Para mudar a posição, arraste dentro
        da coluna. Isto não reescreve a proposta: grava a sua discordância.
      </p>

      {erro && <div className="note" data-tone="bad">{erro}</div>}

      <div className="popover-acoes">
        <button type="button" className="btn btn-menor" onClick={onCancelar} disabled={gravando}>
          Cancelar
        </button>
        <button
          type="button"
          className="btn btn-menor btn-primary"
          disabled={gravando || quem.trim().length === 0}
          onClick={() => onConfirmar(quem, motivo)}
        >
          {gravando ? 'Registrando…' : `Passar para ${para}`}
        </button>
      </div>
    </div>
  );
}
