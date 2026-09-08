'use client';
import { useState } from 'react';
import { Badge, Card, CardContent, CardHeader, PageHead } from '@/components/ui';
import type { Run, Verification } from '@/lib/api';

export function Decidir({ run, verification, onDecide, working, error }: {
  run: Run;
  verification: Verification;
  onDecide: (decisao: 'approve' | 'reject', quem: string, motivo: string) => void;
  working: boolean;
  error: string | null;
}) {
  const [quem, setQuem] = useState('');
  const [motivo, setMotivo] = useState('');
  const decidida = run.decision;
  const podeAprovar = verification.valid;

  return (
    <>
      <PageHead
        title="Decidir"
        lead="A decisão fica registrada com quem decidiu, quando, sobre qual proposta e com quais versões de regra."
      />

      {decidida ? (
        <Card>
          <CardContent>
            <p style={{ marginTop: 0 }}>
              <Badge tone={decidida.decision === 'approve' ? 'good' : 'bad'}>
                {decidida.decision === 'approve' ? 'aprovada' : 'rejeitada'}
              </Badge>{' '}
              <span className="muted">
                por {decidida.decided_by} em {new Date(decidida.decided_at).toLocaleString('pt-BR')}
              </span>
            </p>
            <p style={{ marginBottom: 0 }}>{decidida.reason}</p>
            <p className="muted" style={{ fontSize: '.84rem', marginBottom: 0 }}>
              Aprovar não publica programação, não altera OS e não escreve na Tractian.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>Registrar a decisão</CardHeader>
          <CardContent>
            {!podeAprovar && (
              <div className="note" data-tone="bad" style={{ marginBottom: 18 }}>
                A conferência encontrou violações duras. Só é possível rejeitar.
              </div>
            )}
            <div className="field" style={{ maxWidth: 320, marginBottom: 14 }}>
              <label htmlFor="quem">Quem está decidindo</label>
              <input id="quem" value={quem} onChange={(e) => setQuem(e.target.value)} placeholder="seu nome" />
            </div>
            <div className="field" style={{ marginBottom: 18 }}>
              <label htmlFor="motivo">Motivo</label>
              <input id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="por que você está aprovando ou rejeitando" />
            </div>
            <div className="row">
              <button
                className="btn btn-primary"
                disabled={working || !podeAprovar || !quem.trim() || !motivo.trim()}
                onClick={() => onDecide('approve', quem, motivo)}
              >
                Aprovar a semana
              </button>
              <button
                className="btn"
                disabled={working || !quem.trim() || !motivo.trim()}
                onClick={() => onDecide('reject', quem, motivo)}
              >
                Rejeitar
              </button>
            </div>
            {error && <div className="note" data-tone="bad" style={{ marginTop: 16 }}>{error}</div>}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>O que fica registrado</CardHeader>
        <CardContent>
          <p className="mono" style={{ margin: 0 }}>
            execução {run.run_id}<br />
            recorte {run.snapshot_id}<br />
            período {new Date(run.request.period.start).toLocaleDateString('pt-BR')} – {new Date(run.request.period.end).toLocaleDateString('pt-BR')}
          </p>
        </CardContent>
      </Card>
    </>
  );
}
