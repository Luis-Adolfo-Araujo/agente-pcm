import type { Assignment, Backlog, Capacity, Enriched, Schedule, Unscheduled } from '@/lib/api';

/**
 * O dia de uma alocação vem da string ISO, não de `new Date`: a janela carrega o
 * fuso do recorte, e converter para UTC joga a ordem da madrugada para o dia
 * anterior.
 */
export function diaDe(iso: string): string {
  return iso.slice(0, 10);
}

/** Dias do período, do primeiro ao último. `period.end` é exclusivo. */
export function diasDoPeriodo(inicioISO: string, fimISO: string): string[] {
  const [ai, am, ad] = diaDe(inicioISO).split('-').map(Number);
  const [fi, fm, fd] = diaDe(fimISO).split('-').map(Number);
  // Meio-dia local evita que horário de verão empurre a data para o vizinho.
  const cursor = new Date(ai, am - 1, ad, 12);
  const fim = new Date(fi, fm - 1, fd, 12);
  const dias: string[] = [];
  while (cursor < fim && dias.length < 62) {
    const mes = String(cursor.getMonth() + 1).padStart(2, '0');
    const dia = String(cursor.getDate()).padStart(2, '0');
    dias.push(`${cursor.getFullYear()}-${mes}-${dia}`);
    cursor.setDate(cursor.getDate() + 1);
  }
  return dias;
}

export function rotuloDia(dia: string): { nome: string; numero: string } {
  const [ano, mes, d] = dia.split('-').map(Number);
  const data = new Date(ano, mes - 1, d, 12);
  return {
    nome: data.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', ''),
    numero: `${String(d).padStart(2, '0')}/${String(mes).padStart(2, '0')}`,
  };
}

/** O dia por extenso, para o cabeçalho do modal. */
export function diaExtenso(dia: string): string {
  const [ano, mes, d] = dia.split('-').map(Number);
  return new Date(ano, mes - 1, d, 12).toLocaleDateString('pt-BR', {
    weekday: 'long',
    day: '2-digit',
    month: '2-digit',
  });
}

export function minutosEntre(inicio: string, fim: string): number {
  return Math.max(0, (new Date(fim).getTime() - new Date(inicio).getTime()) / 60000);
}

export function minutosDe(a: Assignment): number {
  return minutosEntre(a.window.start, a.window.end);
}

export function horas(minutos: number): string {
  return `${(minutos / 60).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}h`;
}

/** Minutos de escala declarada de um executante num dia. Cada slot é um dia. */
export function escalaDoDia(capacidades: Capacity[], tecnico: string, dia: string): number {
  const capacidade = capacidades.find((c) => c.worker_id === tecnico);
  if (!capacidade) return 0;
  return capacidade.slots
    .filter((slot) => diaDe(slot.window.start) === dia)
    .reduce((soma, slot) => soma + minutosEntre(slot.window.start, slot.window.end), 0);
}

export function carga(ordens: Assignment[]): number {
  return ordens.reduce((soma, a) => soma + minutosDe(a), 0);
}

/** Acima de 12h num único dia nenhuma escala fecha, nem a 12x36. */
export function escalaImpossivel(minutos: number): boolean {
  return minutos > 12 * 60;
}

/**
 * As três abas da semana precisam responder pela mesma ordem sem varrer 2,5 mil
 * itens cada vez que alguém abre um modal.
 */
export type Indice = {
  enriched: Map<string, Enriched>;
  alocada: Map<string, Assignment>;
  fora: Map<string, Unscheduled>;
  titulos: Map<string, string>;
};

export function indexar(backlog: Backlog, schedule: Schedule): Indice {
  const enriched = new Map<string, Enriched>();
  const titulos = new Map<string, string>();
  backlog.backlog.forEach((item) => {
    enriched.set(item.operation.operation_id, item);
    titulos.set(item.operation.operation_id, item.operation.title);
  });
  const alocada = new Map<string, Assignment>();
  schedule.assignments.forEach((a) => alocada.set(a.operation_id, a));
  const fora = new Map<string, Unscheduled>();
  schedule.unscheduled.forEach((u) => fora.set(u.operation_id, u));
  return { enriched, alocada, fora, titulos };
}

/** Quem pode receber a ordem: todo mundo com escala declarada naquele dia. */
export function tecnicosComEscala(capacidades: Capacity[], dia: string): string[] {
  return capacidades
    .filter((c) => c.slots.some((slot) => diaDe(slot.window.start) === dia))
    .map((c) => c.worker_id)
    .sort((a, b) => a.localeCompare(b));
}
