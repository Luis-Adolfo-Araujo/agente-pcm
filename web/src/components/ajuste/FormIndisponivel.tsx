'use client';
import type { Causa } from '@/lib/api';
import { CAUSA } from '@/lib/rotulos';

export type RascunhoIndisponivel = { de: string; ate: string; causa: Causa | '' };

/** De quando a quando, e por quê. Os dias ficam presos ao período da semana. */
export function FormIndisponivel({ dias, valor, onMudar }: {
  dias: string[];
  valor: RascunhoIndisponivel;
  onMudar: (valor: RascunhoIndisponivel) => void;
}) {
  const primeiro = dias[0] ?? '';
  const ultimo = dias[dias.length - 1] ?? '';
  const invertido = !!valor.de && !!valor.ate && valor.de > valor.ate;

  return (
    <>
      <div className="field">
        <label htmlFor="indisponivel-de">De</label>
        <input
          id="indisponivel-de" type="date" min={primeiro} max={ultimo} value={valor.de}
          onChange={(e) => onMudar({ ...valor, de: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor="indisponivel-ate">Até</label>
        <input
          id="indisponivel-ate" type="date" min={primeiro} max={ultimo} value={valor.ate}
          onChange={(e) => onMudar({ ...valor, ate: e.target.value })}
        />
      </div>
      <fieldset className="causa-escolha">
        <legend>Por quê</legend>
        {(Object.keys(CAUSA) as Causa[]).map((causa) => (
          <label key={causa} className="causa-opcao">
            <input
              type="radio" name="indisponivel-causa" value={causa} checked={valor.causa === causa}
              onChange={() => onMudar({ ...valor, causa })}
            />
            {CAUSA[causa]}
          </label>
        ))}
      </fieldset>
      {invertido && <p className="note" data-tone="bad">O fim vem antes do começo.</p>}
    </>
  );
}
