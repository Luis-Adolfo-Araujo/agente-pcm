'use client';
import { useEffect, useState, type ReactNode } from 'react';
import { Modal, Table } from '@/components/ui';
import { mensagemDaApi, type Revisor } from '@/components/sessao/useRevisao';
import { descreverLugar, destinoEfetivo, quantosAjustes, resumoDasConsequencias } from '@/lib/previa';
import { CONSEQUENCIA, NOTA_DA_CASCATA } from '@/lib/rotulos';
import { horas, rotuloDia } from '@/lib/semana';
import {
  quemSalvo, type Consequencia, type FeedbackDoAjuste, type Previa, type RascunhoDeAjuste,
} from '@/lib/api';

/**
 * Antes de gravar, o que a ação desarruma na semana — e a escolha, linha a
 * linha, do que aceitar.
 *
 * Um componente só para as quatro ações: o formulário de cada uma entra em
 * cima, e a prévia é refeita a cada mudança dele ou de um checkbox. Não há
 * passo "ver impacto": a pessoa vê o efeito enquanto decide. A violação criada
 * aparece em tom de bloqueio, mas não trava o confirmar — o verificador não
 * veta ajuste, e aprovar a semana é que exige resolver.
 */
export function PreviaAjuste({
  titulo, acoes, formulario, vazio, revisor, titulos, feedback, anuncio, onFechar, onConfirmado,
}: {
  titulo: string;
  /** O pedido que o formulário monta. `null` enquanto ele não está completo. */
  acoes: RascunhoDeAjuste[] | null;
  formulario?: ReactNode;
  /** O que dizer enquanto `acoes` é `null`. */
  vazio?: string;
  revisor: Revisor;
  titulos: Map<string, string>;
  /** O feedback da ação, montado com a justificativa que a pessoa digitou. */
  feedback: (motivo: string) => FeedbackDoAjuste[];
  /** A frase que a tela anuncia depois de gravar. */
  anuncio: (previa: Previa) => string;
  onFechar: () => void;
  onConfirmado: (mensagem: string) => void;
}) {
  const [previa, setPrevia] = useState<Previa | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erroDaPrevia, setErroDaPrevia] = useState<string | null>(null);
  const [rejeitadas, setRejeitadas] = useState<string[]>([]);
  const [aceitas, setAceitas] = useState<string[]>([]);
  const [quem, setQuem] = useState(quemSalvo);
  const [motivo, setMotivo] = useState('');
  const { previa: pedirPrevia, confirmar, gravando, erro, limparErro } = revisor;

  // O formulário remonta o array a cada render; o que importa é o conteúdo.
  const chaveDasAcoes = JSON.stringify(acoes);

  // Ação nova, escolhas zeradas: os ids das consequências antigas podem nem existir mais.
  useEffect(() => { setRejeitadas([]); setAceitas([]); }, [chaveDasAcoes]);

  useEffect(() => {
    if (!acoes) {
      setPrevia(null);
      setErroDaPrevia(null);
      setCarregando(false);
      return;
    }
    let viva = true;
    setCarregando(true);
    const espera = setTimeout(() => {
      pedirPrevia(acoes, rejeitadas, aceitas)
        .then((nova) => { if (viva) { setPrevia(nova); setErroDaPrevia(null); } })
        .catch((causa: unknown) => {
          if (viva) setErroDaPrevia(mensagemDaApi(causa, 'calcular a prévia'));
        })
        .finally(() => { if (viva) setCarregando(false); });
    }, 300);
    return () => { viva = false; clearTimeout(espera); };
    // `acoes` entra pela chave. `pedirPrevia` muda quando a revisão muda — e aí
    // a prévia precisa ser refeita sobre a revisão nova.
  }, [chaveDasAcoes, rejeitadas, aceitas, pedirPrevia]); // eslint-disable-line react-hooks/exhaustive-deps

  function alternar(c: Consequencia) {
    if (c.locked) return;
    const alterna = (lista: string[]) => (
      lista.includes(c.id) ? lista.filter((id) => id !== c.id) : [...lista, c.id]
    );
    if (c.default_accepted) setRejeitadas(alterna);
    else setAceitas(alterna);
  }

  function fechar() {
    limparErro();
    onFechar();
  }

  async function gravar() {
    if (!acoes || !previa) return;
    const ok = await confirmar({ acoes, rejeitadas, aceitas, quem, motivo, feedback: feedback(motivo) });
    if (!ok) return;
    onConfirmado(anuncio(previa));
    onFechar();
  }

  const total = acoes && previa ? quantosAjustes(acoes, previa) : 0;
  const criadas = previa?.violations.created ?? [];
  const resolvidas = previa?.violations.resolved.length ?? 0;
  const pronto = !!acoes && !!previa && !carregando && !gravando && quem.trim().length > 0;

  return (
    <Modal aberto onFechar={fechar} expandido titulo={titulo}>
      <div className="previa">
        {formulario && <div className="previa-formulario">{formulario}</div>}

        <section className="previa-corpo" aria-busy={carregando} aria-label="O que muda na semana">
          {!acoes && (
            <p className="muted">{vazio ?? 'Complete o formulário para ver o que muda na semana.'}</p>
          )}
          {acoes && erroDaPrevia && <div className="note" data-tone="bad">{erroDaPrevia}</div>}
          {acoes && !previa && !erroDaPrevia && <p className="muted">Calculando o que muda…</p>}

          {acoes && previa && (
            <>
              <p className="previa-resumo">{resumoDasConsequencias(previa)}</p>

              {previa.notes.map((nota) => (
                <div key={nota} className="note" data-tone="bad">{NOTA_DA_CASCATA[nota] ?? nota}</div>
              ))}

              {previa.consequences.length > 0 && (
                <ul className="previa-lista">
                  {previa.consequences.map((c) => {
                    const op = c.adjustment.operation_id ?? '';
                    const destino = destinoEfetivo(c);
                    return (
                      <li key={c.id} className="previa-item" data-destino={destino}>
                        <label className="previa-escolha">
                          <input
                            type="checkbox"
                            checked={c.accepted}
                            disabled={c.locked || gravando}
                            onChange={() => alternar(c)}
                          />
                          <span className="previa-ordem">
                            <span className="mono" title={op}>{op.slice(-6)}</span>{' '}
                            {titulos.get(op) || op}
                          </span>
                          {c.locked && <span className="previa-travada">travada</span>}
                        </label>
                        <p className="previa-caminho">
                          {destino === 'fica'
                            ? <>{descreverLugar(c.from)} · continua onde está</>
                            : <>{descreverLugar(c.from)} → {descreverLugar(c.to)}</>}
                        </p>
                        <p className="previa-motivo">{CONSEQUENCIA[c.reason_code] ?? c.reason_code}</p>
                      </li>
                    );
                  })}
                </ul>
              )}

              {previa.load.length > 0 && (
                <Table className="previa-carga" head={<>
                  <th scope="col">Carga que muda</th>
                  <th scope="col" className="num">Antes</th>
                  <th scope="col" className="num">Depois</th>
                  <th scope="col" className="num">Escala</th>
                </>}>
                  {previa.load.map((linha) => {
                    const estoura = linha.shift_minutes > 0
                      ? linha.after_minutes > linha.shift_minutes
                      : linha.after_minutes > 0;
                    const rotulo = rotuloDia(linha.date);
                    return (
                      <tr key={`${linha.worker_id}-${linha.date}`}>
                        <td><span className="mono">{linha.worker_id}</span> · {rotulo.nome} {rotulo.numero}</td>
                        <td className="num">{horas(linha.before_minutes)}</td>
                        <td className="num" data-tone={estoura ? 'bad' : undefined}>
                          {horas(linha.after_minutes)}{estoura && ' · acima'}
                        </td>
                        <td className="num">
                          {linha.shift_minutes > 0 ? horas(linha.shift_minutes) : 'sem escala'}
                        </td>
                      </tr>
                    );
                  })}
                </Table>
              )}

              <div className="previa-conferencia">
                {criadas.length === 0 ? (
                  <p>
                    Conferência: nenhuma violação nova
                    {resolvidas > 0 && ` · ${resolvidas} ${resolvidas === 1 ? 'resolvida' : 'resolvidas'}`}.
                  </p>
                ) : (
                  <div className="note" data-tone="bad" role="alert">
                    <strong>{criadas.length} {criadas.length === 1 ? 'violação nova' : 'violações novas'}.</strong>{' '}
                    Dá para gravar assim; a semana só é aprovada depois de resolver.
                    <ul>
                      {criadas.map((v, i) => (
                        <li key={`${v.code}-${v.operation_id ?? ''}-${v.worker_id ?? ''}-${i}`}>
                          <span className="mono">{v.code}</span>
                          {v.operation_id && ` · ${titulos.get(v.operation_id) || v.operation_id}`}
                          {v.worker_id && ` · ${v.worker_id}`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </>
          )}
        </section>

        <footer className="previa-rodape">
          <div className="previa-campos">
            <div className="field">
              <label htmlFor="previa-quem">Quem está ajustando</label>
              <input id="previa-quem" value={quem} onChange={(e) => setQuem(e.target.value)} placeholder="seu nome" />
            </div>
            <div className="field">
              <label htmlFor="previa-motivo">
                Por quê <span className="field-opcional">opcional, mas é o que o agente aprende</span>
              </label>
              <input
                id="previa-motivo"
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                placeholder="férias programadas, parada da linha…"
              />
            </div>
          </div>
          <p className="popover-nota">Grava um ajuste na revisão. Desfazer volta o grupo inteiro.</p>
          {erro && <div className="note" data-tone="bad">{erro}</div>}
          <div className="popover-acoes">
            <button type="button" className="btn" onClick={fechar} disabled={gravando}>Cancelar</button>
            <button type="button" className="btn btn-primary" disabled={!pronto} onClick={() => { void gravar(); }}>
              {gravando ? 'Gravando…' : `Confirmar ${total} ${total === 1 ? 'ajuste' : 'ajustes'}`}
            </button>
          </div>
        </footer>
      </div>
    </Modal>
  );
}
