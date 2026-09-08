# Agent Base Worktree

Arquitetura de referência para visualizar as responsabilidades de um projeto de
agentes de IA robusto e operável em produção.

A árvore separa:

1. domínio e casos de uso do produto;
2. runtime do agente segundo `H = (E, T, C, S, L, V)`;
3. plataforma operacional, integrações e entrega confiável.

Comece por [`guidelines/architecture.md`](guidelines/architecture.md). Os arquivos
vazios ou contendo apenas comentários representam contratos e pontos de extensão a
serem implementados conforme o domínio do projeto.

Documentos complementares:

- `guidelines/implementation_order.md`: sequência sugerida de construção;
- `guidelines/verificador.md`: verificação em runtime e offline;
- `guidelines/funcionalidades.md`: exemplo de escopo positivo;
- `guidelines/nao_faz.md`: exemplo de limites e escalonamento.

## Agente Programador de PCM

O primeiro incremento offline está implementado com:

- ranking de backlog;
- estimativa de duração;
- disponibilidade de materiais;
- capacidade líquida;
- sugestão de executantes;
- otimizador guloso determinístico;
- verificador independente;
- gate de aprovação humana;
- adaptador Tractian somente leitura.

As quatro primeiras skills independentes são executadas em paralelo. A skill de
executantes consome duração e capacidade, e o otimizador recebe apenas contratos
estruturados. Nenhuma decisão numérica depende de LLM.

### Preparar o ambiente

```bash
uv sync --extra dev
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
  --output evals/datasets/golden-set.jsonl
```

O arquivo carrega snapshot, operação, skill, veredito e motivo. A identidade de
quem avaliou permanece no banco do piloto e não entra no conjunto de dados.

### Validar

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

Consulte [`docs/architecture/plano-implementacao-agente-programador.md`](docs/architecture/plano-implementacao-agente-programador.md)
para o roadmap e os gates das próximas fases.

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
