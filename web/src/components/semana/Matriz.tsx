'use client';
import { useMemo, useState } from 'react';
import { LinhaExecutante } from '@/components/semana/LinhaExecutante';
import { PopoverRemanejo } from '@/components/quadro/PopoverRemanejo';
import { PopoverTroca } from '@/components/quadro/PopoverTroca';
import type { useArraste } from '@/components/quadro/useArraste';
import type { useRemanejos } from '@/components/sessao/useRemanejos';
import type { Pedido } from '@/components/sessao/useTrocas';
import { decidirSolta, destinoDaCelula, ocupacaoDoDia, type LinhaSemana, type Solta } from '@/lib/matriz';
import { inicioNoDia } from '@/lib/remanejos';
import { diaDe, minutosDe, rotuloDia } from '@/lib/semana';
import type { Schedule } from '@/lib/api';
import type { Remanejo } from '@/lib/remanejos';
import type { Troca } from '@/lib/trocas';

/** Um cartão solto numa célula, esperando quem move e por quê. */
type PedidoDeCelula = {
  tipo: Exclude<Solta, 'nada'>;
  operationId: string;
  deTecnico: string;
  deDia: string;
  paraTecnico: string;
  paraDia: string;
};

/** A casa decimal só aqui: o agregado do dia é a leitura fina da semana. */
function agregado(ocupacao: number | null): string {
  if (ocupacao === null) return '—';
  return `${ocupacao.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

/**
 * A semana inteira de uma vez: uma linha por pessoa, uma coluna por dia.
 *
 * A matriz responde a pergunta que o quadro de um dia não responde — quem
 * estourou e quem está ocioso na semana — e aceita a correção no mesmo lugar. O
 * arraste tem uma gramática só: a célula onde o cartão cai é a pessoa e o dia.
 * O que muda é o registro. Mesmo dia, outra pessoa, é troca de executante; outro
 * dia é remanejo, que já carrega a pessoa junto.
 *
 * Sequenciar continua fora daqui: a célula tem uma linha de HH, não uma fila de
 * relógio.
 */
export function Matriz({
  dias, linhas, todas, schedule, base, titulos, trocas, remanejos, ativa, total,
  onAbrirOrdem, onAbrirDia, arraste, remanejo, trocar, gravando, erro, limparErro,
}: {
  dias: string[];
  /** As linhas que a tela desenha, já filtradas. */
  linhas: LinhaSemana[];
  /** As linhas sem filtro: a ocupação do dia e os avisos contam a semana inteira. */
  todas: LinhaSemana[];
  schedule: Schedule;
  /** A semana antes de reordenar, para o cartão dizer que horário ele tinha. */
  base: Schedule;
  titulos: Map<string, string>;
  trocas: Troca[];
  remanejos: Remanejo[];
  ativa: string | null;
  /** Ordens alocadas na semana, para o canto do cabeçalho. */
  total: number;
  onAbrirOrdem: (operationId: string) => void;
  onAbrirDia: (dia: string) => void;
  arraste: ReturnType<typeof useArraste>;
  remanejo: ReturnType<typeof useRemanejos>;
  trocar: (pedido: Pedido) => Promise<boolean>;
  gravando: boolean;
  erro: string | null;
  limparErro: () => void;
}) {
  const [abertas, setAbertas] = useState<string[]>([]);
  const [alvo, setAlvo] = useState<{ tecnico: string; dia: string } | null>(null);
  const [pedido, setPedido] = useState<PedidoDeCelula | null>(null);

  const ocupacoes = useMemo(
    () => new Map(dias.map((dia) => [dia, ocupacaoDoDia(todas, dia)])),
    [dias, todas],
  );

  const inicioOriginal = useMemo(() => {
    const mapa = new Map<string, string>();
    base.assignments.forEach((a) => mapa.set(a.operation_id, a.window.start));
    return mapa;
  }, [base]);

  const trocadas = useMemo(() => new Set(trocas.map((t) => t.operation_id)), [trocas]);
  const movidas = useMemo(() => new Set(remanejos.map((r) => r.operation_id)), [remanejos]);

  const ordemDoPedido = pedido
    ? schedule.assignments.find((a) => a.operation_id === pedido.operationId) ?? null
    : null;
  const destino = pedido ? destinoDaCelula(todas, pedido.paraTecnico, pedido.paraDia) : null;

  function alternar(tecnico: string) {
    setAbertas((atuais) => (
      atuais.includes(tecnico) ? atuais.filter((t) => t !== tecnico) : [...atuais, tecnico]
    ));
  }

  function soltar(paraTecnico: string, paraDia: string) {
    const emCurso = arraste.arraste;
    setAlvo(null);
    if (!emCurso) return;
    const ordem = schedule.assignments.find((a) => a.operation_id === emCurso.operationId);
    arraste.terminar();
    if (!ordem) return;
    const decisao = decidirSolta(ordem, emCurso.tecnico, paraTecnico, paraDia);
    if (decisao === 'nada') return;
    limparErro();
    remanejo.limparErro();
    setPedido({
      tipo: decisao,
      operationId: emCurso.operationId,
      deTecnico: emCurso.tecnico,
      deDia: diaDe(ordem.window.start),
      paraTecnico,
      paraDia,
    });
    // Quem recebe precisa aparecer: a linha de destino pode estar fechada, e a
    // ordem sumiria da tela entre a solta e a confirmação.
    setAbertas((atuais) => (atuais.includes(paraTecnico) ? atuais : [...atuais, paraTecnico]));
  }

  async function confirmarTroca(quem: string, motivo: string) {
    if (!pedido) return;
    const ok = await trocar({
      operation_id: pedido.operationId, de: pedido.deTecnico, para: pedido.paraTecnico, motivo, quem,
    });
    // Recusado pela API, o cartão fica onde estava: a tela não afirma o que o
    // banco não tem. O erro aparece no próprio popover.
    if (ok) setPedido(null);
  }

  async function confirmarRemanejo(paraTecnico: string, hhmm: string, quem: string, motivo: string) {
    if (!pedido || !ordemDoPedido) return;
    const ok = await remanejo.remanejar({
      operation_id: pedido.operationId,
      deDia: pedido.deDia,
      deInicio: ordemDoPedido.window.start,
      deTecnico: pedido.deTecnico,
      paraDia: pedido.paraDia,
      paraInicio: inicioNoDia(ordemDoPedido.window.start, pedido.paraDia, hhmm),
      paraTecnico,
      motivo,
      quem,
    });
    if (ok) setPedido(null);
  }

  function popoverDa(tecnico: string, dia: string) {
    if (!pedido || !ordemDoPedido || pedido.paraTecnico !== tecnico || pedido.paraDia !== dia) {
      return null;
    }
    if (pedido.tipo === 'troca') {
      return {
        dia,
        conteudo: (
          <PopoverTroca
            de={pedido.deTecnico}
            para={pedido.paraTecnico}
            duracao={minutosDe(ordemDoPedido)}
            cargaDestino={destino?.carga ?? 0}
            escalaDestino={destino?.escala ?? 0}
            gravando={gravando}
            erro={erro}
            onConfirmar={confirmarTroca}
            onCancelar={() => { limparErro(); setPedido(null); }}
          />
        ),
      };
    }
    return {
      dia,
      conteudo: (
        <PopoverRemanejo
          deDia={pedido.deDia}
          paraDia={pedido.paraDia}
          deTecnico={pedido.deTecnico}
          horaAtual={ordemDoPedido.window.start.slice(11, 16)}
          duracao={minutosDe(ordemDoPedido)}
          dividida={ordemDoPedido.worker_ids.length > 1}
          // A célula já disse quem recebe; perguntar de novo seria refazer o gesto.
          pessoaFixa
          destinos={destino ? [destino] : []}
          gravando={remanejo.gravando}
          erro={remanejo.erro}
          onConfirmar={confirmarRemanejo}
          onCancelar={() => { remanejo.limparErro(); setPedido(null); }}
        />
      ),
    };
  }

  const todasAbertas = linhas.length > 0 && linhas.every((l) => abertas.includes(l.tecnico));

  return (
    <div className="matriz-caixa">
      <div className="matriz-acoes">
        <button
          type="button"
          className="btn btn-menor"
          onClick={() => setAbertas(todasAbertas ? [] : linhas.map((l) => l.tecnico))}
        >
          {todasAbertas ? 'Fechar todas' : 'Abrir todas'}
        </button>
        <span className="muted">
          Abra a linha para ver as ordens e arrastá-las. A célula de destino pode ficar fechada.
        </span>
      </div>

      <div className="matriz-rolagem" tabIndex={0} role="group" aria-label="Semana por executante">
        <table className="matriz">
          <thead>
            <tr>
              <th scope="col" className="matriz-canto">
                <span className="canto-titulo">Executante</span>
                <span className="canto-total">
                  {total.toLocaleString('pt-BR')} {total === 1 ? 'ordem' : 'ordens'}
                </span>
              </th>
              {dias.map((dia) => {
                const rotulo = rotuloDia(dia);
                return (
                  <th scope="col" key={dia} className="matriz-dia">
                    <button type="button" className="dia-abrir" onClick={() => onAbrirDia(dia)}>
                      <span className="dia-nome">{rotulo.nome} {rotulo.numero}</span>
                      <span className="dia-ocupacao">{agregado(ocupacoes.get(dia) ?? null)}</span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {linhas.map((linha) => (
              <LinhaExecutante
                key={linha.tecnico}
                linha={linha}
                aberta={abertas.includes(linha.tecnico)}
                alvo={alvo?.tecnico === linha.tecnico ? alvo.dia : null}
                arrastando={arraste.arraste?.operationId ?? null}
                titulos={titulos}
                inicioOriginal={inicioOriginal}
                trocadas={trocadas}
                movidas={movidas}
                ativa={ativa}
                popoverEm={linha.celulas.map((c) => popoverDa(linha.tecnico, c.dia)).find(Boolean) ?? null}
                onAlternar={() => alternar(linha.tecnico)}
                onAbrirDia={onAbrirDia}
                onAbrirOrdem={onAbrirOrdem}
                onArrastarInicio={(operationId, posicao) => {
                  arraste.comecar(operationId, linha.tecnico, posicao);
                }}
                onArrastarFim={() => { arraste.terminar(); setAlvo(null); }}
                onMirar={(dia) => setAlvo({ tecnico: linha.tecnico, dia })}
                onSair={(dia) => setAlvo((atual) => (
                  atual?.tecnico === linha.tecnico && atual.dia === dia ? null : atual
                ))}
                onSoltar={(dia) => soltar(linha.tecnico, dia)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
