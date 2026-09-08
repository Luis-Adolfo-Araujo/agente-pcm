'use client';
import type { FiltroSemana } from '@/lib/matriz';

/**
 * O recorte da matriz.
 *
 * Não há Facility, Team nem Certification: esses campos não existem no contrato
 * da API, e um select vazio prometeria um recorte que não dá para fazer. O local
 * existe, mas só como id da origem — daí o rótulo dizer "código" em vez de fingir
 * que a tela conhece o nome dele.
 */
export function FiltrosSemana({ filtro, locais, onMudar, resultado }: {
  filtro: FiltroSemana;
  locais: string[];
  onMudar: (filtro: FiltroSemana) => void;
  /** Quantas linhas sobraram, para quem filtrou saber que sobrou pouco. */
  resultado: { linhas: number; total: number };
}) {
  const recortando = filtro.busca.trim().length > 0 || filtro.soEstouro || filtro.local.length > 0;

  return (
    <div className="filtros" role="search">
      <div className="field filtro-busca">
        <label htmlFor="filtro-busca">Buscar</label>
        <input
          id="filtro-busca"
          type="search"
          value={filtro.busca}
          placeholder="OS ou serviço"
          onChange={(e) => onMudar({ ...filtro, busca: e.target.value })}
        />
      </div>

      {locais.length > 0 && (
        <div className="field filtro-local">
          <label htmlFor="filtro-local">Local <span className="field-opcional">código</span></label>
          <select
            id="filtro-local"
            value={filtro.local}
            onChange={(e) => onMudar({ ...filtro, local: e.target.value })}
          >
            <option value="">todos</option>
            {locais.map((local) => <option key={local} value={local}>{local}</option>)}
          </select>
        </div>
      )}

      <button
        type="button"
        className="filtro-estouro"
        aria-pressed={filtro.soEstouro}
        onClick={() => onMudar({ ...filtro, soEstouro: !filtro.soEstouro })}
      >
        Só quem estourou
      </button>

      {recortando && (
        <p className="filtro-resultado">
          {resultado.linhas} de {resultado.total}{' '}
          {resultado.total === 1 ? 'pessoa' : 'pessoas'}
          {' · '}
          <button
            type="button"
            className="btn-lapis"
            onClick={() => onMudar({ busca: '', soEstouro: false, local: '' })}
          >
            limpar
          </button>
        </p>
      )}

      <p className="filtro-aviso">
        O filtro esconde linha e cartão. A barra de ocupação continua contando a semana inteira.
      </p>
    </div>
  );
}
