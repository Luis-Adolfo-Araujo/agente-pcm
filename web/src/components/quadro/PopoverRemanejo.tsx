'use client';
import { useEffect, useRef, useState } from 'react';
import { quemSalvo } from '@/lib/api';
import { escalaImpossivel, horas, rotuloDia } from '@/lib/semana';

export type DestinoDoDia = { worker_id: string; carga: number; escala: number };

/**
 * O que o movimento de dia pergunta: quem recebe, a que horas, quem está
 * movendo e por quê. O dia não é perguntado — ele é o chip onde o cartão caiu.
 *
 * A pessoa é perguntada quando o alvo do arraste foi um dia inteiro: mudar de
 * dia é mudar de contexto, e quem decide o dia costuma querer olhar para quem
 * também. Quando o alvo já foi a célula de uma pessoa, `pessoaFixa` cala essa
 * pergunta. A justificativa é opcional; o nome de quem move não é, porque a API
 * recusa feedback sem autor.
 */
export function PopoverRemanejo({
  deDia, paraDia, deTecnico, horaAtual, duracao, dividida, destinos, pessoaFixa,
  gravando, erro, onConfirmar, onCancelar,
}: {
  deDia: string;
  paraDia: string;
  deTecnico: string;
  /** Hora que a ordem já tinha, em HH:MM — o valor inicial do campo. */
  horaAtual: string;
  /** Minutos da ordem, para dizer o que ela faz com a escala de quem recebe. */
  duracao: number;
  /** A ordem tem mais de um executante e vai perder o segundo. */
  dividida: boolean;
  destinos: DestinoDoDia[];
  /**
   * A célula onde o cartão caiu já disse quem recebe. Na matriz semanal o
   * destino é o próprio alvo do arraste, então perguntar de novo seria mandar a
   * pessoa refazer o gesto que ela acabou de fazer.
   */
  pessoaFixa?: boolean;
  gravando: boolean;
  erro: string | null;
  onConfirmar: (paraTecnico: string, hhmm: string, quem: string, motivo: string) => void;
  onCancelar: () => void;
}) {
  const [para, setPara] = useState(
    destinos.some((d) => d.worker_id === deTecnico) ? deTecnico : destinos[0]?.worker_id ?? '',
  );
  const [hora, setHora] = useState(horaAtual);
  const [quem, setQuem] = useState(quemSalvo);
  const [motivo, setMotivo] = useState('');
  const primeiro = useRef<HTMLSelectElement>(null);
  const campoHora = useRef<HTMLInputElement>(null);

  // O arraste termina com o cursor longe do formulário, e o teclado chega aqui
  // sem ter clicado em nada: sem foco programático não há onde digitar. Com a
  // pessoa fixa não há select, e o primeiro campo passa a ser a hora.
  useEffect(() => { (primeiro.current ?? campoHora.current)?.focus(); }, []);

  const rotuloDestino = `${rotuloDia(paraDia).nome} ${rotuloDia(paraDia).numero}`;
  const rotuloOrigem = `${rotuloDia(deDia).nome} ${rotuloDia(deDia).numero}`;

  if (destinos.length === 0) {
    return (
      <div className="popover-remanejo" role="dialog" aria-label={`Mover para ${rotuloDestino}`}>
        <p className="popover-titulo">{rotuloOrigem} → {rotuloDestino}</p>
        <p className="popover-nota">
          Ninguém tem escala declarada em {rotuloDestino}. A ordem cairia num dia em que ninguém
          trabalha.
        </p>
        <div className="popover-acoes">
          <button type="button" className="btn btn-menor" onClick={onCancelar}>Cancelar</button>
        </div>
      </div>
    );
  }

  const alvo = destinos.find((d) => d.worker_id === para) ?? null;
  const depois = alvo ? alvo.carga + duracao : 0;
  const estoura = !!alvo && alvo.escala > 0 && depois > alvo.escala;
  const semEscala = !!alvo && alvo.escala === 0;

  return (
    <div
      className="popover-remanejo"
      role="dialog"
      aria-label={`Mover para ${rotuloDestino}`}
      onKeyDown={(event) => { if (event.key === 'Escape') onCancelar(); }}
    >
      <p className="popover-titulo">{rotuloOrigem} → <strong>{rotuloDestino}</strong></p>

      {pessoaFixa ? (
        <p className="popover-destino">
          Fica com <strong>{para}</strong>
          {alvo && (alvo.escala > 0
            ? ` · ${horas(alvo.carga)} de ${horas(alvo.escala)} no dia`
            : ' · sem escala no dia')}
        </p>
      ) : (
        <div className="field">
          <label htmlFor="remanejo-para">Quem recebe</label>
          <select
            id="remanejo-para"
            ref={primeiro}
            value={para}
            onChange={(e) => setPara(e.target.value)}
          >
            {destinos.map((d) => (
              <option key={d.worker_id} value={d.worker_id}>
                {d.worker_id}
                {d.escala > 0 ? ` · ${horas(d.carga)} de ${horas(d.escala)}` : ' · sem escala no dia'}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="field">
        <label htmlFor="remanejo-hora">Começa às</label>
        <input
          id="remanejo-hora"
          ref={campoHora}
          type="time"
          value={hora}
          onChange={(e) => setHora(e.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="remanejo-quem">Quem está movendo</label>
        <input
          id="remanejo-quem"
          value={quem}
          onChange={(e) => setQuem(e.target.value)}
          placeholder="seu nome"
        />
      </div>

      <div className="field">
        <label htmlFor="remanejo-motivo">
          Por que este dia <span className="field-opcional">opcional, mas é o que o agente aprende</span>
        </label>
        <input
          id="remanejo-motivo"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          placeholder="parada da linha só na quarta, material chega amanhã…"
        />
      </div>

      {alvo && (estoura || semEscala || escalaImpossivel(alvo.escala)) && (
        <div className="note" data-tone="bad">
          {semEscala && <>{alvo.worker_id} não tem escala declarada em {rotuloDestino}.</>}
          {estoura && (
            <>
              {alvo.worker_id} fica com {horas(depois)} num dia de {horas(alvo.escala)} de escala —
              {' '}{horas(depois - alvo.escala)} acima.
            </>
          )}
          {!estoura && !semEscala && escalaImpossivel(alvo.escala) && (
            <>A escala declarada de {alvo.worker_id} é de {horas(alvo.escala)}, que nenhuma jornada fecha.</>
          )}
        </div>
      )}

      {dividida && alvo && (
        <div className="note" data-tone="bad">
          Esta ordem tem mais de um executante; mover deixa ela com {alvo.worker_id}.
        </div>
      )}

      <p className="popover-nota">
        Isto não reescreve a proposta. Fica gravada a sua discordância com o encaixe — dia, hora
        e pessoa.
      </p>

      {erro && <div className="note" data-tone="bad">{erro}</div>}

      <div className="popover-acoes">
        <button type="button" className="btn btn-menor" onClick={onCancelar} disabled={gravando}>
          Cancelar
        </button>
        <button
          type="button"
          className="btn btn-menor btn-primary"
          disabled={gravando || !para || !hora || quem.trim().length === 0}
          onClick={() => onConfirmar(para, hora, quem, motivo)}
        >
          {gravando ? 'Registrando…' : `Mover para ${rotuloDestino}`}
        </button>
      </div>
    </div>
  );
}
