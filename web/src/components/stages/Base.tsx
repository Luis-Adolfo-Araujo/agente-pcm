'use client';
import { Badge, Card, CardContent, CardHeader, Stat, Table } from '@/components/ui';
import { STATUS_OS, STATUS_PLANEJAMENTO } from '@/lib/rotulos';
import { composicaoDoBacklog, origemDoSnapshot, type Snapshot } from '@/lib/api';

/**
 * Cada indicador conta sobre uma população diferente: cinco sobre as ordens, um
 * sobre os ativos referenciados e um sobre as pessoas ativas. A tabela precisa
 * dizer isso em cada linha, senão "988 ausentes" parece 988 ordens.
 */
const CAMPOS: Record<string, { rotulo: string; unidade: string; usa: string }> = {
  operations_with_priority: {
    rotulo: 'Prioridade da OS',
    unidade: 'ordens',
    usa: 'decide quem é atendido primeiro',
  },
  operations_with_sla: {
    rotulo: 'Prazo (SLA)',
    unidade: 'ordens',
    usa: 'mostra o que já está vencendo',
  },
  assets_with_criticality: {
    rotulo: 'Criticidade do ativo',
    unidade: 'ativos',
    usa: 'diz quais máquinas doem mais quando param',
  },
  operations_with_planned_duration: {
    rotulo: 'Duração planejada',
    unidade: 'ordens',
    usa: 'quanto tempo o serviço leva, para caber no dia',
  },
  operations_with_materials: {
    rotulo: 'Material cadastrado',
    unidade: 'ordens',
    usa: 'se existe peça para o serviço acontecer',
  },
  operations_with_activity_type: {
    rotulo: 'Tipo de atividade',
    unidade: 'ordens',
    usa: 'que serviço é, para achar quem sabe fazer',
  },
  workers_with_availability: {
    rotulo: 'Pessoas com escala',
    unidade: 'pessoas',
    usa: 'quem está disponível, e em que horário',
  },
};

