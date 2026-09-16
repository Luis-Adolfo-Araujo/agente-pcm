import type { Backlog, Enriched, Schedule, Unscheduled } from '@/lib/api';

/**
 * O recorte da aba Fora da semana. Todos os campos saem do que a API já
 * devolve; não há filtro de equipe ou certificação porque esses campos não
 * existem no contrato.
 */
export type FiltroBacklog = {
  busca: string;
  motivo: string;
  local: string;
  faixa: string;
  /** Texto do campo: vazio é "sem mínimo". */
  scoreMinimo: string;
  material: string;
  bloqueador: '' | 'sim' | 'nao';
  venceNoPeriodo: boolean;
  tecnico: string;
};

export const SEM_FILTRO_BACKLOG: FiltroBacklog = {
  busca: '', motivo: '', local: '', faixa: '', scoreMinimo: '',
  material: '', bloqueador: '', venceNoPeriodo: false, tecnico: '',
};

export type LinhaBacklog = { fora: Unscheduled; item: Enriched | null };

/** Quem ficou de fora da semana, com o que o agente sabe de cada um, por prioridade. */
export function linhasDoBacklog(semana: Schedule, backlog: Backlog): LinhaBacklog[] {
  const porId = new Map(backlog.backlog.map((item) => [item.operation.operation_id, item]));
  return semana.unscheduled
    .map((fora) => ({ fora, item: porId.get(fora.operation_id) ?? null }))
    .sort((a, b) => (
      (b.item?.priority.score ?? -1) - (a.item?.priority.score ?? -1)
      || a.fora.operation_id.localeCompare(b.fora.operation_id)
    ));
}

/** Sem acento e sem caixa: quem digita "mecanico" quer achar "mecânico". */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

export function filtrando(filtro: FiltroBacklog): boolean {
  return (Object.keys(SEM_FILTRO_BACKLOG) as (keyof FiltroBacklog)[])
    .some((chave) => filtro[chave] !== SEM_FILTRO_BACKLOG[chave]);
}

export function filtrarBacklog(
  linhas: LinhaBacklog[],
  filtro: FiltroBacklog,
  periodo: { start: string; end: string },
): LinhaBacklog[] {
  const busca = normalizar(filtro.busca.trim());
  const minimo = filtro.scoreMinimo.trim() === '' ? null : Number(filtro.scoreMinimo.replace(',', '.'));
  const inicio = new Date(periodo.start).getTime();
  // `period.end` é exclusivo: o que vence à meia-noite do dia seguinte já é outra semana.
  const fim = new Date(periodo.end).getTime();
  const dependeDoItem = !!filtro.local || !!filtro.faixa || minimo !== null || !!filtro.material
    || !!filtro.bloqueador || filtro.venceNoPeriodo || !!filtro.tecnico;

  return linhas.filter(({ fora, item }) => {
    if (filtro.motivo && fora.reason !== filtro.motivo) return false;
    if (busca) {
      const titulo = normalizar(item?.operation.title ?? '');
      const os = normalizar(item?.operation.work_order_id ?? fora.work_order_id);
      if (!titulo.includes(busca) && !os.includes(busca)) return false;
    }
    if (!item) return !dependeDoItem;
    if (filtro.local && item.operation.location_id !== filtro.local) return false;
    if (filtro.faixa && item.priority.band !== filtro.faixa) return false;
    if (minimo !== null && !Number.isNaN(minimo) && item.priority.score < minimo) return false;
    if (filtro.material && item.materials.status !== filtro.material) return false;
    if (filtro.bloqueador === 'sim' && !item.materials.blocking) return false;
    if (filtro.bloqueador === 'nao' && item.materials.blocking) return false;
    if (filtro.venceNoPeriodo) {
      if (!item.operation.due_at) return false;
      const vence = new Date(item.operation.due_at).getTime();
      if (vence < inicio || vence >= fim) return false;
    }
    if (filtro.tecnico && !item.executants.some((e) => e.eligible && e.worker_id === filtro.tecnico)) {
      return false;
    }
    return true;
  });
}

export type OpcoesDoBacklog = {
  motivos: string[];
  locais: string[];
  faixas: string[];
  materiais: string[];
  tecnicos: string[];
};

/** As opções de cada filtro, só com o que existe nas ordens de fora. */
export function opcoesDoBacklog(linhas: LinhaBacklog[]): OpcoesDoBacklog {
  const distintos = (valores: (string | null | undefined)[]) => (
    [...new Set(valores.filter((v): v is string => !!v))].sort((a, b) => a.localeCompare(b))
  );
  return {
    motivos: distintos(linhas.map((l) => l.fora.reason)),
    locais: distintos(linhas.map((l) => l.item?.operation.location_id)),
    faixas: distintos(linhas.map((l) => l.item?.priority.band)),
    materiais: distintos(linhas.map((l) => l.item?.materials.status)),
    tecnicos: distintos(linhas.flatMap((l) => (l.item?.executants ?? [])
      .filter((e) => e.eligible)
      .map((e) => e.worker_id))),
  };
}

/** Quantas ordens de fora há por motivo. Conta todas: o filtro esconde linha, não reescreve número. */
export function contagemPorMotivo(linhas: LinhaBacklog[]): [string, number][] {
  const conta = new Map<string, number>();
  linhas.forEach((l) => conta.set(l.fora.reason, (conta.get(l.fora.reason) ?? 0) + 1));
  return [...conta.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
