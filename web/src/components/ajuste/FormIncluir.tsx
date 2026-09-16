'use client';
import type { LinhaDestino } from '@/lib/destinos';
import type { Escolha } from '@/lib/pedidos';
import { horas, rotuloDia } from '@/lib/semana';

/**
 * Onde a ordem entra: os candidatos do agente × os dias da semana, com a folga
 * de cada célula. Clicar escolhe; a prévia embaixo diz o que acontece.
 */
export function FormIncluir({ dias, destinos, escolha, onEscolher, minutos, precisaDuracao, duracao, onDuracao }: {
  dias: string[];
  destinos: LinhaDestino[];
  escolha: Escolha | null;
  onEscolher: (escolha: Escolha) => void;
  /** O tamanho da ordem, para dizer quanto falta onde não cabe. */
  minutos: number;
  precisaDuracao: boolean;
  duracao: string;
  onDuracao: (valor: string) => void;
}) {
  return (
    <div className="incluir">
      {precisaDuracao && (
        <div className="field">
          <label htmlFor="incluir-duracao">
            Tempo previsto <span className="field-opcional">h:mm · esta OS não tem duração, e sem ela não encaixa</span>
          </label>
          <input
            id="incluir-duracao" inputMode="numeric" placeholder="1:30" value={duracao}
            onChange={(e) => onDuracao(e.target.value)}
          />
        </div>
      )}

      {destinos.length === 0 ? (
        <p className="muted">O agente não avaliou nenhum executante para esta ordem.</p>
      ) : (
        <div className="grade-destinos-rolagem">
          <table className="grade-destinos">
            <thead>
              <tr>
                <th scope="col">Quem</th>
                {dias.map((d) => (
                  <th scope="col" key={d}>{rotuloDia(d).nome} {rotuloDia(d).numero}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {destinos.map((linha) => (
                <tr key={linha.worker_id} data-elegivel={linha.eligible ? undefined : 'nao'}>
                  <th scope="row">
                    <span className="mono">{linha.worker_id}</span>
                    <span className="grade-nota">
                      {linha.eligible
                        ? `score ${linha.score.toFixed(0)}`
                        : `não elegível · ${linha.motivos.join(', ') || 'sem motivo informado'}`}
                    </span>
                  </th>
                  {linha.celulas.map((celula) => {
                    const escolhida = escolha?.tecnico === linha.worker_id && escolha.dia === celula.dia;
                    return (
                      <td key={celula.dia}>
                        <button
                          type="button"
                          className="destino"
                          data-cabe={celula.cabe ? 'sim' : 'nao'}
                          aria-pressed={escolhida}
                          disabled={celula.escala === 0}
                          onClick={() => onEscolher({ tecnico: linha.worker_id, dia: celula.dia })}
                        >
                          {celula.escala === 0
                            ? 'sem escala'
                            : celula.cabe
                              ? `cabe · ${horas(celula.folga)} livres`
                              : `faltam ${horas(minutos - celula.folga)}`}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
