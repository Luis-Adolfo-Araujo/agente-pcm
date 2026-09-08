# Arquitetura de referência

Esta árvore representa as responsabilidades necessárias para levar um agente de IA
da experimentação à produção. Ela é uma referência de organização, não a prescrição
de um framework específico.

## Visão em três camadas

```text
Produto
└── domínio e casos de uso

Agent runtime — H = (E, T, C, S, L, V)
└── loop, ferramentas, contexto, estado, lifecycle, política e trajetória

Plataforma operacional
└── canais, API, workers, filas, bancos, providers, segurança e telemetria
```

O domínio deve continuar válido sem WhatsApp e, sempre que possível, sem LLM. O
runtime coordena decisões probabilísticas, mas regras duras pertencem ao domínio ou
ao motor de políticas. A plataforma cuida da entrega confiável e da operação.

## Árvore de referência

```text
.
├── src/
│   ├── agent/                 # runtime genérico do agente
│   │   ├── loop/              # E: execução, recuperação e terminação
│   │   ├── tools/             # T: catálogo, seleção, contratos e dispatcher
│   │   ├── context/           # C: montagem, orçamento, projeção e compactação
│   │   ├── state/             # S: memória, checkpoint, locks e idempotência
│   │   ├── lifecycle/         # L: interceptores obrigatórios do ciclo de vida
│   │   ├── trace/             # V: eventos, persistência e replay
│   │   ├── models/            # providers, roteamento, capacidades, custo
│   │   ├── policies/          # motor e decisões; artefatos ficam em /policies
│   │   ├── prompts/           # carregamento e versionamento de prompts
│   │   └── skills/            # capacidades progressivamente carregáveis
│   ├── application/           # comandos, consultas e workflows do produto
│   ├── domain/                # entidades, regras e eventos do negócio
│   ├── channels/              # adapters de WhatsApp, web e outros canais
│   ├── infrastructure/        # banco, fila, cache, LLM, grafo, secrets, telemetry
│   ├── api/                   # fronteira HTTP; valida e enfileira trabalho
│   └── workers/               # processamento assíncrono e entrega outbound
├── prompts/                   # conteúdo versionado por finalidade
├── policies/                  # regras declarativas versionadas
├── config/                    # configuração por ambiente, validada por schema
├── evals/                     # comportamento probabilístico e regressões
├── tests/                     # invariantes determinísticos
├── migrations/                # evolução reproduzível dos stores
├── sandbox/                   # isolamento técnico das ações
├── deploy/                    # manifests, health checks e rollout
├── scripts/                   # tarefas operacionais explícitas
└── docs/                      # ADRs, threat model, runbooks e incidentes
```

## Fluxo produtivo mínimo

```text
webhook
  → autenticação e deduplicação
  → fila
  → lock por sessão
  → restauração de checkpoint
  → política de entrada
  → montagem de contexto
  → geração estruturada
  → validação determinística
  → autorização e execução de ferramenta
  → validação de saída
  → outbox
  → entrega
  → checkpoint e trace
```

O webhook não executa o agente inteiro. Ele autentica, normaliza, deduplica e
enfileira. Workers aplicam backpressure, retry e isolamento de falhas.

## Invariantes arquiteturais

1. Toda ferramenta passa por `tools/dispatcher.py`; adapters não são chamados pelo
   loop diretamente.
2. Toda ação com efeito exige autorização, chave de idempotência e registro no trace.
3. Hooks de observabilidade podem ser opcionais; controles de segurança não são.
4. Estado persistido é versionado e usa concorrência otimista ou lock por sessão.
5. Cada execução registra versões de modelo, prompt, política, grafo e plano.
6. Respostas externas são projetadas e sanitizadas antes de entrar no contexto.
7. Trace produz evidência; `evals/` consome evidência. Eles não são a mesma camada.
8. Falha do verificador termina em resposta segura e escalonamento, nunca em envio
   irrestrito nem silêncio.
9. Segredos, dados pessoais e conteúdo clínico não entram em logs por padrão.
10. Regras duras são código ou política executável, nunca apenas instruções no prompt.

## Identidade mínima de uma execução

```text
tenant_id
patient_id ou subject_id
conversation_id
message_id
trace_id
idempotency_key
state_version
plan_version
ruleset_version
graph_version
prompt_version
model_version
```

Antes da entrega, o worker revalida autorização, consentimento e versões das fontes
de verdade. Uma resposta gerada sobre estado revogado ou desatualizado é descartada.

## Testes versus avaliações

- `tests/unit`: funções, schemas e regras determinísticas.
- `tests/integration`: bancos, filas, grafo e providers reais ou compatíveis.
- `tests/contract`: contratos de ferramentas, canais e modelos.
- `tests/security`: autorização, isolamento, prompt injection e vazamento de dados.
- `tests/resilience`: retry, timeout, duplicação, concorrência e retomada.
- `tests/end_to_end`: fluxo completo por cenário.
- `evals`: segurança e qualidade probabilística, golden sets, red team,
  escalonamento e over-refusal.

## Operação

Uma arquitetura de produção inclui também migrations, backup/restore, métricas,
alertas, limites de custo, feature flags, rollout/rollback, runbooks, threat model e
processo de incidentes. Esses artefatos aparecem na árvore porque são parte do
sistema, não documentação posterior.
