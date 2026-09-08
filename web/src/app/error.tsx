'use client';

import { useEffect } from 'react';

/**
 * Sem isto, um erro de render apaga a tela inteira e parece que a página recarregou.
 * O piloto precisa dizer o que quebrou, onde, e oferecer volta.
 */
export default function Erro({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error('[MAIA] erro de render:', error);
  }, [error]);

  return (
    <div className="shell">
      <main className="shell-main">
        <div className="shell-inner" style={{ maxWidth: 720 }}>
          <h1 className="page-title">A tela quebrou ao montar</h1>
          <p className="page-lead">
            Nada foi gravado e a execução no agente continua intacta. Abaixo está o que o navegador
            reportou — é isso que precisa ser corrigido.
          </p>
          <div className="note" data-tone="bad" style={{ marginTop: 20 }}>
            <strong>{error.name}: {error.message}</strong>
            {error.digest && <div className="mono" style={{ marginTop: 8 }}>digest {error.digest}</div>}
          </div>
          {error.stack && (
            <details className="trace-json" style={{ marginTop: 16 }}>
              <summary>pilha de chamadas</summary>
              <pre>{error.stack}</pre>
            </details>
          )}
          <div className="row" style={{ marginTop: 24 }}>
            <button className="btn btn-primary" onClick={reset}>Tentar montar de novo</button>
            <button className="btn" onClick={() => window.location.reload()}>Recarregar a página</button>
          </div>
        </div>
      </main>
    </div>
  );
}
