'use client';
import { useEffect, useId, useRef, type ReactNode } from 'react';

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={['ui-card', className].filter(Boolean).join(' ')}>{children}</div>;
}
export function CardHeader({ children }: { children: ReactNode }) {
  return <div className="ui-card-header"><div className="ui-card-title">{children}</div></div>;
}
export function CardContent({ children }: { children: ReactNode }) {
  return <div className="ui-card-content">{children}</div>;
}

export function Stat({ label, value, note, tone }: {
  label: string; value: ReactNode; note?: string; tone?: 'good' | 'warn' | 'bad';
}) {
  return (
    <Card>
      <div className="stat" data-tone={tone}>
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {note && <div className="stat-note">{note}</div>}
      </div>
    </Card>
  );
}

export function Badge({ children, tone = 'mute' }: {
  children: ReactNode; tone?: 'good' | 'warn' | 'bad' | 'mute';
}) {
  return <span className="badge" data-tone={tone}>{children}</span>;
}

export function EmptyState({ title, description, children }: {
  title: string; description?: string; children?: ReactNode;
}) {
  return (
    <div className="ui-empty">
      <h1 className="ui-empty-title">{title}</h1>
      {description && <p className="ui-empty-desc">{description}</p>}
      {children}
    </div>
  );
}

export function Table({ head, children, className }: {
  head: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <div className="ui-table-wrap" tabIndex={0} role="group">
      <table className={['ui-table', className].filter(Boolean).join(' ')}>
        <thead><tr>{head}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function PageHead({ title, lead }: { title: string; lead?: string }) {
  return (
    <div className="page-head">
      <h1 className="page-title">{title}</h1>
      {lead && <p className="page-lead">{lead}</p>}
    </div>
  );
}

/**
 * `<dialog>` nativo: a camada de topo, o foco preso e o Esc já vêm do browser.
 * Reimplementar isso em div daria uma armadilha de foco pior e um `inert` a menos.
 */
export function Modal({ aberto, onFechar, titulo, expandido, children }: {
  aberto: boolean;
  onFechar: () => void;
  titulo: ReactNode;
  /** Cresce para a direita. A ordem aberta liga isto; o aviso curto não. */
  expandido?: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement | null>(null);
  const idTitulo = useId();

  useEffect(() => {
    const dialogo = ref.current;
    if (!dialogo) return;
    if (aberto && !dialogo.open) dialogo.showModal();
    if (!aberto && dialogo.open) dialogo.close();
  }, [aberto]);

  // `showModal` já bloqueia o clique no fundo, mas não a rolagem dele — sem isso a
  // página inteira desliza atrás do modal quando a roda do mouse passa da borda.
  useEffect(() => {
    if (!aberto) return;
    const anterior = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = anterior; };
  }, [aberto]);

  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby={idTitulo}
      onCancel={(event) => { event.preventDefault(); onFechar(); }}
      onClick={(event) => { if (event.target === ref.current) onFechar(); }}
    >
      <div className="modal-caixa" data-expandido={expandido ? 'sim' : undefined}>
        <header className="modal-topo">
          <div className="modal-titulo-linha">
            <h1
              className="modal-titulo"
              id={idTitulo}
              title={typeof titulo === 'string' ? titulo : undefined}
            >
              {titulo}
            </h1>
            <button type="button" className="modal-fechar" onClick={onFechar} aria-label="Fechar">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </header>
        <div className="modal-corpo">{children}</div>
      </div>
    </dialog>
  );
}

export type Aba = { id: string; rotulo: string; contagem?: number };

/** Abas de verdade: role, seta do teclado e foco que anda junto com a seleção. */
export function Tabs({ label, abas, ativa, onChange }: {
  label: string; abas: Aba[]; ativa: string; onChange: (id: string) => void;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function mover(indice: number, passo: number) {
    const proximo = (indice + passo + abas.length) % abas.length;
    const alvo = abas[proximo];
    onChange(alvo.id);
    refs.current[alvo.id]?.focus();
  }

  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {abas.map((aba, i) => (
        <button
          key={aba.id}
          type="button"
          role="tab"
          id={`aba-${aba.id}`}
          className="tab"
          ref={(node) => { refs.current[aba.id] = node; }}
          aria-selected={ativa === aba.id}
          aria-controls={`painel-${aba.id}`}
          tabIndex={ativa === aba.id ? 0 : -1}
          onClick={() => onChange(aba.id)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowRight') { event.preventDefault(); mover(i, 1); }
            if (event.key === 'ArrowLeft') { event.preventDefault(); mover(i, -1); }
            if (event.key === 'Home') { event.preventDefault(); mover(0, 0); }
            if (event.key === 'End') { event.preventDefault(); mover(abas.length - 1, 0); }
          }}
        >
          {aba.rotulo}
          {aba.contagem !== undefined && <span className="tab-count">{aba.contagem.toLocaleString('pt-BR')}</span>}
        </button>
      ))}
    </div>
  );
}

export function TabPanel({ id, ativa, children }: { id: string; ativa: string; children: ReactNode }) {
  if (id !== ativa) return null;
  return (
    <div role="tabpanel" id={`painel-${id}`} aria-labelledby={`aba-${id}`} tabIndex={0}>
      {children}
    </div>
  );
}
