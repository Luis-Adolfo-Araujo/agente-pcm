import { demoApi } from '@/lib/demo';

export const BASE = process.env.NEXT_PUBLIC_API ?? 'http://localhost:8000';
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? '';

/** Erro que carrega o status e o detalhe: sem eles, 401, 409 e API fora do ar viram a mesma frase. */
export class ApiError extends Error {
  constructor(readonly status: number, readonly path: string, readonly detalhe: unknown = null) {
    super(`${status} em ${path}`);
    this.name = 'ApiError';
  }
}

function headers(extra?: Record<string, string>): Record<string, string> {
  return {
    ...extra,
    ...(TOKEN ? { authorization: `Bearer ${TOKEN}` } : {}),
  };
}

async function falha(response: Response, path: string): Promise<ApiError> {
  let detalhe: unknown = null;
  try {
    detalhe = ((await response.json()) as { detail?: unknown }).detail ?? null;
  } catch {
    // Corpo sem JSON: o status sozinho já diz o bastante.
  }
  return new ApiError(response.status, path, detalhe);
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { cache: 'no-store', headers: headers() });
  if (!response.ok) throw await falha(response, path);
  return response.json() as Promise<T>;
}

async function enviar<T>(metodo: 'POST' | 'DELETE', path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: metodo,
    headers: headers(body === undefined ? undefined : { 'content-type': 'application/json' }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw await falha(response, path);
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) => enviar<T>('POST', path, body);
const del = <T>(path: string) => enviar<T>('DELETE', path);

export type Indicator = {
  key: string; present: number; total: number; missing: number; coverage_percent: number;
};
export type BacklogStatusRow = {
  status: string; total: number; available: number; blocked: number;
};
export type BacklogComposition = {
  total: number; available: number; blocked: number;
  by_status: BacklogStatusRow[];
  by_planning_status: Record<string, number>;
};
export type Snapshot = {
  snapshot_id: string; tenant_id: string; as_of: string; sha256: string;
  /** De onde o extrato veio. Ausente em API anterior a este campo. */
  source?: string | null;
  quality: {
    operation_count: number;
    /** Ausente em API mais antiga que esta tela. Ver `composicaoDoBacklog`. */
    backlog?: BacklogComposition;
    worker_count: number; inventory_item_count: number;
    historical_execution_count: number; availability_slot_count: number;
    material_requirement_count: number; rejected_record_count: number;
    indicators: Indicator[];
  };
};
/**
 * A composição pode faltar: a API do piloto sobe como processo longo, e uma que
 * não foi reiniciada depois do contrato novo devolve `quality` sem `backlog`.
 * Quebrar a etapa inteira num TypeError esconde justamente essa informação, que
 * é a única acionável — então a ausência vira estado, não exceção.
 */
export function composicaoDoBacklog(quality: Snapshot['quality']): BacklogComposition & { parcial: boolean } {
  if (quality.backlog) return { ...quality.backlog, parcial: false };
  return {
    total: quality.operation_count,
    available: quality.operation_count,
    blocked: 0,
    by_status: [],
    by_planning_status: {},
    parcial: true,
  };
}

export type StageTrace = { sequence: number; stage: string; elapsed_ms: number; counts: Record<string, number> };
/** Só o que o trace exibe. O backend manda mais; o resto não precisa de tipo aqui. */
export type RunConfig = {
  ranking?: Record<string, unknown>;
  duration?: Record<string, unknown>;
  materials?: Record<string, unknown>;
  executants?: Record<string, unknown>;
  optimizer?: Record<string, unknown>;
};
export type Run = {
  run_id: string; snapshot_id: string; status: string; created_at: string;
  current_stage: string | null; trace_events: StageTrace[];
  config?: RunConfig;
  error?: string | null;
  request: {
    period: { start: string; end: string };
    ruleset_version?: string;
    weights_version?: string;
  };
  summary: null | {
    assignments: number; unscheduled: number; violations: number;
    verification_valid: boolean; proposal_status: string;
  };
  decision: null | { decision: string; decided_by: string; reason: string; decided_at: string };
};
export type Coverage = {
  total_operations: number; scheduled_operations: number; unscheduled_operations: number;
  capacity_limited_operations: number; demand_minutes: number; available_minutes: number;
  coverage_percent: number; reasons: Record<string, number>;
};
export type Assignment = {
  work_order_id: string; operation_id: string; worker_ids: string[];
  window: { start: string; end: string }; priority_score: number; reason_codes: string[];
};
export type Unscheduled = { work_order_id: string; operation_id: string; reason: string; details: string[] };
export type Schedule = {
  status: string; assignments: Assignment[]; unscheduled: Unscheduled[]; coverage: Coverage;
};
export type Enriched = {
  operation: {
    work_order_id: string; operation_id: string; title: string; priority_level: number | null;
    criticality: number | null; asset_id: string | null; location_id: string | null;
    planned_duration_minutes: number | null; due_at: string | null;
  };
  priority: {
    score: number; band: string; model: string; reason_codes: string[]; missing_fields: string[];
    components: { name: string; raw_value: number; normalized_value: number; weight: number; contribution: number }[];
  };
  duration: { minutes: number | null; p50_minutes: number | null; p80_minutes: number | null; source: string; sample_size: number; confidence: number };
  materials: { status: string; blocking: boolean; reason_codes: string[] };
  executants: { worker_id: string; score: number; eligible: boolean; available_minutes: number; reason_codes: string[] }[];
  scheduled: boolean;
};
export type CapacitySlot = { worker_id: string; window: { start: string; end: string } };
export type Capacity = {
  worker_id: string; gross_minutes: number; committed_minutes: number; net_minutes: number;
  slots: CapacitySlot[];
};
export type Backlog = { backlog: Enriched[]; capacities: Capacity[] };
export type Violation = {
  code: string; severity: string; details: string; operation_id: string | null; worker_id?: string | null;
};
export type Verification = { valid: boolean; input_hash: string; violations: Violation[] };
export type FeedbackSkill = 'ranking' | 'duration' | 'materials' | 'executants' | 'schedule';
export type FeedbackVerdict = 'correct' | 'acceptable' | 'incorrect';
export type FeedbackItem = {
  operation_id: string; skill: FeedbackSkill; verdict: FeedbackVerdict; reason: string;
};
export type FeedbackRecord = FeedbackItem & {
  feedback_id: string; run_id: string; snapshot_id: string; recorded_by: string; recorded_at: string;
};

export type TipoDeAjuste = 'move' | 'remove' | 'include' | 'duration' | 'unavailable';
export type Causa = 'vacation' | 'sick_leave' | 'other';

/** Um ajuste gravado. Os campos que o tipo não usa vêm `null`. */
export type Ajuste = {
  sequence: number; group: number; kind: TipoDeAjuste;
  operation_id: string | null; target_date: string | null; target_worker_id: string | null;
  target_start: string | null; replace_worker_id: string | null; minutes: number | null;
  worker_id: string | null; date_from: string | null; date_to: string | null; cause: Causa | null;
  reason: string | null; applied_by: string; applied_at: string;
};

/** O que a tela pede: só os campos do tipo, sem numeração nem autor. */
export type RascunhoDeAjuste = {
  kind: TipoDeAjuste;
  operation_id?: string; target_date?: string; target_worker_id?: string; target_start?: string;
  replace_worker_id?: string; minutes?: number;
  worker_id?: string; date_from?: string; date_to?: string; cause?: Causa;
};

export type Solucao = { status: string; assignments: Assignment[]; unscheduled: Unscheduled[] };

export type Revisao = {
  run_id: string; revision_sequence: number; groups: number; adjustments: Ajuste[];
  solution: Solucao; verification: Verification;
  created_violations: Violation[]; inherited_violations: Violation[];
  capacities: Capacity[]; duration_overrides: Record<string, number>;
};

export type Lugar = { date: string; start: string; worker_ids: string[] };

export type Consequencia = {
  id: string; adjustment: Ajuste; default_accepted: boolean; accepted: boolean; locked: boolean;
  reason_code: string; if_rejected: 'remove' | 'stay'; from: Lugar | null; to: Lugar | null;
};

export type CargaQueMuda = {
  worker_id: string; date: string; before_minutes: number; after_minutes: number; shift_minutes: number;
};

export type Previa = {
  run_id: string; base_revision: number; consequences: Consequencia[]; load: CargaQueMuda[];
  violations: { created: Violation[]; resolved: Violation[] }; notes: string[];
};

export type PedidoDeAjuste = {
  actions: RascunhoDeAjuste[]; rejected: string[]; accepted: string[]; expected_revision: number;
};

export type FeedbackDoAjuste = { operation_id: string; skill: FeedbackSkill; reason: string };

export type ConfirmacaoDeAjuste = PedidoDeAjuste & {
  recorded_by: string; reason: string | null; feedback: FeedbackDoAjuste[];
};

const apiHttp = {
  snapshots: () => get<Snapshot[]>('/api/snapshots'),
  runs: () => get<Run[]>('/api/runs'),
  run: (id: string) => get<Run>(`/api/runs/${id}`),
  backlog: (id: string) => get<Backlog>(`/api/runs/${id}/backlog`),
  schedule: (id: string) => get<Schedule>(`/api/runs/${id}/schedule`),
  verification: (id: string) => get<Verification>(`/api/runs/${id}/verification`),
  startRun: (body: { snapshot_id: string; period_start: string; period_end: string }) =>
    post<Run>('/api/runs', body),
  decide: (id: string, body: { decision: string; decided_by: string; reason: string; revision_sequence: number }) =>
    post<Run>(`/api/runs/${id}/decision`, body),
  revision: (id: string) => get<Revisao>(`/api/runs/${id}/revision`),
  previewAdjustments: (id: string, body: PedidoDeAjuste) =>
    post<Previa>(`/api/runs/${id}/adjustments/preview`, body),
  confirmAdjustments: (id: string, body: ConfirmacaoDeAjuste) =>
    post<Revisao>(`/api/runs/${id}/adjustments`, body),
  undoAdjustments: (id: string) => del<Revisao>(`/api/runs/${id}/adjustments/last`),
  feedback: (id: string, body: { recorded_by: string; items: FeedbackItem[] }) =>
    post<FeedbackRecord[]>(`/api/runs/${id}/feedback`, body),
};

/**
 * Na demonstração pública não há API atrás da página: os artefatos foram
 * gerados uma vez pelo agente e viajam como arquivo estático. A tela não
 * sabe da diferença — as duas implementações têm a mesma forma.
 */
const DEMONSTRACAO = (process.env.NEXT_PUBLIC_DEMO ?? '') === '1';

export const api = DEMONSTRACAO ? demoApi : apiHttp;

/**
 * De onde a base saiu, em palavra de gente. O nome da origem é dado do
 * snapshot, não do código: escrever "Tractian" fixo na tela mentia sobre
 * qualquer outra origem, a começar pelo mundo fictício da demonstração.
 */
export function origemDoSnapshot(snapshot: Snapshot): string {
  const rotulos: Record<string, string> = {
    sintetico: 'dado fictício',
    tractian: 'Tractian',
  };
  const chave = (snapshot.source ?? '').trim().toLowerCase();
  return rotulos[chave] ?? (chave || 'origem não declarada');
}

/** Quem está mexendo. Perguntar a cada troca seria pedágio; o piloto é de uma pessoa por vez. */
const CHAVE_QUEM = 'maia.quem';

export function quemSalvo(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem(CHAVE_QUEM) ?? '';
}

export function salvarQuem(nome: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(CHAVE_QUEM, nome.trim());
}

export const STAGE_NAMES: Record<string, string> = {
  snapshot_validated: 'Dados validados',
  skills_parallel: 'Skills em paralelo',
  'skill.rank_backlog': 'Priorização do backlog',
  'skill.estimate_duration': 'Estimativa de duração',
  'skill.check_materials': 'Conferência de material',
  'skill.calculate_capacity': 'Cálculo de capacidade',
  executant_candidates: 'Candidatos a executante',
  optimization: 'Otimização',
  verification: 'Verificação',
  proposal_ready: 'Semana pronta',
};

/** Os contadores do trace saem com nome de campo; na tela eles precisam de nome de gente. */
export const CONTAGEM_NOMES: Record<string, string> = {
  history: 'execuções no histórico',
  inventory: 'itens de estoque',
  operations: 'operações',
  workers: 'pessoas',
  priorities: 'scores',
  durations: 'durações',
  materials: 'materiais conferidos',
  capacities: 'capacidades',
  candidates: 'candidatos',
  assignments: 'alocadas',
  unscheduled: 'fora da semana',
  violations: 'violações',
  proposals: 'proposta',
};

export function resumoContagens(counts: Record<string, number>): string {
  return Object.entries(counts)
    .map(([chave, valor]) => `${valor.toLocaleString('pt-BR')} ${CONTAGEM_NOMES[chave] ?? chave}`)
    .join(' · ');
}

/** Os estágios de topo, na ordem em que a execução acontece. */
export const ESTAGIOS_PRINCIPAIS = [
  'snapshot_validated',
  'skills_parallel',
  'executant_candidates',
  'optimization',
  'verification',
  'proposal_ready',
] as const;

/** Ordem de leitura do funil. As quatro skills paralelas moram dentro de skills_parallel. */
export const SKILLS_PARALELAS = [
  'skill.rank_backlog',
  'skill.estimate_duration',
  'skill.check_materials',
  'skill.calculate_capacity',
] as const;

export const REASON_NAMES: Record<string, string> = {
  no_capacity: 'Sem hora-homem disponível',
  blocked: 'Ordem bloqueada na origem',
  material: 'Material bloqueador',
  duration: 'Sem duração utilizável',
  no_executant: 'Sem executante compatível',
  outside_window: 'Fora da janela operacional',
  outside_period: 'Fora do período',
  manual: 'Tirada da semana pelo PCM',
};

export function hhmm(minutes: number): string {
  return `${Math.round(minutes / 60).toLocaleString('pt-BR')} HH`;
}
export function dia(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}
export function hora(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}
export function segundos(ms: number): string {
  return ms >= 1000
    ? `${(ms / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`
    : `${Math.round(ms).toLocaleString('pt-BR')} ms`;
}
