'use client';
import { useMemo, useState } from 'react';
import { FormDuracao } from '@/components/ajuste/FormDuracao';
import { FormIncluir } from '@/components/ajuste/FormIncluir';
import { FormIndisponivel, type RascunhoIndisponivel } from '@/components/ajuste/FormIndisponivel';
import { PreviaAjuste } from '@/components/ajuste/PreviaAjuste';
import type { Revisor } from '@/components/sessao/useRevisao';
import type { Capacity, FeedbackDoAjuste, Schedule } from '@/lib/api';
import { destinosDaInclusao } from '@/lib/destinos';
import { escreverHhmm, lerHhmm } from '@/lib/duracao';
import {
  pedidoDeDuracao, pedidoDeInclusao, pedidoDeIndisponibilidade, type Escolha,
} from '@/lib/pedidos';
import { resumoDasConsequencias } from '@/lib/previa';
import { motivoDeAjuste, type MarcasDaRevisao } from '@/lib/revisao';
import { rotuloDia, type Indice } from '@/lib/semana';

/** A ação que está com o modal de prévia aberto. */
export type AcaoAberta =
  | { tipo: 'remover'; operationId: string }
  | { tipo: 'indisponivel'; tecnico: string; dia: string }
  | { tipo: 'duracao'; operationId: string }
  | { tipo: 'incluir'; operationId: string };

type Props = {
  revisor: Revisor;
  indice: Indice;
  dias: string[];
  marcas: MarcasDaRevisao;
  /** A semana na tela, para a folga de cada destino de inclusão. */
  semana: Schedule;
  capacidades: Capacity[];
  onFechar: () => void;
  onConfirmado: (mensagem: string) => void;
};

/**
 * Cada ação é um componente próprio porque cada formulário tem o seu estado, e
 * hook não pode morar dentro de um `if`.
 */
export function AcaoDeAjuste({ acao, ...props }: Props & { acao: AcaoAberta }) {
  if (acao.tipo === 'remover') return <AcaoRemover operationId={acao.operationId} {...props} />;
  if (acao.tipo === 'indisponivel') return <AcaoIndisponivel tecnico={acao.tecnico} dia={acao.dia} {...props} />;
  if (acao.tipo === 'duracao') return <AcaoDuracao operationId={acao.operationId} {...props} />;
  if (acao.tipo === 'incluir') return <AcaoIncluir operationId={acao.operationId} {...props} />;
  return null;
}

function AcaoRemover({ operationId, revisor, indice, onFechar, onConfirmado }: Props & { operationId: string }) {
  const titulo = indice.titulos.get(operationId) || operationId;
  return (
    <PreviaAjuste
      titulo={`Tirar da semana · ${titulo}`}
      acoes={[{ kind: 'remove', operation_id: operationId }]}
      revisor={revisor}
      titulos={indice.titulos}
      feedback={(motivo) => [{
        operation_id: operationId, skill: 'ranking', reason: motivoDeAjuste('tirar da semana', motivo),
      }]}
      anuncio={(previa) => `${titulo} saiu da semana. ${resumoDasConsequencias(previa)}`}
      onFechar={onFechar}
      onConfirmado={onConfirmado}
    />
  );
}

/**
 * A ausência não grava feedback: o agente não tinha como saber de férias ou de
 * atestado, e ensinar que ele errou aqui seria ensinar errado.
 */
function AcaoIndisponivel({
  tecnico, dia, dias, revisor, indice, onFechar, onConfirmado,
}: Props & { tecnico: string; dia: string }) {
  const [valor, setValor] = useState<RascunhoIndisponivel>({ de: dia, ate: dia, causa: '' });
  const acoes = pedidoDeIndisponibilidade(tecnico, valor.de, valor.ate, valor.causa, dias);
  return (
    <PreviaAjuste
      titulo={`Marcar indisponível · ${tecnico}`}
      acoes={acoes}
      formulario={<FormIndisponivel dias={dias} valor={valor} onMudar={setValor} />}
      vazio="Escolha os dias e o motivo para ver para onde vão as ordens dessa pessoa."
      revisor={revisor}
      titulos={indice.titulos}
      feedback={() => []}
      anuncio={(previa) => (
        `${tecnico} indisponível de ${rotuloDia(valor.de).numero} a ${rotuloDia(valor.ate).numero}. `
        + resumoDasConsequencias(previa)
      )}
      onFechar={onFechar}
      onConfirmado={onConfirmado}
    />
  );
}

