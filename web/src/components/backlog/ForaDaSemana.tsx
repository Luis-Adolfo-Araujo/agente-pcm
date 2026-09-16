'use client';
import { useEffect, useMemo, useState } from 'react';
import { Badge, Card, CardContent, CardHeader, EmptyState, Stat, Table } from '@/components/ui';
import { FiltrosBacklog } from '@/components/backlog/FiltrosBacklog';
import { REASON_NAMES, dia, type Backlog, type Schedule } from '@/lib/api';
import {
  SEM_FILTRO_BACKLOG, contagemPorMotivo, filtrarBacklog, linhasDoBacklog, opcoesDoBacklog,
} from '@/lib/filtroBacklog';
import { BANDA, MATERIAL } from '@/lib/rotulos';
import { horas } from '@/lib/semana';

const PAGINA = 120;

type Tom = 'good' | 'warn' | 'bad' | 'mute';

/**
 * O que ficou de fora da semana — da revisão, não da proposta: uma ordem tirada
 * pelo PCM aparece aqui com o motivo dela, e uma incluída sai.
 */
export function ForaDaSemana({ semana, backlog, periodo, titulos, onAbrirOrdem, onIncluir }: {
  semana: Schedule;
  backlog: Backlog;
  periodo: { start: string; end: string };
  titulos: Map<string, string>;
  onAbrirOrdem: (operationId: string) => void;
  /** Abre a prévia de incluir a ordem. Ausente, a coluna de ação some. */
  onIncluir?: (operationId: string) => void;
}) {
  const [filtro, setFiltro] = useState(SEM_FILTRO_BACKLOG);
  const [limite, setLimite] = useState(PAGINA);
  const linhas = useMemo(() => linhasDoBacklog(semana, backlog), [semana, backlog]);
  const opcoes = useMemo(() => opcoesDoBacklog(linhas), [linhas]);
  const contagem = useMemo(() => contagemPorMotivo(linhas), [linhas]);
  const filtradas = useMemo(() => filtrarBacklog(linhas, filtro, periodo), [linhas, filtro, periodo]);

  // Filtro novo, lista do começo: "mostrar mais" de um recorte não vale para outro.
  useEffect(() => setLimite(PAGINA), [filtro]);

  return (
    <Card>
      <CardHeader>Por que cada ordem ficou de fora</CardHeader>
      <CardContent>
        <div className="ui-grid ui-grid-4" style={{ marginBottom: 20 }}>
          {contagem.map(([motivo, quantas]) => (
            <Stat
              key={motivo}
              label={REASON_NAMES[motivo] ?? motivo}
              value={quantas.toLocaleString('pt-BR')}
              tone={motivo === 'no_capacity' ? 'warn' : 'bad'}
            />
          ))}
        </div>

        <FiltrosBacklog
          filtro={filtro}
          opcoes={opcoes}
          onMudar={setFiltro}
          resultado={{ linhas: filtradas.length, total: linhas.length }}
        />

        {filtradas.length === 0 ? (
          <EmptyState
            title="Nada casa com esse recorte"
            description="Nenhuma ordem de fora da semana atende a todos os filtros ao mesmo tempo."
          >
            <button type="button" className="btn" onClick={() => setFiltro(SEM_FILTRO_BACKLOG)}>
              Limpar os filtros
            </button>
          </EmptyState>
        ) : (
          <>
            <Table head={<>
              <th scope="col">OS</th>
              <th scope="col">Serviço</th>
              <th scope="col">Motivo</th>
              <th scope="col" className="num">Prioridade</th>
              <th scope="col" className="num">Duração</th>
              <th scope="col">Material</th>
              <th scope="col">Vence</th>
              {onIncluir && <th scope="col"><span className="sr-only">Ação</span></th>}
            </>}>
              {filtradas.slice(0, limite).map(({ fora, item }) => {
                const material: [string, Tom] = item
                  ? MATERIAL[item.materials.status] ?? [item.materials.status, 'mute']
                  : ['—', 'mute'];
                const [rotuloMaterial, tomMaterial] = material;
                return (
                  <tr key={fora.operation_id}>
                    <td className="mono" title={fora.work_order_id}>
                      <button type="button" className="btn-lapis" onClick={() => onAbrirOrdem(fora.operation_id)}>
                        {fora.work_order_id.slice(-6)}
                      </button>
                    </td>
                    <td>{titulos.get(fora.operation_id) ?? '—'}</td>
                    <td>
                      <Badge tone={fora.reason === 'no_capacity' ? 'warn' : 'bad'}>
                        {REASON_NAMES[fora.reason] ?? fora.reason}
                      </Badge>
                    </td>
                    <td className="num">
                      {item ? `${item.priority.score.toFixed(0)} · ${BANDA[item.priority.band] ?? item.priority.band}` : '—'}
                    </td>
                    <td className="num">{item?.duration.minutes ? horas(item.duration.minutes) : 'sem duração'}</td>
                    <td><Badge tone={tomMaterial}>{rotuloMaterial}</Badge></td>
                    <td>{item?.operation.due_at ? dia(item.operation.due_at) : '—'}</td>
                    {onIncluir && (
                      <td className="num">
                        {item && (
                          <button type="button" className="btn btn-menor" onClick={() => onIncluir(fora.operation_id)}>
                            Incluir
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </Table>
            {filtradas.length > limite && (
              <button
                type="button"
                className="btn"
                style={{ marginTop: 'var(--space-md)' }}
                onClick={() => setLimite((atual) => atual + PAGINA)}
              >
                Mostrar mais {Math.min(PAGINA, filtradas.length - limite)} de {filtradas.length - limite}
              </button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
