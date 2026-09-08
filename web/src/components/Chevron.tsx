'use client';

export type EstadoEtapa = 'done' | 'current' | 'available' | 'locked';
export type Metrica = { value: string; tone?: 'good' | 'warn' | 'bad' };
export type Etapa = { id: number; nome: string; estado: EstadoEtapa; metrica: Metrica };

function Marca({ estado }: { estado: EstadoEtapa }) {
  if (estado === 'done') {
    return (
      <svg className="chev-mark" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
        <path d="M2.5 7.5 5.5 10.5 11.5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (estado === 'current') {
    // O pingo inclinado do "i" do logotipo, no único lugar onde o laranja da marca aparece.
    return <span className="chev-dot" aria-hidden="true" />;
  }
  if (estado === 'locked') {
    return (
      <svg className="chev-mark" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
        <rect x="3" y="6.2" width="8" height="5.3" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
        <path d="M5.2 6.2V4.9a1.8 1.8 0 0 1 3.6 0v1.3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    );
  }
  return null;
}

const ROTULO_ESTADO: Record<EstadoEtapa, string> = {
  done: 'concluída',
  current: 'etapa atual',
  available: 'disponível',
  locked: 'ainda travada',
};

/**
 * O trilho do processo: uma seta por etapa, com o número daquela etapa em cima.
 * O número vem sempre da execução — é o trace aparecendo na navegação.
 */
export function Chevron({ etapas, onSelect }: { etapas: Etapa[]; onSelect: (id: number) => void }) {
  return (
    <nav aria-label="Etapas da programação">
      <ol className="rail">
        {etapas.map((etapa) => (
          <li key={etapa.id} className="step">
            <span className="step-metric" data-tone={etapa.metrica.tone}>{etapa.metrica.value}</span>
            <button
              type="button"
              className="chev"
              data-state={etapa.estado}
              disabled={etapa.estado === 'locked'}
              aria-current={etapa.estado === 'current' ? 'step' : undefined}
              onClick={() => onSelect(etapa.id)}
            >
              <Marca estado={etapa.estado} />
              <span className="chev-name">{etapa.nome}</span>
              <span className="sr-only">
                {` · ${ROTULO_ESTADO[etapa.estado]} · ${etapa.metrica.value}`}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
