---
name: rank-backlog
description: Priorizar operações de manutenção por prioridade informada, idade, SLA e criticidade disponível. Usar ao ordenar backlog ou preparar uma proposta de programação; não usar disponibilidade de material ou executante para reduzir a urgência da ordem.
---

# Ranking do backlog

Substitui a etapa "Priorização de ordens" do processo do PCM: avaliar ordens
conforme critérios de priorização.

1. Validar `tenant_id`, `as_of` e versão dos pesos.
2. Chamar exclusivamente a ferramenta estruturada de ranking.
3. Preservar separadamente as parcelas de prioridade, idade, SLA e criticidade.
4. Sinalizar criticidade ausente; nunca inferir criticidade baixa.
5. Entregar score, faixa, razões e campos ausentes.

Não recalcular score em linguagem natural. Não confundir prioridade com prontidão ou programabilidade.

## Fronteira com o trabalho manual

`priority_level` é entrada, não saída. Quem o define é o PCM em "Tratamento das
notas". Esta skill ordena o backlog usando a prioridade já cadastrada; ela não
classifica a nota, não define centro de trabalho e não diagnostica a falha.
