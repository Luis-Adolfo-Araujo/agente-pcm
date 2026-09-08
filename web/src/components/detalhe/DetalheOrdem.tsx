'use client';
import { useState } from 'react';
import { Badge, Table, TabPanel, Tabs } from '@/components/ui';
import { ComoDeterminou } from '@/components/detalhe/ComoDeterminou';
import { BANDA, FATOR, FONTE, MATERIAL, valorNaOrdem } from '@/lib/rotulos';
import { hora, type Assignment, type Enriched, type Unscheduled } from '@/lib/api';
import type { Troca } from '@/lib/trocas';

export function DetalheOrdem({ item, alocada, fora, troca, podeTrocar, onAbrirTroca }: {
  item: Enriched;
  alocada: Assignment | null;
  fora: Unscheduled | null;
  troca: Troca | null;
  podeTrocar: boolean;
  /** Abre a vista de troca já apontando para quem foi clicado na tabela. */
  onAbrirTroca: (destino?: string) => void;
}) {
  const [aba, setAba] = useState('detalhe');
  const [rotuloMaterial, toneMaterial] = MATERIAL[item.materials.status] ?? [item.materials.status, 'mute'];
  const atual = alocada?.worker_ids ?? [];

  return (
    <>
      <Tabs
        label="Como ler esta ordem"
        ativa={aba}
        onChange={setAba}
        abas={[
          { id: 'detalhe', rotulo: 'Detalhe' },
          { id: 'trilha', rotulo: 'Como foi determinado' },
        ]}
      />

      <TabPanel id="detalhe" ativa={aba}>
        <div className="ficha">
          <div>
            <dt>Duração adotada</dt>
            <dd>
              {item.duration.minutes ?? '—'} min
              <span className="ficha-nota">{FONTE[item.duration.source] ?? item.duration.source}</span>
            </dd>
          </div>
          <div>
            <dt>Prioridade</dt>
            <dd>
              {item.priority.score.toFixed(1)}
              <span className="ficha-nota">de 100 · {BANDA[item.priority.band] ?? item.priority.band}</span>
            </dd>
          </div>
          <div>
            <dt>Material</dt>
            <dd>
              <Badge tone={toneMaterial}>{rotuloMaterial}</Badge>
              <span className="ficha-nota">
                {item.materials.blocking ? 'bloqueia a execução' : 'não bloqueia'}
              </span>
            </dd>
          </div>
          <div>
            <dt>Ordem de serviço</dt>
            <dd className="ficha-mono">
              {item.operation.work_order_id}
              <span className="ficha-nota">operação {item.operation.operation_id.slice(-8)}</span>
            </dd>
          </div>
        </div>

        <section className="secao">
          <h2 className="secao-titulo">Por que está nesta posição</h2>
          <Table head={<>
            <th scope="col">Fator</th>
            <th scope="col">O que esta ordem tem</th>
            <th scope="col">Contribuição</th>
          </>}>
            {item.priority.components.map((comp) => {
              const teto = comp.weight * 100;
              return (
                <tr key={comp.name}>
                  <td>{FATOR[comp.name] ?? comp.name}</td>
                  <td className="muted">
                    {valorNaOrdem(comp.name, comp.raw_value, item.priority.reason_codes)}
                  </td>
                  <td>
                    <div className="row" style={{ gap: 10, alignItems: 'center', flexWrap: 'nowrap' }}>
                      <div className="bar" style={{ flex: 1 }}>
                        <i style={{ width: `${teto > 0 ? (comp.contribution / teto) * 100 : 0}%` }} />
                      </div>
                      <span className="num" style={{ minWidth: 76 }}>
                        {comp.contribution.toFixed(1)}
                        <span className="campo-total"> de {teto.toFixed(0)}</span>
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
            <tr>
              <td colSpan={2}><strong>Score final</strong></td>
              <td className="num">
                <strong>{item.priority.score.toFixed(1)}</strong>
                <span className="campo-total"> de 100</span>
              </td>
            </tr>
          </Table>
          {item.priority.missing_fields.length > 0 && (
            <div className="note" data-tone="bad" style={{ marginTop: 12 }}>
              Sem informação de: {item.priority.missing_fields.join(', ')}. Ausência não virou valor
              baixo — ficou marcada.
            </div>
          )}
        </section>

        <section className="secao">
          <h2 className="secao-titulo">
            {atual.length > 0 ? 'Quem está com ela, e quem mais poderia' : 'Executantes sugeridos'}
          </h2>
          {item.executants.length === 0 ? (
            <p className="muted">Nenhum candidato compatível para esta ordem.</p>
          ) : (
            <Table head={<>
              <th scope="col">Pessoa</th>
              <th scope="col" className="num">Score</th>
              <th scope="col">Elegível</th>
              <th scope="col">Evidência</th>
              {podeTrocar && <th scope="col"><span className="sr-only">Ação</span></th>}
            </>}>
              {item.executants.slice(0, 6).map((e) => {
                const ehAtual = atual.includes(e.worker_id);
                return (
                  <tr key={e.worker_id} aria-selected={ehAtual || undefined}>
                    <td className="mono" style={{ color: 'var(--color-text)' }}>
                      {e.worker_id}
                      {ehAtual && <span className="marca-atual">nesta ordem</span>}
                    </td>
                    <td className="num">{e.score.toFixed(0)}</td>
                    <td>{e.eligible ? <Badge tone="good">sim</Badge> : <Badge tone="bad">não</Badge>}</td>
                    <td className="muted" style={{ fontSize: '.8rem' }}>{e.reason_codes.join(' · ') || '—'}</td>
                    {podeTrocar && (
                      <td className="num">
                        {!ehAtual && (
                          <button
                            type="button"
                            className="btn btn-menor"
                            onClick={() => onAbrirTroca(e.worker_id)}
                          >
                            Passar
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </Table>
          )}
          {item.executants.length > 6 && (
            <p className="muted" style={{ fontSize: '.84rem', marginBottom: 0 }}>
              Mostrando 6 de {item.executants.length} candidatos.
            </p>
          )}

          {/* A tabela lista só quem o agente avaliou. Quem você quer pode não estar
              nela — daí a porta de entrada que não depende de candidato. */}
          {podeTrocar && (
            <button type="button" className="btn" onClick={() => onAbrirTroca()} style={{ marginTop: 'var(--space-md)' }}>
              {item.executants.length === 0 ? 'Passar para outra pessoa mesmo assim' : 'Passar para alguém fora desta lista'}
            </button>
          )}
        </section>

        {alocada && (
          <p className="muted" style={{ fontSize: '.84rem', marginBottom: 0 }}>
            Alocada das {hora(alocada.window.start)} às {hora(alocada.window.end)}.
            {troca && ` Passada por você para ${troca.para}.`}
          </p>
        )}
        {fora && (
          <p className="muted" style={{ fontSize: '.84rem', marginBottom: 0 }}>
            Esta ordem não entrou na semana, então não tem executante nem horário.
          </p>
        )}
      </TabPanel>

      <TabPanel id="trilha" ativa={aba}>
        <ComoDeterminou item={item} alocada={alocada} fora={fora} troca={troca} />
      </TabPanel>
    </>
  );
}
