<!-- o que o agente aprende -->
<!-- Nomeie pela capacidade ou pelo trabalho realizado: investigate-industrial-incident, validate-identity-document, analyze-energy-anomaly, generate-auditable-report -->
<!-- Evite nomes de persona: maintenance-agent, document-agent, energy-specialist, report-agent -->
<!-- Uma skill representa uma competência, não uma identidade. -->



<!-- EXEMPLO DE COMO ESCREVER UMA SKILL CORRETAMENTE:
---
name: investigate-industrial-incident
description: >
  Investiga incidentes industriais correlacionando telemetria, alarmes,
  eventos operacionais e histórico de manutenção. Use em casos de falha,
  parada, degradação ou comportamento anômalo de equipamento.
license: Proprietary
compatibility: Requires telemetry, alarm-history and maintenance-order tools
metadata:
  owner: industrial-ai
  version: "1.0.0"
  domain: industrial-operations
  risk-tier: high
---

# Investigate Industrial Incident

## Purpose

Produzir uma investigação baseada em evidências sobre um incidente
industrial sem executar alterações operacionais.

## Use When

- Um equipamento apresentar comportamento anômalo.
- Houver parada, alarme ou degradação.
- For necessário correlacionar telemetria e eventos.

## Do Not Use When

- O usuário pedir alteração direta no equipamento.
- Não houver identificação do ativo ou intervalo temporal.
- A fonte de telemetria estiver indisponível.

## Required Inputs

- Identificação do equipamento.
- Intervalo temporal.
- Sintoma, alarme ou evento inicial.

## Procedure

1. Confirme o equipamento e o intervalo temporal.
2. Consulte alarmes e mudanças operacionais.
3. Analise a telemetria anterior e posterior ao incidente.
4. Busque ocorrências semelhantes.
5. Classifique cada hipótese como confirmada, provável ou inconclusiva.
6. Produza o relatório seguindo `assets/incident-report.md`.

## Tool Guidance

- Use `telemetry.query` para séries temporais.
- Use `alarm-history.search` para alarmes.
- Use `maintenance-orders.search` para intervenções anteriores.
- Execute `scripts/correlate-events.py` para correlação temporal.

## Evidence Requirements

Toda conclusão deve citar:

- Fonte.
- Timestamp.
- Equipamento.
- Dado observado.
- Relação entre dado e hipótese.

Leia `references/evidence-requirements.md` para os critérios completos.

## Guardrails

- Não execute comandos em equipamentos.
- Não apresente correlação como causalidade.
- Não omita fontes contraditórias.
- Solicite revisão humana para recomendações operacionais.

## Output Contract

Retorne:

1. Resumo do incidente.
2. Linha do tempo.
3. Evidências.
4. Hipóteses avaliadas.
5. Grau de confiança.
6. Dados ausentes.
7. Próximos passos sujeitos a aprovação.

## Failure Handling

Se uma fonte estiver indisponível:

1. Registre a indisponibilidade.
2. Continue apenas se houver evidência suficiente.
3. Reduza explicitamente o grau de confiança.
4. Não fabrique dados ou eventos. -->