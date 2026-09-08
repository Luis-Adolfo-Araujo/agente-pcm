## Semana 1 — contratos, domínio e observabilidade

- Definir entidades, IDs, versões, estados e invariantes do domínio.
- Criar schema de evento e writer com redaction.
- Criar contratos de ação, resposta estruturada e decisão de política.
- Implementar laço mínimo com duas ferramentas somente de leitura.
- Adicionar interceptores de lifecycle que ao menos emitam eventos.
- Criar checkpoint simples e identidade completa da execução.

Os pontos de interceptação entram desde o começo porque adicioná-los depois exige
refatorar todos os caminhos de execução. Controles obrigatórios, porém, ficam no dispatcher
ou no motor de políticas; não dependem de um hook opcional.

## Semana 2 — adapters e entrega assíncrona

- Consolidar endpoints, projeção de resposta e tradução de erro.
- Implementar webhook como autenticação, normalização, dedupe e enqueue.
- Processar o agente em worker, com lock por sessão e backpressure.
- Adicionar outbox para entrega e correlação por `message_id`/`trace_id`.
- Medir tokens, latência, erros e custo por execução.

## Semana 3 — política e ações com efeito

- Implementar o dispatcher único de ferramentas.
- Aplicar escopo, privilégio, irreversibilidade e inspeção de saída.
- Adicionar idempotência, concorrência otimista e revalidação antes da entrega.
- Criar templates seguros de fallback e escalonamento.
- Só depois disso habilitar a primeira ferramenta de escrita.

## Semana 4 — avaliação e operação

- Criar casos com estado inicial fixo e critério explícito.
- Cobrir golden set, red team, escalonamento e over-refusal.
- Rodar testes de contrato, segurança, resiliência e replay em CI.
- Criar dashboards, alertas, runbooks, backup/restore e rollback.
- Versionar conjuntamente modelo, prompt, política, grafo e dados de domínio.
