# Agente Programador de PCM

Monta a programação semanal de manutenção de uma planta industrial: lê o backlog
de ordens, decide o que cabe na semana, para quem vai e em que dia — e diz, ordem
por ordem, por que cada uma que ficou de fora ficou de fora.

**Nenhuma decisão numérica depende de LLM.** Ranking, duração, material,
capacidade e alocação saem de skills determinísticas sobre um snapshot congelado.
Um verificador independente confere a proposta pronta, e nada vira programação
sem um humano aprovar — uma proposta inválida não pode ser aprovada.

Para ver funcionando, sobre uma planta que não existe:
<https://luis-adolfo-araujo.github.io/agente-pcm/>

## O que tem aqui

```
src/agent/skills/      as skills, uma pasta por competência
src/agent/programmer/  o otimizador guloso e o verificador
src/agent/trace/       o registro do que a rodada fez, em JSONL
src/domain/planning/   ordens, técnicos, capacidade, janela
src/domain/notes/      notas de manutenção, antes de virarem ordem
src/application/       CLI, workflows e a camada de serviço
src/infrastructure/    adaptador Tractian, somente leitura
src/api/               a API HTTP que a interface consome
src/presentation/      o piloto Streamlit, a primeira tela
web/                   a interface de programação, em Next.js
demo/                  o snapshot inventado da demonstração
config/tenants/        os parâmetros de uma planta
scripts/               congelamento dos artefatos da demonstração
```

A anatomia `H = (E, T, C, S, L, V)` que o runtime persegue está no cabeçalho de
[`src/agent/__init__.py`](src/agent/__init__.py). O que está versionado é a fatia
dela que o Agente Programador exercita; o resto é ponto de extensão em aberto, e
não um esqueleto de arquivos vazios no repositório.

## As skills

| Skill | O que decide |
|---|---|
| [`rank-backlog`](src/agent/skills/pcm/rank-backlog/SKILL.md) | a ordem do backlog, por prioridade informada, idade, SLA e criticidade |
| [`estimate-duration`](src/agent/skills/pcm/estimate-duration/SKILL.md) | quanto tempo cada operação leva, com confiança e fallback explícitos |
| [`check-materials`](src/agent/skills/pcm/check-materials/SKILL.md) | disponível, parcial, indisponível ou desconhecido — sem confundir falta de saldo com falta de cadastro |
| [`calculate-capacity`](src/agent/skills/pcm/calculate-capacity/SKILL.md) | a capacidade líquida por pessoa, descontando escala, ausências e compromissos |
| [`suggest-executants`](src/agent/skills/pcm/suggest-executants/SKILL.md) | quem são os candidatos a executar, e em que ordem |
| [`treat-notes`](src/agent/skills/notes/treat-notes/SKILL.md) | duplicidade, tipo e prioridade de um lote de notas, antes da ordem existir |

As quatro primeiras são independentes e rodam em paralelo. A de executantes
consome duração e capacidade. O otimizador recebe apenas contratos estruturados,
nunca texto livre, e o adaptador Tractian nunca escreve.

`treat-notes` fica fora do workflow de programação: trata o que chega antes dele.

## Rodar o agente

### Preparar o ambiente

```bash
uv sync --extra dev
```

Não há `uv.lock` versionado. Para levantar só a API da demonstração, sem o resto,
`requirements.txt` fixa as versões verificadas — `psycopg` e o extra `pilot`
ficam de fora de propósito, porque a demonstração lê arquivo e nunca abre banco:

```bash
pip install -r requirements.txt
```

### Extrair um snapshot atual da Tractian

Configure a conexão fora da linha de comando para não expor credenciais:

```bash
export SOURCE_DATABASE_DSN='postgresql://usuario:senha@host:porta/banco'

uv run maia-pcm extract-snapshot \
  --tenant TENANT_ID \
  --period-start 2026-08-18T00:00:00-03:00 \
  --period-end 2026-08-25T00:00:00-03:00 \
  --as-of 2026-08-17T12:00:00-03:00 \
  --output /tmp/planta-modelo-snapshot.json
```

O adaptador recusa simular um `as_of` histórico sobre tabelas de estado atual.
Backtesting exige snapshot imutável ou reconstrução por histórico.

### Gerar uma proposta em dry-run

```bash
uv run maia-pcm generate-proposal \
  --snapshot-file /tmp/planta-modelo-snapshot.json \
  --period-start 2026-08-18T00:00:00-03:00 \
  --period-end 2026-08-25T00:00:00-03:00 \
  --as-of 2026-08-17T12:00:00-03:00 \
  --config config/tenants/planta-modelo.yaml \
  --output-dir planning-output
```

A execução produz `proposal.json`, `verification.json`, `summary.json` e
`trace.jsonl`.

### Registrar a decisão humana

```bash
uv run maia-pcm decide-proposal \
  --proposal-file planning-output/proposal.json \
  --decision approve \
  --decided-by USUARIO_PCM \
  --decided-at 2026-08-17T13:00:00-03:00 \
  --reason 'Programação revisada pelo PCM' \
  --output planning-output/proposal-reviewed.json
```

Uma proposta inválida não pode ser aprovada.

## Interface web do piloto

Streamlit multipágina que consome a camada de serviço em processo. O piloto é
somente leitura: nenhuma tela escreve na Tractian.

