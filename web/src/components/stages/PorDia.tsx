'use client';
import { useMemo, useState } from 'react';
import { EmptyState } from '@/components/ui';
import { Quadro } from '@/components/quadro/Quadro';
import { PopoverRemanejo, type DestinoDoDia } from '@/components/quadro/PopoverRemanejo';
import type { useArraste } from '@/components/quadro/useArraste';
import type { useReordens } from '@/components/sessao/useReordens';
import type { useRemanejos } from '@/components/sessao/useRemanejos';
import type { Pedido } from '@/components/sessao/useTrocas';
import type { Assignment, Backlog, Run, Schedule } from '@/lib/api';
import {
  carga, diaDe, diasDoPeriodo, escalaDoDia, horas, minutosDe, rotuloDia, tecnicosComEscala,
} from '@/lib/semana';
import { colunasDoDia } from '@/lib/quadro';
import { inicioNoDia } from '@/lib/remanejos';
import type { Troca } from '@/lib/trocas';

/** Um cartão solto num chip do trilho, esperando quem recebe e a que horas. */
type PedidoDeDia = { operationId: string; deTecnico: string; paraDia: string };

export function PorDia({
  run, schedule, base, backlog, trocas, titulos, ativa, onAbrirOrdem,
  dia: diaEscolhido, onMudarDia, arraste,
  reordenacao, remanejo, trocar, gravando, erro, limparErro,
}: {
  run: Run;
  /** A semana com trocas, movimentos e sequências da sessão por cima. */
  schedule: Schedule;
  /** A mesma semana antes de reordenar, para dizer que horário a ordem tinha. */
  base: Schedule;
  backlog: Backlog;
  trocas: Troca[];
  titulos: Map<string, string>;
  /** A ordem aberta no modal, para o cartão dela ficar marcado. */
  ativa: string | null;
  onAbrirOrdem: (operationId: string) => void;
  /** O dia aberto. Vazio significa "escolha por mim": o primeiro com trabalho. */
  dia: string;
  onMudarDia: (dia: string) => void;
  /** O arraste em curso, o mesmo da matriz semanal. */
  arraste: ReturnType<typeof useArraste>;
  reordenacao: ReturnType<typeof useReordens>;
  remanejo: ReturnType<typeof useRemanejos>;
  trocar: (pedido: Pedido) => Promise<boolean>;
  gravando: boolean;
  erro: string | null;
  limparErro: () => void;
}) {
  const dias = useMemo(
    () => diasDoPeriodo(run.request.period.start, run.request.period.end),
    [run],
  );

  const porDia = useMemo(() => {
    const mapa = new Map<string, Assignment[]>();
    schedule.assignments.forEach((a) => {
      const dia = diaDe(a.window.start);
      mapa.set(dia, [...(mapa.get(dia) ?? []), a]);
    });
    return mapa;
  }, [schedule]);

  // Sem dia escolhido, abre no primeiro que tem trabalho: um dia vazio como tela
  // inicial esconderia a semana inteira atrás de um clique.
  const padrao = useMemo(
    () => dias.find((d) => (porDia.get(d)?.length ?? 0) > 0) ?? dias[0] ?? '',
    [dias, porDia],
  );
  const dia = diaEscolhido || padrao;

  // O chip sob o cursor durante o arraste, e a ordem que caiu num deles.
  const [diaAlvo, setDiaAlvo] = useState<string | null>(null);
  const [pedido, setPedido] = useState<PedidoDeDia | null>(null);
  // Depois de mover, a ordem sai desta tela: o quadro mostra um dia por vez.
  const [movida, setMovida] = useState<{ operationId: string; paraDia: string } | null>(null);

  const doDia = useMemo(() => porDia.get(dia) ?? [], [porDia, dia]);
  const pessoas = useMemo(
    () => colunasDoDia(schedule.assignments, backlog.capacities, dia, trocas, remanejo.remanejos).length,
    [schedule, backlog, dia, trocas, remanejo.remanejos],
  );

  const ordemDoPedido = pedido
    ? schedule.assignments.find((a) => a.operation_id === pedido.operationId) ?? null
    : null;

  /** Quem pode receber a ordem no dia destino, com a carga que já tem lá. */
  const destinos = useMemo((): DestinoDoDia[] => {
    if (!pedido) return [];
    return tecnicosComEscala(backlog.capacities, pedido.paraDia).map((worker_id) => ({
      worker_id,
      carga: carga(schedule.assignments.filter(
        (a) => diaDe(a.window.start) === pedido.paraDia && a.worker_ids.includes(worker_id),
      )),
      escala: escalaDoDia(backlog.capacities, worker_id, pedido.paraDia),
    }));
  }, [pedido, backlog, schedule]);

  async function confirmarRemanejo(paraTecnico: string, hhmm: string, quem: string, motivo: string) {
    if (!pedido || !ordemDoPedido) return;
    const ok = await remanejo.remanejar({
      operation_id: pedido.operationId,
      deDia: dia,
      deInicio: ordemDoPedido.window.start,
      deTecnico: pedido.deTecnico,
      paraDia: pedido.paraDia,
      paraInicio: inicioNoDia(ordemDoPedido.window.start, pedido.paraDia, hhmm),
      paraTecnico,
      motivo,
      quem,
    });
    // Recusado pela API, a ordem fica no dia em que estava: a tela não afirma o
    // que o banco não tem. O erro aparece no próprio popover.
    if (!ok) return;
    setMovida({ operationId: pedido.operationId, paraDia: pedido.paraDia });
    setPedido(null);
  }

  if (dias.length === 0) return <EmptyState title="Este recorte não tem período" />;

  return (
    <>
      <nav className="trilho-dias" aria-label="Dias da semana">
        {dias.map((d) => {
          const ordens = porDia.get(d) ?? [];
          const rotulo = rotuloDia(d);
          return (
            <button
              key={d}
              type="button"
              className="chip-dia"
              data-estado={d === dia ? 'ativo' : ordens.length === 0 ? 'vazio' : undefined}
              data-alvo={diaAlvo === d && d !== dia ? 'sim' : undefined}
              aria-current={d === dia ? 'true' : undefined}
              onClick={() => onMudarDia(d)}
              onDragOver={(event) => {
                if (!arraste.arraste) return;
                event.preventDefault();
                setDiaAlvo(d);
              }}
              onDragLeave={() => setDiaAlvo((atual) => (atual === d ? null : atual))}
              onDrop={(event) => {
                const emCurso = arraste.arraste;
                if (!emCurso) return;
                event.preventDefault();
                // Soltar no dia em que a ordem já está não é um movimento.
                if (d !== dia) {
                  remanejo.limparErro();
                  setPedido({
                    operationId: emCurso.operationId, deTecnico: emCurso.tecnico, paraDia: d,
                  });
                }
                arraste.terminar();
                setDiaAlvo(null);
              }}
            >
              <span className="chip-dia-nome">{rotulo.nome} {rotulo.numero}</span>
              <span className="chip-dia-nota">
                {ordens.length === 0 ? 'sem alocação' : `${ordens.length} ordens`}
              </span>
              {ordens.length > 0 && <span className="chip-dia-nota">{horas(carga(ordens))} alocadas</span>}
            </button>
          );
        })}
      </nav>

      {pedido && ordemDoPedido && (
        <PopoverRemanejo
          deDia={dia}
          paraDia={pedido.paraDia}
          deTecnico={pedido.deTecnico}
          horaAtual={ordemDoPedido.window.start.slice(11, 16)}
          duracao={minutosDe(ordemDoPedido)}
          dividida={ordemDoPedido.worker_ids.length > 1}
          destinos={destinos}
          gravando={remanejo.gravando}
          erro={remanejo.erro}
          onConfirmar={confirmarRemanejo}
          onCancelar={() => { remanejo.limparErro(); setPedido(null); }}
        />
      )}

      {movida && (
        <p className="movida-nota">
          <span>
            A ordem <strong>{titulos.get(movida.operationId) || movida.operationId}</strong> foi
            para {rotuloDia(movida.paraDia).nome} {rotuloDia(movida.paraDia).numero}.
          </span>
          <button
            type="button"
            className="btn btn-menor"
            onClick={() => { onMudarDia(movida.paraDia); setMovida(null); }}
          >
            Ir para o dia
          </button>
          <button type="button" className="btn btn-menor" onClick={() => setMovida(null)}>
            Dispensar
          </button>
        </p>
      )}

      {doDia.length === 0 && pessoas === 0 ? (
        <EmptyState
          title="Nenhuma ordem neste dia"
          description="O agente não alocou nada aqui — normalmente porque ninguém tem escala no dia, ou porque a capacidade acabou nos dias anteriores."
        />
      ) : (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            {pessoas} {pessoas === 1 ? 'pessoa' : 'pessoas'} · {doDia.length}{' '}
            {doDia.length === 1 ? 'ordem' : 'ordens'} · {horas(carga(doDia))} alocadas.
            {' '}Abra um cartão para ver a conta que colocou a ordem ali, ou arraste um até outro
            dia do trilho.
          </p>

          <Quadro
            dia={dia}
            schedule={schedule}
            base={base}
            backlog={backlog}
            trocas={trocas}
            remanejos={remanejo.remanejos}
            titulos={titulos}
            ativa={ativa}
            onAbrirOrdem={onAbrirOrdem}
            arraste={arraste}
            reordenacao={reordenacao}
            trocar={trocar}
            gravando={gravando}
            erro={erro}
            limparErro={limparErro}
          />
        </>
      )}
    </>
  );
}
