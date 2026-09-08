'use client';
import { useEffect, useMemo, useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { ColunaTecnico } from '@/components/quadro/ColunaTecnico';
import type { useArraste } from '@/components/quadro/useArraste';
import { BarraSequencia, type Pendencia } from '@/components/quadro/BarraSequencia';
import { PopoverTroca } from '@/components/quadro/PopoverTroca';
import type { useReordens } from '@/components/sessao/useReordens';
import type { Pedido } from '@/components/sessao/useTrocas';
import { colunasDoDia, inserirPeloRelogio } from '@/lib/quadro';
import { mover, mudancas, ordensDoDia, reordenacaoDe, trocasDePosicao } from '@/lib/reordenar';
import { minutosDe } from '@/lib/semana';
import type { Backlog, Schedule } from '@/lib/api';
import type { Remanejo } from '@/lib/remanejos';
import type { Troca } from '@/lib/trocas';

/** Uma troca desenhada pelo arraste, ainda não gravada. */
type PedidoDeTroca = { operationId: string; de: string; para: string; duracao: number };

/**
 * O dia inteiro de uma vez: uma coluna por pessoa, um cartão por ordem.
 *
 * As colunas vêm de `colunasDoDia`, que já decide quem tem coluna e em que ordem
 * elas ficam — a tela só desenha, e por isso a regra é testável sem render.
 *
 * O arraste tem duas gramáticas. Dentro da coluna ele desenha a sequência do dia
 * e se acumula na barra de baixo. Entre colunas ele passa a ordem para outra
 * pessoa, e aí para e pergunta: a troca só aparece na tela depois de gravada.
 */
export function Quadro({
  dia, schedule, base, backlog, trocas, remanejos, titulos, ativa, onAbrirOrdem,
  arraste, reordenacao, trocar, gravando, erro, limparErro,
}: {
  dia: string;
  /** A semana com trocas e sequências da sessão por cima. */
  schedule: Schedule;
  /** A mesma semana antes de reordenar, para dizer que horário a ordem tinha. */
  base: Schedule;
  backlog: Backlog;
  trocas: Troca[];
  remanejos: Remanejo[];
  titulos: Map<string, string>;
  ativa: string | null;
  onAbrirOrdem: (operationId: string) => void;
  /** O arraste em curso, compartilhado com o trilho de dias. */
  arraste: ReturnType<typeof useArraste>;
  reordenacao: ReturnType<typeof useReordens>;
  trocar: (pedido: Pedido) => Promise<boolean>;
  gravando: boolean;
  erro: string | null;
  limparErro: () => void;
}) {
  const [pedido, setPedido] = useState<PedidoDeTroca | null>(null);
  // A ordem que acabou de trocar de dono e ainda precisa achar o lugar dela na
  // sequência pendente do destino — que só existe no render seguinte.
  const recemChegada = useRef<{ operationId: string; tecnico: string } | null>(null);
  const trilho = useRef<HTMLDivElement>(null);

  const colunas = useMemo(
    () => colunasDoDia(schedule.assignments, backlog.capacities, dia, trocas, remanejos),
    [schedule, backlog, dia, trocas, remanejos],
  );

  /** O horário que cada ordem do dia tinha antes de a sequência ser remexida. */
  const inicioOriginal = useMemo(() => {
    const mapa = new Map<string, string>();
    base.assignments.forEach((a) => mapa.set(a.operation_id, a.window.start));
    return mapa;
  }, [base]);

  /**
   * O que cada coluna tem de remexido e ainda não registrado. Quem só foi
   * empurrado pelo reempacotamento entra na contagem, mas não vira feedback:
   * gravar "o agente errou" numa ordem que a pessoa não tocou ensinaria o
   * contrário do que ela quis dizer.
   */
  const pendencias = useMemo((): Pendencia[] => colunas
    .filter((coluna) => reordenacao.pendenteEm(coluna.tecnico, dia))
    .map((coluna) => {
      const remexidas = mudancas(
        ordensDoDia(base, coluna.tecnico, dia),
        ordensDoDia(schedule, coluna.tecnico, dia),
      );
      const decididas = trocasDePosicao(remexidas);
      return { tecnico: coluna.tecnico, decididas, empurradas: remexidas.length - decididas.length };
    })
    .filter((pendencia) => pendencia.decididas.length > 0),
  [colunas, base, schedule, dia, reordenacao]);

  /**
   * A sequência pendente do destino não conhece a recém-chegada, e `reempacotar`
   * jogaria ela para o fim da fila. Ela entra pelo relógio, que é justamente o
   * que a troca preserva.
   */
  useEffect(() => {
    const chegada = recemChegada.current;
    if (!chegada) return;
    const sequencia = reordenacaoDe(reordenacao.reordens, chegada.tecnico, dia);
    if (!sequencia) { recemChegada.current = null; return; }
    const ordens = ordensDoDia(base, chegada.tecnico, dia);
    if (!ordens.some((a) => a.operation_id === chegada.operationId)) return;
    recemChegada.current = null;
    reordenacao.absorver(
      chegada.tecnico, dia, inserirPeloRelogio(sequencia.sequencia, ordens, chegada.operationId),
    );
  }, [base, dia, reordenacao]);

  /**
   * O mesmo problema da troca, para quem chega de outro dia — e a ordem pode
   * chegar num dia que não está aberto, então isto roda quando a pessoa navega
   * até lá. Absorver duas vezes não faz nada: quem já está na sequência sai fora.
   */
  useEffect(() => {
    remanejos
      .filter((r) => r.paraDia === dia)
      .forEach((r) => {
        const sequencia = reordenacaoDe(reordenacao.reordens, r.paraTecnico, dia);
        if (!sequencia || sequencia.sequencia.includes(r.operation_id)) return;
        const ordens = ordensDoDia(base, r.paraTecnico, dia);
        if (!ordens.some((a) => a.operation_id === r.operation_id)) return;
        reordenacao.absorver(
          r.paraTecnico, dia, inserirPeloRelogio(sequencia.sequencia, ordens, r.operation_id),
        );
      });
  }, [remanejos, base, dia, reordenacao]);

  function sequenciar(tecnico: string, de: number, para: number) {
    const coluna = colunas.find((c) => c.tecnico === tecnico);
    if (!coluna || de === para) return;
    const ids = coluna.ordens.map((a) => a.operation_id);
    reordenacao.definir(tecnico, dia, mover(ids, de, para));
  }

  function pedirTroca(operationId: string, de: string, para: string) {
    const ordem = schedule.assignments.find((a) => a.operation_id === operationId);
    if (!ordem) return;
    limparErro();
    setPedido({ operationId, de, para, duracao: minutosDe(ordem) });
  }

  function soltar(tecnico: string, posicao: number | null) {
    const emCurso = arraste.arraste;
    if (!emCurso) return;
    if (emCurso.tecnico === tecnico) {
      const coluna = colunas.find((c) => c.tecnico === tecnico);
      const ultima = (coluna?.ordens.length ?? 1) - 1;
      sequenciar(tecnico, emCurso.posicao, posicao ?? ultima);
    } else {
      pedirTroca(emCurso.operationId, emCurso.tecnico, tecnico);
    }
    arraste.terminar();
  }

  function teclado(tecnico: string, operationId: string, posicao: number, event: KeyboardEvent) {
    if (!event.altKey) return;
    const indice = colunas.findIndex((c) => c.tecnico === tecnico);
    if (event.key === 'ArrowUp') { event.preventDefault(); sequenciar(tecnico, posicao, posicao - 1); }
    if (event.key === 'ArrowDown') { event.preventDefault(); sequenciar(tecnico, posicao, posicao + 1); }
    if (event.key === 'ArrowLeft' && indice > 0) {
      event.preventDefault();
      pedirTroca(operationId, tecnico, colunas[indice - 1].tecnico);
    }
    if (event.key === 'ArrowRight' && indice < colunas.length - 1) {
      event.preventDefault();
      pedirTroca(operationId, tecnico, colunas[indice + 1].tecnico);
    }
  }

  async function confirmarTroca(quem: string, motivo: string) {
    if (!pedido) return;
    const ok = await trocar({
      operation_id: pedido.operationId, de: pedido.de, para: pedido.para, motivo, quem,
    });
    // Recusado pela API, o cartão fica onde estava: a tela não afirma o que o
    // banco não tem. O erro aparece no próprio popover.
    if (!ok) return;
    recemChegada.current = { operationId: pedido.operationId, tecnico: pedido.para };
    setPedido(null);
  }

  /**
   * Com quatorze colunas, o destino costuma estar fora da tela quando o arraste
   * começa. O próprio `dragover` dispara sem parar enquanto o cursor se mexe, o
   * que dispensa um timer — e um timer sobreviveria ao fim do arraste.
   */
  function rolarNaBorda(event: DragEvent<HTMLDivElement>) {
    const caixa = trilho.current?.getBoundingClientRect();
    if (!caixa || !arraste.arraste) return;
    const margem = 64;
    if (event.clientX < caixa.left + margem) trilho.current?.scrollBy({ left: -24 });
    if (event.clientX > caixa.right - margem) trilho.current?.scrollBy({ left: 24 });
  }

  return (
    <>
      <div className="quadro" ref={trilho} onDragOver={rolarNaBorda}>
        {colunas.map((coluna) => (
          <ColunaTecnico
            key={coluna.tecnico}
            coluna={coluna}
            titulos={titulos}
            trocas={trocas}
            remanejos={remanejos}
            inicioOriginal={inicioOriginal}
            ativa={ativa}
            arraste={arraste.arraste}
            alvo={arraste.alvo}
            popover={pedido?.para === coluna.tecnico ? (
              <PopoverTroca
                de={pedido.de}
                para={pedido.para}
                duracao={pedido.duracao}
                cargaDestino={coluna.minutos}
                escalaDestino={coluna.escala}
                gravando={gravando}
                erro={erro}
                onConfirmar={confirmarTroca}
                onCancelar={() => { limparErro(); setPedido(null); }}
              />
            ) : null}
            onAbrirOrdem={onAbrirOrdem}
            onArrastarInicio={(operationId, posicao) => {
              arraste.comecar(operationId, coluna.tecnico, posicao);
            }}
            onArrastarSobre={(posicao) => arraste.mirar(coluna.tecnico, posicao)}
            onSoltar={(posicao) => soltar(coluna.tecnico, posicao)}
            onArrastarFim={arraste.terminar}
            onTeclado={(operationId, posicao, event) => (
              teclado(coluna.tecnico, operationId, posicao, event)
            )}
          />
        ))}
      </div>

      <BarraSequencia
        pendencias={pendencias}
        gravando={reordenacao.gravando}
        erro={reordenacao.erro}
        onDesfazer={(tecnico) => reordenacao.desfazer(tecnico, dia)}
        onRegistrar={(tecnico, quem, motivo) => {
          const pendencia = pendencias.find((p) => p.tecnico === tecnico);
          if (!pendencia) return;
          reordenacao.registrar({ tecnico, dia, motivo, quem, mudancas: pendencia.decididas });
        }}
      />
    </>
  );
}
