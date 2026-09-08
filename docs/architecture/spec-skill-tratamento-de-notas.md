# Spec — Skill de Tratamento de Notas (`treat-notes`)

Data: 2026-08-18

## 1. Objetivo

Reduzir o esforço manual da etapa "Tratamento das notas" do processo de PCM,
sugerindo duplicidade, tipo de nota e prioridade para um lote de notas, sem
decidir nada sozinha e sem contaminar o caminho determinístico do Agente
Programador.

O processo de referência é o mapa do M. Dias Branco (`docs/adr/use-cases-mdiasbranco.md`,
Épico 1 — Porteiro Inteligente). A intenção declarada é unificar esse processo
para Planta Modelo e Stellantis.

## 2. Escopo da primeira versão

Coberto: US-01 (lote), US-02 (duplicidade), US-03 (tipo de nota), US-04 (prioridade).

Fora: componente defeituoso, modo de falha, lista de tarefa, descrição reescrita,
tipo de atividade e desativação, material e duração. Duração e material já são
resolvidos de forma determinística por `estimate-duration` e `check-materials`;
a skill de notas delega, não refaz.

## 3. Posição no fluxo

A skill não entra em `generate_schedule`. Ela opera sobre notas; o workflow
determinístico opera sobre operações já criadas. Existe um portão humano entre
os dois estágios.

```
NoteBatch → treat-notes → NoteBatchResult → [PCM revisa e aplica] → ordens → PlanningSnapshot → generate_schedule
```

Fundir os estágios faria inferência sobre texto livre alimentar diretamente o
ranking determinístico.

## 4. Matriz de política por campo

| Campo | Política | Motivo |
|---|---|---|
| duplicidade | recomendação | não preenche campo canônico; cancelar é ação humana |
| tipo de nota | consultivo | juízo sobre texto contra catálogo fechado |
| prioridade | consultivo | alimenta `rank-backlog`; autoritativo quebraria a garantia determinística |

Na primeira versão nenhum campo é autoritativo. Os campos que justificam o modo
autoritativo — código de material e lista de tarefa — pertencem ao escopo
seguinte. A política existe por campo desde já e é configurável.

## 5. Duplicidade em três faixas

1. Bloqueio determinístico por `asset_id` e janela temporal; sem ativo, por
   trigrama do título normalizado.
2. Score determinístico por par: Jaccard de trigramas, proximidade temporal e
   coincidência de ativo. Acima do limiar alto o veredito é `duplicate`; abaixo
   do limiar baixo é `unique`. Nenhum LLM nessas duas faixas.
3. Somente a faixa cinzenta vai ao adjudicador, que recebe apenas os dois textos,
   datas e ativo.

## 6. Fronteira do LLM

O adjudicador fica atrás de um `Protocol`. Sem adjudicador disponível, a faixa
cinzenta degrada para `needs_review`, nunca para `unique`: o modo de falha seguro
devolve trabalho ao humano em vez de afirmar unicidade.

## 7. Degradação por fonte

Quando a fonte não traz o dado, a sugestão é omitida com motivo estruturado, e
nunca preenchida por inferência silenciosa:

- sem catálogo de tipos configurado: `note_type` omitido, motivo `catalog_not_configured`;
- sem vínculo histórico nota → ordem: `priority` omitido, motivo `no_historical_linkage`.

## 8. Reprodutibilidade

`NoteBatchResult` carrega versão de regras, hash da configuração, identificação do
adjudicador e versão do prompt. A parte determinística é reprodutível
integralmente.

## 9. Validação

Os dados disponíveis são apenas os da Planta Modelo (`tractian.work_requests`, 795 notas).
Nesse conjunto:

- duplicidade tem verdade verificável: 2 grupos de título repetido, 4 notas;
- tipo de nota não existe como campo (`target` é `workorders` em 100%);
- prioridade não existe na nota, e o vínculo nota → ordem tem 12 registros em 8.998.

Portanto a primeira versão é validada por duplicidade. Tipo de nota e prioridade
são exercitados pelo caminho de degradação até existir uma amostra do export SAP.

Os limiares das três faixas ficam configuráveis, com default conservador: faixa
cinzenta larga, mais casos encaminhados para revisão humana.
