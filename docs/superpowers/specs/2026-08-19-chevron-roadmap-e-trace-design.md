# Chevron roadmap + aba de trace no maia-web

Data: 2026-08-19
Alvo: `maia-web/` (Next.js 15) e `pcm-agent/src/application/workflows/generate_schedule.py`

## Problema

1. O roadmap do piloto é uma barra lateral vertical de 280px que come largura das tabelas e mostra estado que não conferiu (marca etapas 3–5 como concluídas assim que a semana fica pronta; marca a etapa 2 como concluída em run `failed`).
2. O agente produz muito mais do que a tela mostra. O `backlog` (13 MB) é baixado a cada run e a maior parte é descartada: capacidades por pessoa, bandas de prioridade, fonte de duração, evidências de executante, lista de violações.
3. Não existe superfície que responda "o que cada skill fez nesta execução" — necessária tanto para auditar/defender a proposta quanto para depurar um número suspeito.

## Decisões

- Chevron horizontal com **as 5 etapas do app** (não as 6 do processo PCM), no visual da referência: setas encaixadas com um número vivo acima de cada uma.
- Trace no **formato funil vertical**, um cartão por skill, dentro da etapa 4 como segunda aba.
- Backend pode mudar.
- Escopo inclui os 2 P0 da vistoria de 2026-08-19 (`.impeccable/critique/2026-08-19T14-15-39Z__maia-web-src-app-page-tsx.md`).

## Arquitetura

### 1. Casca: `Chevron` substitui `.sidebar`

`page.tsx` deixa de renderizar `<aside class="sidebar">` e passa a renderizar `<header class="topbar">` com marca, garantia de somente-leitura e o trilho.

Novo componente `src/components/Chevron.tsx`:

- `<nav aria-label="Etapas">` com um `<button>` por etapa, `aria-current="step"` na atual, `disabled` nas travadas.
- Forma via `clip-path` nas classes `.chev`; estado por preenchimento **e** glifo (`✓`, `●`, vazio) — nunca só por cor.
- `:focus-visible` explícito (hoje `.btn`/`.stage` não têm nenhum).
- Cada etapa recebe `metric: {value: string, tone?: 'good'|'warn'|'bad'}` calculado em `page.tsx`.

Números por etapa (nenhum inventado):

| Etapa | Métrica | Fonte |
|---|---|---|
| 1 | `1.200 OS` | `snapshot.quality.operation_count` |
| 2 | `5,1 s` ou `montando…` | soma de `run.trace_events[].elapsed_ms` |
| 3 | `469/1.200` | `schedule.coverage.scheduled_operations` / `total_operations` |
| 4 | `0 violações` / `3 violações` | `verification.violations.length` |
| 5 | `pendente` / `aprovada 19/08` / `rejeitada` | `run.decision` |

Estado das etapas passa a derivar de `run.status`, `run.decision` e da existência dos artefatos — não mais de "existe schedule".

Responsivo: `@media (max-width: 900px)` o trilho vira faixa com rolagem horizontal; `640px` os chevrons empilham em duas linhas e o topbar quebra em duas linhas.

### 2. Etapa 4: duas abas

`PorQue.tsx` passa a hospedar um tablist acessível (`role="tablist"`, `role="tab"`, `aria-selected`, setas do teclado, `role="tabpanel"`):

- **Por ordem** — a fila e o detalhe que já existem.
- **Por skill** — novo `src/components/stages/Trace.tsx`.

### 3. `Trace.tsx` — funil vertical

Topo: faixa de procedência com recorte, `sha256`, período, `ruleset_version`, `weights_version` e os parâmetros de `run.config` que a skill do cartão usa (todos já servidos pelo `GET /api/runs/{id}`; `config` só não estava tipado no cliente).

Um cartão por estágio na ordem de execução, com as 4 skills paralelas aninhadas dentro de `skills_parallel`. Cada cartão: contagem de saída, tempo, distribuição em barras segmentadas. Segmento é `<button>`; clicar filtra a tabela de OS no rodapé do cartão; cada linha abre o JSON cru daquele trecho num `<details>`.

Distribuições derivadas client-side (`useMemo`) do `backlog` já carregado:

- `rank_backlog` — bandas de `priority.band`, frequência de `reason_codes`, frequência de `missing_fields`
- `estimate_duration` — frequência de `duration.source`, confiança média, quantas com `sample_size === 0`
- `check_materials` — frequência de `materials.status`, quantas com `blocking`
- `calculate_capacity` — HH bruto/comprometido/líquido por pessoa (de `backlog.capacities`, hoje descartado)
- `suggest_executants` — candidatos por OS, elegíveis, OS sem candidato
- `optimization` — alocadas × fora por motivo (de `schedule.coverage.reasons`)
- `verification` — tabela de `verification.violations` (code · severity · details · OS)

### 4. Backend: tempo por skill

`generate_schedule.py` cronometra cada skill dentro do `TaskGroup` e emite um evento por skill com nome `skill.<nome>` antes do evento agregado `skills_parallel`, que **continua existindo**. `PlanningStageTrace.stage` já é string livre, então não há mudança de schema e nada que lê o trace hoje quebra.

Consumidores a atualizar: `tests/end_to_end/test_generate_schedule.py` (duas asserções de sequência) e o mapa `STAGE_NAMES` em `maia-web/src/lib/api.ts`.

`skill_versions` fica de fora: não vive em `PilotRun`, e `ruleset_version` + `weights_version` (sha256) já dão a procedência.

### 5. Os dois P0

- `page.tsx` passa `verification` para `Semana`; o Stat "Violações duras" deriva valor e tom em vez do `value={0}` fixo.
- `lib/api.ts` envia `Authorization: Bearer ${NEXT_PUBLIC_API_TOKEN}` quando houver token, propaga `response.status` num `ApiError`, e as mensagens de `page.tsx` ramificam por status (401 → credencial; conexão → cita a URL real, não ":8000" fixo).

Fora de escopo nesta rodada: tela de login, export, histórico de runs, feedback, filtros, Gantt. Ficam registrados na vistoria.

## Verificação

- `npm run typecheck` e `npm run build` em `maia-web/`
- `pytest` nos testes de trace e e2e do agente
- detector do Impeccable sobre `maia-web/src`
- run real contra a API com a semana montada, conferindo os números do chevron contra `trace.jsonl` e `summary.json`

Sem suíte de teste no front hoje; não será criada nesta rodada.

## Adendo — defeito encontrado durante a verificação (2026-08-19)

`pseudonymize_worker_fields` tratava a chave `executants` como lista de nomes. Quando o valor é
uma lista de candidatos (objetos com `score`, `eligible`, `available_minutes`, `reason_codes`), cada
objeto inteiro virava um único alias derivado do `repr` do dict: a saída da skill era destruída na
saída da API. Efeitos observados: `GET /api/runs/{id}/backlog` devolvia `executants` como lista de
strings, o painel "Executantes sugeridos" da etapa 4 quebrava em runtime ao ler `.score`, e a
distribuição de elegibilidade lia "nenhum elegível" para as 1.200 ordens.

Corrigido em `src/presentation/privacy.py`: itens que são Mapping/list/tuple descem recursivamente
(o alias é aplicado na chave `worker_id` de cada candidato); apenas escalares viram alias direto.
Regressões em `tests/unit/presentation/test_privacy.py`.
