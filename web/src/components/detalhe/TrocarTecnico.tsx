'use client';
import { useState } from 'react';
import { quemSalvo } from '@/lib/api';
import { escalaImpossivel, horas } from '@/lib/semana';
import type { Pedido } from '@/components/sessao/useTrocas';

export type Destino = {
  worker_id: string;
  score: number | null;
  eligible: boolean | null;
  carga: number;
  escala: number;
};

/**
 * Passar a ordem para outra pessoa é uma discordância registrada, não uma edição
 * da proposta. O motivo é recomendado, não obrigatório: exigi-lo fazia a pessoa
 * inventar texto para destravar o botão, e texto inventado ensina o golden set
 * pior que silêncio. O movimento — de quem para quem — é registrado sempre, e é
 * ele que cumpre o mínimo que a API exige no `reason`.
 */
export function TrocarTecnico({ de, duracao, destinos, inicial, gravando, erro, onConfirmar, onCancelar }: {
  de: string;
  /** Minutos da ordem, para dizer o que ela faz com a escala de quem recebe. */
  duracao: number;
  destinos: Destino[];
  /** Quem você clicou na tabela de candidatos. */
  inicial?: string;
  gravando: boolean;
  erro: string | null;
  onConfirmar: (pedido: Omit<Pedido, 'operation_id'>) => void;
  onCancelar: () => void;
}) {
  const [para, setPara] = useState(
    inicial && destinos.some((d) => d.worker_id === inicial) ? inicial : destinos[0]?.worker_id ?? '',
  );
  const [motivo, setMotivo] = useState('');
  const [quem, setQuem] = useState(quemSalvo());

  const alvo = destinos.find((d) => d.worker_id === para) ?? null;
  const depois = alvo ? alvo.carga + duracao : 0;
  const estoura = !!alvo && alvo.escala > 0 && depois > alvo.escala;
  const semEscala = !!alvo && alvo.escala === 0;
  const pronto = !!para && quem.trim().length > 0 && !gravando;

  if (destinos.length === 0) {
    return (
      <div className="troca">
        <p className="muted" style={{ marginTop: 0 }}>
          Ninguém mais tem escala declarada neste dia. Não há para quem passar esta ordem.
        </p>
        <div className="troca-acoes">
          <button type="button" className="btn" onClick={onCancelar}>Voltar para a ordem</button>
        </div>
      </div>
    );
  }

  return (
    <div className="troca">
      <p className="muted" style={{ marginTop: 0 }}>
        Hoje ela é de <strong>{de}</strong>. Quem recebe, e por quê.
      </p>

      <div className="troca-campos">
        <div className="field">
          <label htmlFor="troca-para">Quem recebe</label>
          <select id="troca-para" value={para} onChange={(e) => setPara(e.target.value)}>
            {destinos.map((d) => (
              <option key={d.worker_id} value={d.worker_id}>
                {d.worker_id}
                {d.score !== null ? ` · score ${d.score.toFixed(0)}` : ' · não avaliado'}
                {d.eligible === false ? ' · inelegível' : ''}
                {d.escala > 0 ? ` · ${horas(d.carga)} de ${horas(d.escala)}` : ' · sem escala no dia'}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="troca-quem">Quem está passando</label>
          <input
            id="troca-quem"
            value={quem}
            onChange={(e) => setQuem(e.target.value)}
            placeholder="seu nome"
          />
        </div>
      </div>

      <div className="field" style={{ marginTop: 'var(--space-md)' }}>
        <label htmlFor="troca-motivo">
          Por que esta pessoa e não a que o agente escolheu{' '}
          <span className="field-opcional">opcional, mas é o que o agente aprende</span>
        </label>
        <textarea
          id="troca-motivo"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          placeholder="conhece o equipamento, já está na área, certificação exigida…"
        />
      </div>

      {alvo && (estoura || semEscala || escalaImpossivel(alvo.escala)) && (
        <div className="note" data-tone="bad" style={{ marginTop: 'var(--space-md)' }}>
          {semEscala && <>{alvo.worker_id} não tem escala declarada neste dia.</>}
          {estoura && (
            <>
              {alvo.worker_id} fica com {horas(depois)} num dia de {horas(alvo.escala)} de escala —
              {' '}{horas(depois - alvo.escala)} acima.
            </>
          )}
          {!estoura && !semEscala && escalaImpossivel(alvo.escala) && (
            <>A escala declarada de {alvo.worker_id} é de {horas(alvo.escala)}, que nenhuma jornada fecha.</>
          )}
          {' '}A troca é registrada mesmo assim; a conferência dura continua valendo sobre a proposta do agente.
        </div>
      )}

      <div className="note" style={{ marginTop: 'var(--space-md)' }}>
        Isto <strong>não reescreve a proposta</strong>. O que fica gravado é a sua discordância —
        ordem, de quem para quem e por quê — e é dela que o agente aprende. A tela passa a mostrar
        a semana com a sua troca por cima, até você recarregar.
      </div>

      {erro && <div className="note" data-tone="bad" style={{ marginTop: 'var(--space-md)' }}>{erro}</div>}

      <div className="troca-acoes">
        <button type="button" className="btn" onClick={onCancelar} disabled={gravando}>Cancelar</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!pronto}
          onClick={() => onConfirmar({ de, para, motivo, quem })}
        >
          {gravando ? 'Registrando…' : `Passar para ${para}`}
        </button>
      </div>
    </div>
  );
}