function AcaoDuracao({
  operationId, revisor, indice, marcas, onFechar, onConfirmado,
}: Props & { operationId: string }) {
  const item = indice.enriched.get(operationId) ?? null;
  const atual = item?.duration.minutes ?? null;
  const [valor, setValor] = useState(atual === null ? '' : escreverHhmm(atual));
  if (!item) return null;

  const titulo = item.operation.title || operationId;
  const novo = lerHhmm(valor);
  const deHoje = atual === null ? 'sem duração' : escreverHhmm(atual);
  return (
    <PreviaAjuste
      titulo={`Alterar tempo previsto · ${titulo}`}
      acoes={pedidoDeDuracao(operationId, valor, atual)}
      formulario={(
        <FormDuracao
          item={item}
          antes={marcas.duracaoAntes.get(operationId)}
          valor={valor}
          onMudar={setValor}
        />
      )}
      vazio="Digite um tempo diferente do atual para ver o que muda no dia."
      revisor={revisor}
      titulos={indice.titulos}
      feedback={(motivo) => (novo === null ? [] : [{
        operation_id: operationId,
        skill: 'duration',
        reason: motivoDeAjuste(`duração de ${deHoje} para ${escreverHhmm(novo)}`, motivo),
      }])}
      anuncio={(previa) => (
        `${titulo} passou a ter ${novo === null ? deHoje : escreverHhmm(novo)} previstas. `
        + resumoDasConsequencias(previa)
      )}
      onFechar={onFechar}
      onConfirmado={onConfirmado}
    />
  );
}

function AcaoIncluir({
  operationId, revisor, indice, dias, semana, capacidades, onFechar, onConfirmado,
}: Props & { operationId: string }) {
  const item = indice.enriched.get(operationId) ?? null;
  const [escolha, setEscolha] = useState<Escolha | null>(null);
  const [duracao, setDuracao] = useState('');
  const precisaDuracao = !item?.duration.minutes;
  const digitada = lerHhmm(duracao);
  const minutos = item?.duration.minutes ?? digitada ?? 60;
  const destinos = useMemo(
    () => (item ? destinosDaInclusao(item, dias, semana.assignments, capacidades, minutos) : []),
    [item, dias, semana, capacidades, minutos],
  );
  if (!item) return null;

  const titulo = item.operation.title || operationId;
  const onde = escolha ? `${escolha.tecnico} em ${rotuloDia(escolha.dia).numero}` : '';
  return (
    <PreviaAjuste
      titulo={`Incluir na semana · ${titulo}`}
      acoes={pedidoDeInclusao(operationId, escolha, precisaDuracao ? digitada : null, precisaDuracao)}
      formulario={(
        <FormIncluir
          dias={dias}
          destinos={destinos}
          escolha={escolha}
          onEscolher={setEscolha}
          minutos={minutos}
          precisaDuracao={precisaDuracao}
          duracao={duracao}
          onDuracao={setDuracao}
        />
      )}
      vazio={precisaDuracao
        ? 'Dê o tempo previsto e escolha quem e em que dia para ver o que muda.'
        : 'Escolha quem e em que dia para ver o que muda.'}
      revisor={revisor}
      titulos={indice.titulos}
      feedback={(motivo) => {
        if (!escolha) return [];
        const itens: FeedbackDoAjuste[] = [{
          operation_id: operationId, skill: 'ranking', reason: motivoDeAjuste(`incluir na semana com ${onde}`, motivo),
        }];
        if (precisaDuracao && digitada !== null) {
          itens.push({
            operation_id: operationId,
            skill: 'duration',
            reason: motivoDeAjuste(`duração de sem duração para ${escreverHhmm(digitada)}`, motivo),
          });
        }
        return itens;
      }}
      anuncio={(previa) => `${titulo} entrou na semana com ${onde}. ${resumoDasConsequencias(previa)}`}
      onFechar={onFechar}
      onConfirmado={onConfirmado}
    />
  );
}
