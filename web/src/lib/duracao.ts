/**
 * "1:30" → 90. Só h:mm, de 0:01 a 24:00 — a mesma fronteira que a API aceita.
 * Aceitar "90" deixaria em dúvida se são minutos ou horas.
 */
export function lerHhmm(texto: string): number | null {
  const achado = texto.trim().match(/^(\d{1,2}):([0-5]\d)$/);
  if (!achado) return null;
  const minutos = Number(achado[1]) * 60 + Number(achado[2]);
  return minutos >= 1 && minutos <= 24 * 60 ? minutos : null;
}

export function escreverHhmm(minutos: number): string {
  return `${Math.floor(minutos / 60)}:${String(minutos % 60).padStart(2, '0')}`;
}
