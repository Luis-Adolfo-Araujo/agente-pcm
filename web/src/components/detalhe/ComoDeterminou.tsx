'use client';
import { Badge } from '@/components/ui';
import { BANDA, FONTE, MATERIAL } from '@/lib/rotulos';
import { REASON_NAMES, dia, hora, type Assignment, type Enriched, type Unscheduled } from '@/lib/api';
import type { Troca } from '@/lib/trocas';

type Passo = {
  chave: string;
  nome: string;
  veredito: string;
  tone?: 'good' | 'warn' | 'bad' | 'mute';
  evidencia: string[];
  /** Códigos que o backend emite. São identificadores, e são lidos como tal. */
  codigos?: string[];
};

/**
 * O trace da etapa 2 conta o funil das 2,5 mil ordens. Aqui a mesma pergunta desce
 * para uma só: qual skill produziu cada número desta OS, e com que evidência.
 */
export function ComoDeterminou({ item, alocada, fora, troca }: {
  item: Enriched;
  alocada: Assignment | null;
  fora: Unscheduled | null;
  troca: Troca | null;
}) {
  const passos: Passo[] = [];

  const faltando = item.priority.missing_fields;
  passos.push({
    chave: 'ranking',
    nome: 'Priorização do backlog',
    veredito: `score ${item.priority.score.toFixed(1)} de 100 · prioridade ${BANDA[item.priority.band] ?? item.priority.band}`,
    tone: faltando.length > 0 ? 'warn' : 'good',
    evidencia: [
      `${item.priority.components.length} fatores pesados pelo modelo ${item.priority.model}.`,
      faltando.length > 0
        ? `Sem informação de: ${faltando.join(', ')}. A ausência ficou marcada — não virou valor baixo.`
        : 'Todos os fatores tinham dado na origem.',
    ],
    codigos: item.priority.reason_codes,
  });

  const d = item.duration;
  passos.push({
    chave: 'duration',
    nome: 'Estimativa de duração',
    veredito: d.minutes === null ? 'sem duração utilizável' : `${d.minutes} min · ${FONTE[d.source] ?? d.source}`,
    tone: d.minutes === null ? 'bad' : d.sample_size > 0 ? 'good' : 'warn',
    evidencia: d.sample_size > 0
      ? [
        `${d.sample_size.toLocaleString('pt-BR')} execuções comparáveis no histórico.`,
        `P50 ${d.p50_minutes ?? '—'} min · P80 ${d.p80_minutes ?? '—'} min.`,
        `Confiança ${(d.confidence * 100).toFixed(0)}%.`,
      ]
      : ['Sem histórico comparável. O número veio de regra, não de execução passada.'],
  });

  const [rotuloMaterial, toneMaterial] = MATERIAL[item.materials.status] ?? [item.materials.status, 'mute'];
  passos.push({
    chave: 'materials',
    nome: 'Conferência de material',
    veredito: rotuloMaterial,
    tone: toneMaterial,
    evidencia: [
      item.materials.blocking
        ? 'Este material bloqueia a execução: a ordem não entra na semana enquanto não houver saldo.'
        : 'Não bloqueia a execução.',
    ],
    codigos: item.materials.reason_codes,
  });

  const elegiveis = item.executants.filter((e) => e.eligible);
  const escolhido = alocada?.worker_ids ?? [];
  passos.push({
    chave: 'executants',
    nome: 'Candidatos a executante',
    veredito: item.executants.length === 0
      ? 'nenhum candidato compatível'
      : `${elegiveis.length} elegíveis de ${item.executants.length} candidatos`,
    tone: item.executants.length === 0 ? 'bad' : elegiveis.length === 0 ? 'warn' : 'good',
    evidencia: [
      ...(escolhido.length > 0 ? [`O otimizador ficou com ${escolhido.join(', ')}.`] : []),
      ...(elegiveis.length === 0 && item.executants.length > 0
        ? ['Havia candidatos, mas nenhum passou nas regras de elegibilidade.']
        : []),
      ...(troca
        ? [`Você passou para ${troca.para}: ${troca.motivo}`]
        : []),
    ],
  });

  passos.push({
    chave: 'schedule',
    nome: 'Otimização',
    veredito: alocada
      ? `${dia(alocada.window.start)} às ${hora(alocada.window.start)}–${hora(alocada.window.end)}`
      : fora
        ? `fora da semana · ${REASON_NAMES[fora.reason] ?? fora.reason}`
        : 'não avaliada nesta execução',
    tone: alocada ? 'good' : 'bad',
    codigos: alocada?.reason_codes,
    evidencia: alocada
      ? [`Entrou com score ${alocada.priority_score.toFixed(1)}.`]
      : fora
        ? (fora.details ?? []).length > 0
          ? fora.details
          : ['Sem detalhe adicional do otimizador.']
        : ['Esta ordem não apareceu nem na proposta nem na lista de exclusões.'],
  });

  return (
    <ol className="trace trilha">
      {passos.map((passo) => (
        <li key={passo.chave} className="trace-stage" data-skill={passo.chave === 'schedule' ? undefined : 'true'}>
          <div className="trace-head">
            <span className="trace-name">{passo.nome}</span>
            <Badge tone={passo.tone ?? 'mute'}>{passo.veredito}</Badge>
          </div>
          <ul className="trilha-evidencia">
            {passo.evidencia.filter(Boolean).map((linha, i) => <li key={i}>{linha}</li>)}
          </ul>
          {(passo.codigos ?? []).length > 0 && (
            <p className="trilha-codigos">{passo.codigos!.join(' · ')}</p>
          )}
        </li>
      ))}
    </ol>
  );
}