Esta é a primeira interface, feita para avaliar as skills uma a uma. A interface
de programação, com o quadro por executante e por dia, mora em `web/` e conversa
com a API — é ela que a demonstração pública publica.

### Preparar

```bash
uv sync --extra dev --extra pilot

mkdir -p var/pilot/snapshots
cp /tmp/planta-modelo-snapshot.json var/pilot/snapshots/
```

O diretório de snapshots é um catálogo congelado: cada arquivo é validado contra
o contrato canônico, indexado por SHA-256 e recusado se for alterado depois.

### Subir

```bash
export MAIA_PILOT_PASSWORD='defina-uma-senha'
uv run maia-pcm-pilot
```

A interface sobe em `http://localhost:8501`.

### Variáveis de ambiente

| Variável | Padrão | Função |
|---|---|---|
| `MAIA_PILOT_PASSWORD` | — | Senha de acesso. Sem ela a interface fica bloqueada. |
| `MAIA_PILOT_ALLOW_ANONYMOUS` | `false` | Libera acesso sem senha. Apenas para ambiente local descartável. |
| `MAIA_PILOT_SNAPSHOT_DIR` | `var/pilot/snapshots` | Catálogo de snapshots congelados. |
| `MAIA_PILOT_RUN_DIR` | `var/pilot/runs` | Artefatos por execução. |
| `MAIA_PILOT_DB` | `var/pilot/pilot.sqlite3` | Banco local de runs, decisões e feedback. |
| `MAIA_PILOT_SHOW_RAW_WORKER_IDS` | `false` | Exibe identificadores de origem das pessoas. Exige autorização. |
| `MAIA_PILOT_ALIAS_SALT` | interno | Sal do alias determinístico dos executantes. |
| `MAIA_PILOT_TENANT_LABEL` | `Planta Modelo` | Rótulo exibido no cabeçalho. |
| `MAIA_PILOT_USER` | `avaliador-piloto` | Identificação padrão de quem avalia. |

Por padrão os executantes aparecem pseudonimizados como `Técnico-XXXXXXXX`, e os
downloads são sanitizados antes de sair da camada de apresentação.

### Exportar o golden set

O feedback coletado nas sessões alimenta a avaliação offline das skills:

```bash
uv run maia-pcm export-golden-set \
  --db var/pilot/pilot.sqlite3 \
  --output var/pilot/golden-set.jsonl
```

O arquivo carrega snapshot, operação, skill, veredito e motivo. A identidade de
quem avaliou permanece no banco do piloto e não entra no conjunto de dados.

## Demonstração pública

A interface de programação, publicada como página estática, sobre uma planta
que não existe: <https://luis-adolfo-araujo.github.io/agente-pcm/>

Ela serve para olhar e ajustar a tela — o chevron das etapas, o quadro por
executante e por dia, a explicação de por que cada ordem entrou ou ficou de
fora. Não há servidor atrás: a rodada já aconteceu, feita pelo agente de
verdade, e as respostas viajam como arquivo.

### O dado

`demo/snapshots/demo-planta-modelo.json` é gerado por semente, não extraído. A
planta tem 96 ativos em cinco áreas, 22 técnicos em quatro equipes, 1.200 ordens
abertas, 1.466 execuções históricas e 1.800 itens de estoque. Ativos, ordens,
técnicos e materiais são inventados; nenhum registro de cliente participou da
construção.

O mundo é calibrado para não caber inteiro na semana. Uma rodada sobre ele
devolve 469 ordens programadas, 529 sem capacidade, 138 sem material e 64
bloqueadas — as quatro saídas que o PCM precisa distinguir, em vez de uma semana
folgada onde tudo entra.

```bash
# refaz a planta; a mesma semente devolve o mesmo arquivo
uv run maia-pcm generate-demo-snapshot \
  --output demo/snapshots/demo-planta-modelo.json

# congela uma rodada do agente como os JSON que a página lê
uv run python scripts/gerar_artefatos_demo.py
```

Os artefatos saem do próprio cliente HTTP da API, não de um molde escrito à
mão: o que a página lê tem a forma exata que um servidor devolveria. Se o
contrato mudar, quebra aqui.

### Publicar a página

```bash
web/publicar.sh
```

Constrói e empurra para o branch `gh-pages`. O Pages serve um repositório de
projeto sob `/<repositório>/`, então o build recebe esse subcaminho em
`PAGES_BASE_PATH`, e `NEXT_PUBLIC_DEMO=1` liga o modo sem servidor.

### A mesma tela contra a API de verdade

A interface não sabe se está na demonstração. Sem `NEXT_PUBLIC_DEMO`, ela fala
HTTP com a API do piloto:

```bash
MAIA_PILOT_SNAPSHOT_DIR=demo/snapshots \
  uv run uvicorn --factory api.app:create_app --port 8001

cd web && npm install && NEXT_PUBLIC_API=http://localhost:8001 npm run dev
```

`MAIA_WEB_DIR` faz a API montar a interface já exportada na própria raiz, se
você preferir um endereço só.

### O acesso

A página não pede senha: sobre dado inventado não há o que proteger. Sobre dado
real nada muda — com `MAIA_PILOT_PASSWORD` definida, a API exige o Bearer em
toda rota que não seja `/api/health`.

Os executantes aparecem com o identificador cru (`tecnico-07`) porque são
fictícios: o pseudônimo esconderia um dado que não existe.

## Validar

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```
