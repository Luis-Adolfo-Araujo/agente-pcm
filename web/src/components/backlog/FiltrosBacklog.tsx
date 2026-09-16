'use client';
import { REASON_NAMES } from '@/lib/api';
import {
  SEM_FILTRO_BACKLOG, filtrando, type FiltroBacklog, type OpcoesDoBacklog,
} from '@/lib/filtroBacklog';
import { BANDA, MATERIAL } from '@/lib/rotulos';

/**
 * O recorte do backlog. Cada seletor só aparece quando há o que escolher, e só
 * com os valores que existem nas ordens de fora — um select vazio prometeria um
 * recorte que não dá para fazer.
 */
export function FiltrosBacklog({ filtro, opcoes, onMudar, resultado }: {
  filtro: FiltroBacklog;
  opcoes: OpcoesDoBacklog;
  onMudar: (filtro: FiltroBacklog) => void;
  resultado: { linhas: number; total: number };
}) {
  const mudar = (parcial: Partial<FiltroBacklog>) => onMudar({ ...filtro, ...parcial });

  return (
    <div className="filtros filtros-backlog" role="search">
      <div className="field filtro-busca">
        <label htmlFor="backlog-busca">Buscar</label>
        <input
          id="backlog-busca" type="search" value={filtro.busca} placeholder="OS ou serviço"
          onChange={(e) => mudar({ busca: e.target.value })}
        />
      </div>
      <Seletor
        id="backlog-motivo" rotulo="Motivo" valor={filtro.motivo} opcoes={opcoes.motivos}
        nome={(m) => REASON_NAMES[m] ?? m} onMudar={(motivo) => mudar({ motivo })}
      />
      <Seletor
        id="backlog-local" rotulo="Local (código)" valor={filtro.local} opcoes={opcoes.locais}
        nome={(l) => l} onMudar={(local) => mudar({ local })}
      />
      <Seletor
        id="backlog-faixa" rotulo="Prioridade" valor={filtro.faixa} opcoes={opcoes.faixas}
        nome={(f) => BANDA[f] ?? f} onMudar={(faixa) => mudar({ faixa })}
      />
      <div className="field filtro-score">
        <label htmlFor="backlog-score">Score mínimo</label>
        <input
          id="backlog-score" inputMode="numeric" value={filtro.scoreMinimo} placeholder="0"
          onChange={(e) => mudar({ scoreMinimo: e.target.value })}
        />
      </div>
      <Seletor
        id="backlog-material" rotulo="Material" valor={filtro.material} opcoes={opcoes.materiais}
        nome={(m) => MATERIAL[m]?.[0] ?? m} onMudar={(material) => mudar({ material })}
      />
      <div className="field">
        <label htmlFor="backlog-bloqueador">Bloqueia a execução</label>
        <select
          id="backlog-bloqueador" value={filtro.bloqueador}
          onChange={(e) => mudar({ bloqueador: e.target.value as FiltroBacklog['bloqueador'] })}
        >
          <option value="">tanto faz</option>
          <option value="sim">bloqueia</option>
          <option value="nao">não bloqueia</option>
        </select>
      </div>
      <Seletor
        id="backlog-tecnico" rotulo="Técnico candidato" valor={filtro.tecnico} opcoes={opcoes.tecnicos}
        nome={(t) => t} onMudar={(tecnico) => mudar({ tecnico })}
      />
      <button
        type="button"
        className="filtro-estouro"
        aria-pressed={filtro.venceNoPeriodo}
        onClick={() => mudar({ venceNoPeriodo: !filtro.venceNoPeriodo })}
      >
        Vence nesta semana
      </button>

      {filtrando(filtro) && (
        <p className="filtro-resultado">
          {resultado.linhas} de {resultado.total} {resultado.total === 1 ? 'ordem' : 'ordens'}
          {' · '}
          <button type="button" className="btn-lapis" onClick={() => onMudar(SEM_FILTRO_BACKLOG)}>
            limpar
          </button>
        </p>
      )}

      <p className="filtro-aviso">
        O filtro esconde linhas. As contagens por motivo continuam contando todas as ordens de fora.
      </p>
    </div>
  );
}

function Seletor({ id, rotulo, valor, opcoes, nome, onMudar }: {
  id: string;
  rotulo: string;
  valor: string;
  opcoes: string[];
  nome: (valor: string) => string;
  onMudar: (valor: string) => void;
}) {
  if (opcoes.length === 0) return null;
  return (
    <div className="field">
      <label htmlFor={id}>{rotulo}</label>
      <select id={id} value={valor} onChange={(e) => onMudar(e.target.value)}>
        <option value="">todos</option>
        {opcoes.map((opcao) => <option key={opcao} value={opcao}>{nome(opcao)}</option>)}
      </select>
    </div>
  );
}
