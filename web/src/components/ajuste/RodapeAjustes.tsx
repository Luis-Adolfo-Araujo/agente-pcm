'use client';
import { useState } from 'react';
import { Modal, Table } from '@/components/ui';
import { gruposDaRevisao, resumoDoGrupo } from '@/lib/revisao';
import type { Revisao } from '@/lib/api';

/**
 * O que a pessoa já mudou na semana, sempre à vista enquanto houver mudança.
 * Tela sem ajuste não tem rodapé: a proposta do agente é o estado normal.
 */
export function RodapeAjustes({ revisao, gravando, onDesfazer }: {
  revisao: Revisao | null;
  gravando: boolean;
  onDesfazer: () => void;
}) {
  const [lista, setLista] = useState(false);
  if (!revisao || revisao.revision_sequence === 0) return null;

  const total = revisao.revision_sequence;
  const criadas = revisao.created_violations.length;
  const grupos = gruposDaRevisao(revisao.adjustments);

  return (
    <>
      <div className="rodape-ajustes" role="region" aria-label="Ajustes desta semana">
        <span className="rodape-ajustes-conta">
          <strong>{total}</strong> {total === 1 ? 'ajuste seu' : 'ajustes seus'}
          {' · '}
          <span data-tone={criadas > 0 ? 'bad' : undefined}>
            {criadas} {criadas === 1 ? 'violação criada' : 'violações criadas'}
          </span>
        </span>
        <button type="button" className="btn btn-menor" disabled={gravando} onClick={onDesfazer}>
          {gravando ? 'Desfazendo…' : 'Desfazer último'}
        </button>
        <button type="button" className="btn btn-menor" onClick={() => setLista(true)}>
          Ver todos
        </button>
      </div>

      <Modal aberto={lista} onFechar={() => setLista(false)} titulo="Ajustes desta semana">
        <Table head={<>
          <th scope="col">Quando</th>
          <th scope="col">Quem</th>
          <th scope="col">O que</th>
          <th scope="col" className="num">Ajustes</th>
        </>}>
          {grupos.map((grupo) => (
            <tr key={grupo.grupo}>
              <td className="mono">
                {new Date(grupo.em).toLocaleString('pt-BR', {
                  day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                })}
              </td>
              <td>{grupo.quem}</td>
              <td>{resumoDoGrupo(grupo.porTipo)}</td>
              <td className="num">{grupo.total}</td>
            </tr>
          ))}
        </Table>
        <p className="muted" style={{ marginBottom: 0 }}>
          Desfazer tira o grupo mais recente inteiro: uma indisponibilidade volta junto com as ordens
          que ela moveu.
        </p>
      </Modal>
    </>
  );
}
