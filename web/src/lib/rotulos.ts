/** Os nomes que o backend usa não são nomes de gente. Aqui é onde eles viram. */

export const FONTE: Record<string, string> = {
  planned: 'duração planejada da OS',
  same_activity_and_asset: 'histórico: mesma atividade e ativo',
  same_activity_and_location: 'histórico: mesma atividade e local',
  same_asset: 'histórico: mesmo ativo',
  same_activity: 'histórico: mesma atividade',
  same_location: 'histórico: mesmo local',
  similar_title: 'histórico: descrição parecida',
  global_median: 'mediana geral',
  default: 'valor assumido',
  unavailable: 'sem duração',
};

export const MATERIAL: Record<string, [string, 'good' | 'warn' | 'bad' | 'mute']> = {
  available: ['disponível', 'good'],
  partial: ['parcial', 'warn'],
  unavailable: ['sem saldo', 'bad'],
  unknown: ['sem informação', 'warn'],
};

export const BANDA: Record<string, string> = {
  very_high: 'muito alta', high: 'alta', medium: 'média', low: 'baixa',
};

export const FATOR: Record<string, string> = {
  priority: 'Prioridade da OS',
  age: 'Dias em aberto',
  sla: 'Prazo (SLA)',
  criticality: 'Criticidade do ativo',
};

/**
 * A contribuição sozinha não explica nada: 40,0 pode ser uma ordem vencida há um mês
 * ou uma que vence amanhã. O que a ordem tem de fato mora em `raw_value`, e a escala
 * de cada fator é `weight × 100`.
 */
export function valorNaOrdem(nome: string, bruto: number, codigos: string[]): string {
  if (nome === 'priority') {
    return codigos.includes('PRIORITY_MISSING') ? 'sem prioridade na origem' : `nível ${bruto.toFixed(0)}`;
  }
  if (nome === 'criticality') return `nível ${bruto.toFixed(0)}`;
  if (nome === 'age') {
    return bruto < 0 ? 'criada depois do corte' : `${Math.round(bruto).toLocaleString('pt-BR')} dias em aberto`;
  }
  if (nome === 'sla') {
    if (codigos.includes('SLA_MISSING')) return 'sem prazo cadastrado';
    if (codigos.includes('SLA_DUE_NOW')) return 'vence hoje';
    return bruto < 0
      ? `vencida há ${Math.abs(bruto).toFixed(0)} dias`
      : `vence em ${bruto.toFixed(0)} dias`;
  }
  return bruto.toFixed(1);
}

/** Status da ordem na origem. O agente lê o texto cru; a tela dá nome a ele. */
export const STATUS_OS: Record<string, { rotulo: string; nota: string }> = {
  open: { rotulo: 'Aberta', nota: 'não começou' },
  inProgress: { rotulo: 'Em andamento', nota: 'já começou e segue precisando de gente' },
  onHold: { rotulo: 'Em espera', nota: 'parada na origem' },
};

/** O que a origem já decidiu sobre programação, antes de o agente entrar. */
export const STATUS_PLANEJAMENTO: Record<string, string> = {
  unplanned: 'Sem programação na origem',
  scheduled: 'Já programada na origem',
  planned: 'Já planejada na origem',
  awaiting_scheduling: 'Aguardando programação',
  without_planning: 'Sem planejamento previsto',
};