export function Base({ snapshots, selected, onSelect, onNext }: {
  snapshots: Snapshot[];
  selected: Snapshot | null;
  onSelect: (id: string) => void;
  onNext: () => void;
}) {
  if (!selected) return null;
  const q = selected.quality;
  const b = composicaoDoBacklog(q);
  const planejamento = Object.entries(b.by_planning_status);
  // A jornada não é cobertura de campo — o dado está lá, e é implausível. Ela sai
  // da tabela para não distorcer o sentido de "preenchido" e "falta".
  const jornada = q.indicators.find((i) => i.key === 'workers_within_weekly_hours') ?? null;
  // Do mais fraco para o mais forte: o que falta é o que precisa ser visto primeiro.
  const indicadores = [...q.indicators]
    .filter((i) => i.key !== 'workers_within_weekly_hours')
    .sort((a, b) => a.coverage_percent - b.coverage_percent);
  const fracos = indicadores.filter((i) => i.coverage_percent < 50);

  return (
    <>
      <div className="page-source">
        <h1>Base de dados {selected.tenant_id} · {origemDoSnapshot(selected)}</h1>
        <p className="mono">
          snapshot de {new Date(selected.as_of).toLocaleDateString('pt-BR')} ·{' '}
          sha256 {selected.sha256.slice(0, 16)}… · {q.rejected_record_count} registros rejeitados pelo contrato
        </p>
      </div>

      {snapshots.length > 1 && (
        <div className="field" style={{ maxWidth: 460, marginBottom: 24 }}>
          <label htmlFor="recorte">Snapshot em uso</label>
          <select id="recorte" value={selected.snapshot_id} onChange={(e) => onSelect(e.target.value)}>
            {snapshots.map((s) => (
              <option key={s.snapshot_id} value={s.snapshot_id}>
                snapshot de {new Date(s.as_of).toLocaleDateString('pt-BR')}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="ui-grid ui-grid-4" style={{ marginBottom: 24 }}>
        {b.parcial ? (
          <Stat
            label="Operações no backlog"
            value={b.total.toLocaleString('pt-BR')}
            note="a API não informa quanto disso está disponível"
          />
        ) : (
          <Stat
            label="Manutenção disponível"
            value={b.available.toLocaleString('pt-BR')}
            note={b.blocked > 0
              ? `de ${b.total.toLocaleString('pt-BR')} no backlog · ${b.blocked.toLocaleString('pt-BR')} parada${b.blocked === 1 ? '' : 's'} na origem`
              : `de ${b.total.toLocaleString('pt-BR')} no backlog · nenhuma parada`}
            tone="good"
          />
        )}
        <Stat label="Pessoas" value={q.worker_count} note={`${q.availability_slot_count} janelas de escala`} />
        <Stat label="Itens de estoque" value={q.inventory_item_count.toLocaleString('pt-BR')} />
        <Stat label="Execuções no histórico" value={q.historical_execution_count.toLocaleString('pt-BR')} />
      </div>

      {b.parcial ? (
        <Card>
          <CardHeader>O que tem no backlog</CardHeader>
          <CardContent>
            <div className="note" data-tone="bad" style={{ margin: 0 }}>
              <strong>Esta API é mais antiga que a tela.</strong> Ela devolve quantas ordens vieram
              da origem, mas não quanto disso está disponível para fazer — a separação entre ordem
              aberta, em andamento e parada não vem no recorte. Reinicie o serviço do piloto para
              esta parte aparecer.
            </div>
          </CardContent>
        </Card>
      ) : (
      <Card>
        <CardHeader>O que tem no backlog</CardHeader>
        <CardContent>
          <p style={{ marginTop: 0, maxWidth: '72ch' }}>
            A contagem crua de ordens responde quantas vieram da origem, não quanta manutenção há
            para fazer. Uma ordem parada na origem entra na conta do backlog e não entra na semana:
            o agente a lista com o motivo, e ela nunca disputa hora-homem com as outras.
          </p>

          <Table head={<>
            <th scope="col">Situação na origem</th>
            <th scope="col" className="num">Ordens</th>
            <th scope="col" className="num">Disponíveis</th>
            <th scope="col">Entra na semana?</th>
          </>}>
            {b.by_status.map((linha) => {
              const rotulo = STATUS_OS[linha.status];
              return (
                <tr key={linha.status}>
                  <td>
                    <span className="campo-nome">{rotulo?.rotulo ?? linha.status}</span>
                    <span className="campo-uso">{rotulo?.nota ?? linha.status}</span>
                  </td>
                  <td className="num">{linha.total.toLocaleString('pt-BR')}</td>
                  <td className="num">{linha.available.toLocaleString('pt-BR')}</td>
                  <td>
                    {linha.blocked === 0
                      ? <Badge tone="good">sim</Badge>
                      : linha.available === 0
                        ? <Badge tone="bad">não</Badge>
                        : <Badge tone="warn">{linha.blocked.toLocaleString('pt-BR')} de fora</Badge>}
                  </td>
                </tr>
              );
            })}
            <tr>
              <td><strong>Disponível para fazer</strong></td>
              <td className="num">{b.total.toLocaleString('pt-BR')}</td>
              <td className="num"><strong>{b.available.toLocaleString('pt-BR')}</strong></td>
              <td className="campo-total">
                {((b.available / Math.max(1, b.total)) * 100).toFixed(1)}% do backlog
              </td>
            </tr>
          </Table>

          {planejamento.length > 0 && (
            <>
              <h2 style={{ margin: '28px 0 12px', fontSize: '1rem' }}>
                O que a origem já tinha decidido sobre programação
              </h2>
              <p className="muted" style={{ marginTop: 0, maxWidth: '72ch', fontSize: '.88rem' }}>
                O agente monta a semana do zero sobre tudo o que está disponível — ele não herda nem
                respeita a programação que já existe na Tractian. Onde a origem já tinha programado,
                a proposta é uma segunda opinião, não uma continuação.
              </p>
              <Table head={<>
                <th scope="col">Situação de programação</th>
                <th scope="col" className="num">Ordens</th>
                <th scope="col">Fatia do backlog</th>
              </>}>
                {planejamento.map(([chave, quantas]) => (
                  <tr key={chave}>
                    <td>{STATUS_PLANEJAMENTO[chave] ?? chave}</td>
                    <td className="num">{quantas.toLocaleString('pt-BR')}</td>
                    <td>
                      <div className="row" style={{ gap: 10, alignItems: 'center', flexWrap: 'nowrap' }}>
                        <div className="bar" style={{ flex: 1 }}>
                          <i style={{ width: `${(quantas / Math.max(1, b.total)) * 100}%` }} />
                        </div>
                        <span className="num" style={{ minWidth: 52 }}>
                          {((quantas / Math.max(1, b.total)) * 100).toFixed(1)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </Table>
            </>
          )}
        </CardContent>
      </Card>
      )}

      <Card>
        <CardHeader>Cobertura do cadastro</CardHeader>
        <CardContent>
          <p style={{ marginTop: 0, maxWidth: '72ch' }}>
            O agente monta a semana a partir dos campos já preenchidos em cada ordem de serviço; onde
            o campo está vazio, ele marca a ausência em vez de assumir um valor. Barra curta significa
            recomendação com menos base naquela parte.
          </p>

          <Table className="tabela-cobertura" head={<>
            <th scope="col">Campo · para que serve</th>
            <th scope="col">Cobertura</th>
            <th scope="col" className="num">Preenchido</th>
            <th scope="col" className="num">Falta</th>
            <th scope="col">Total</th>
          </>}>
            {indicadores.map((i) => {
              const campo = CAMPOS[i.key];
              const fraco = i.coverage_percent < 50;
              return (
                <tr key={i.key}>
                  <td>
                    <span className="campo-nome">{campo?.rotulo ?? i.key}</span>
                    <span className="campo-uso">{campo?.usa ?? ''}</span>
                  </td>
                  <td>
                    <div className="row" style={{ gap: 10, alignItems: 'center', flexWrap: 'nowrap' }}>
                      <div className="bar" data-tone={fraco ? 'bad' : undefined} style={{ flex: 1 }}>
                        <i style={{ width: `${i.coverage_percent}%` }} />
                      </div>
                      <span className="num" style={{ minWidth: 52 }}>{i.coverage_percent.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="num">{i.present.toLocaleString('pt-BR')}</td>
                  <td className="num">{i.missing.toLocaleString('pt-BR')}</td>
                  <td className="campo-total">
                    {i.total.toLocaleString('pt-BR')} {campo?.unidade ?? ''}
                  </td>
                </tr>
              );
            })}
          </Table>

          {jornada && jornada.missing > 0 && (
            <div className="note" data-tone="bad" style={{ marginTop: 20 }}>
              <strong>
                {jornada.missing.toLocaleString('pt-BR')} de {jornada.total.toLocaleString('pt-BR')} pessoas
                com escala têm jornada declarada acima de 44 h por semana.
              </strong>{' '}
              O agente preenche a escala que a origem afirma existir, então a semana proposta pode
              encostar nesse limite. Não é falha da recomendação: é o cadastro de disponibilidade
              descrevendo um turno que não fecha.
            </div>
          )}

          {fracos.length > 0 && (
            <div className="note" data-tone="bad" style={{ marginTop: 20 }}>
              <strong>
                {fracos.length === 1
                  ? 'Um campo está preenchido em menos da metade dos casos'
                  : `${fracos.length} campos estão preenchidos em menos da metade dos casos`}
                :{' '}
                {fracos.map((f) => CAMPOS[f.key]?.rotulo ?? f.key).join(', ')}.
              </strong>{' '}
              As ordens que dependem desses campos entram na semana com pendência explícita, e você
              vê o motivo em cada uma abrindo a ordem em “Ver a semana”.
            </div>
          )}
        </CardContent>
      </Card>

      <div style={{ marginTop: 28 }}>
        <button className="btn btn-primary" onClick={onNext}>Continuar para a semana</button>
      </div>
    </>
  );
}
