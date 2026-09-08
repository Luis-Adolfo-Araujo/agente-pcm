# Ajustes manuais do PCM sobre a programação semanal

Data: 2026-08-19
Alvo: `pcm-agent` (domínio, aplicação, API) e `maia-web` (etapa 3)

## Problema

A semana proposta pelo agente é hoje um artefato somente-leitura: aprovar ou rejeitar, nada
entre os dois. O PCM sabe coisas que o cadastro não sabe — uma parada de linha combinada, um
técnico que não deve pegar determinado ativo, uma ordem urgente que o agente não tinha como
saber que era urgente. Sem espaço para essa mão, a única saída honesta é rejeitar a semana
inteira por causa de um item.

## Decisões tomadas

1. **Duas camadas.** Restrições guiam a *próxima montagem*; ajustes corrigem *esta proposta*.
2. **O verificador não tem veto.** Ele roda a cada ajuste e mostra o que quebrou; quem decide é
   a pessoa. Aprovar com violação conhecida é permitido, e fica registrado.
3. **Granularidade dia + pessoa.** O horário continua saindo de regra, não de arrasto.
4. **Blocos arrastáveis nesta mesma leva**, com menu como caminho de teclado.
5. **Chat fica para outro spec**, e será somente-leitura quando vier.

## Modelo

### Ajuste (`src/domain/planning/adjustments.py`, novo)

```python
class AdjustmentKind(StrEnum):
    MOVE = "move"        # muda dia e/ou executante de uma ordem já alocada
    REMOVE = "remove"    # tira da semana
    INCLUDE = "include"  # traz para a semana uma ordem que ficou de fora

class ScheduleAdjustment(ContractModel):
    sequence: int                      # ordem de aplicação, começa em 1
    kind: AdjustmentKind
    operation_id: str
    target_date: date | None           # obrigatório em MOVE e INCLUDE
    target_worker_id: str | None       # obrigatório em MOVE e INCLUDE
                                       # MOVE aceita trocar só o dia, só o executante, ou ambos
    reason: str | None                 # texto livre, opcional
    applied_by: str                    # obrigatório
    applied_at: datetime               # com fuso
```

Validação: `MOVE` e `REMOVE` exigem que a operação esteja alocada na revisão corrente, e
`INCLUDE` exige que ela esteja fora — o contrário devolve 409 com a explicação, em vez de aplicar
um ajuste sem sentido. Operação inexistente no snapshot devolve 404.

A proposta do agente é **imutável**. O estado corrente é sempre
`apply_adjustments(proposta_original, ajustes)` — replay puro, ordenado por `sequence`. Duas
aplicações da mesma lista produzem a mesma solução, então a promessa de reprodutibilidade que a
tela exibe continua verdadeira depois de doze ajustes.

### Encaixe de horário (`encaixar_janela`)

Entradas: executante, dia, duração da operação (de `enriched[op].duration.minutes`, caindo em
`config.duration.default_minutes` quando ausente), escala do executante no snapshot, e os blocos
já ocupados na solução corrente (depois das remoções da mesma leva).

Regra: primeiro intervalo livre da escala daquele executante naquele dia, alinhado à malha de
`config.optimizer.slot_granularity_minutes` (15 min).

**Quando não couber, o ajuste é aceito assim mesmo**: o bloco entra imediatamente após o último
compromisso do executante naquele dia, ultrapassando a escala de propósito. O verificador então
acusa `CAPACITY_EXCEEDED` ou `OUTSIDE_AVAILABILITY`, e a violação aparece na tela. Ajuste que não
cabe nunca é recusado em silêncio nem escondido.

### Remoção

`REMOVE` tira a alocação e devolve a operação à lista de não-alocadas com um motivo novo,
`UnscheduledReason.MANUAL`. É o único acréscimo ao enum, e o rótulo entra em `REASON_NAMES` no
front como "Tirada da semana pelo PCM".

### Restrição (`PlanningConstraints`, novo)

```python
class PlanningConstraints(ContractModel):
    must_include: tuple[str, ...] = ()          # operation_id
    must_exclude: tuple[str, ...] = ()          # operation_id
    blocked_days: tuple[date, ...] = ()
    worker_asset_blocks: tuple[tuple[str, str], ...] = ()   # (worker_id, asset_id)
```

Aplicadas **antes** de `optimize_schedule`, sem tocar no otimizador — que precisa continuar com
`algorithm_version: greedy-v1` e replay bit a bit:

- `must_exclude` e `worker_asset_blocks` filtram `enriched` e os candidatos a executante.
- `blocked_days` remove aqueles dias das janelas de capacidade.
- `must_include` pré-aloca essas ordens com o mesmo `encaixar_janela`, subtrai os slots usados das
  capacidades, e só então chama o otimizador para o restante. Se uma ordem exigida não couber
  nem assim, ela entra como não-alocada com `reason = MANUAL` e
  `details = ["CONSTRAINT_MUST_INCLUDE_UNMET"]`, e a tela diz que a regra não pôde ser cumprida —
  a restrição nunca mente sobre ter sido respeitada.

## Verificação

Depois de cada ajuste, `verify_schedule(solucao_ajustada, snapshot, enriched, request)` roda —
o mesmo código que confere o agente, sem atalho nem exceção para mão humana.

A resposta separa:
- **violações herdadas**: já existiam na proposta original;
- **violações criadas**: apareceram por causa dos ajustes (diferença entre os dois conjuntos,
  comparados por `code` + `operation_id`).

## API

```
POST   /api/runs/{id}/adjustments        aplica um ajuste; devolve solução, ajustes e verificação
DELETE /api/runs/{id}/adjustments/last   desfaz o último ajuste
GET    /api/runs/{id}/revision           estado corrente: solução, lista de ajustes, verificação
POST   /api/runs/{id}/constraints        grava as regras para a próxima montagem
POST   /api/runs                         passa a aceitar `constraints` no corpo
POST   /api/runs/{id}/decision           passa a exigir `revision_sequence` e a registrar
                                         `known_violations`

`revision_sequence` é obrigatório de propósito: ele prova que a pessoa aprovou a revisão que
estava na tela. Se outra sessão aplicou um ajuste no intervalo, o servidor devolve 409 em vez de
aprovar uma semana diferente da que foi lida. O cliente web é atualizado na mesma mudança.
```

Persistência: `adjustments.json` e `constraints.json` no diretório da run, além das colunas
correspondentes em `pilot_runs`. A proposta original continua em `proposal.json`, intocada.

## Interface (etapa 3, aba "Por dia")

### Cena de uso

Segunda de manhã, reunião de programação. O PCM abre a semana proposta, percorre dia a dia com
os encarregados, e mexe no que a conversa exigir: "essa não dá, a linha para quinta", "põe o
Silva nessa aqui", "essa aqui tem que entrar". As alterações são poucas e cirúrgicas — a ordem
de grandeza é 3 a 15 ajustes numa semana de 469 ordens, não uma remontagem.

### Faixas reais de dado

Estas são as grandezas que o desenho tem que aguentar, medidas na base da Planta Modelo:

| | Mínimo | Típico | Máximo observado |
|---|---|---|---|
| Técnicos com carga no dia | 0 | 18 | 22 |
| Ordens alocadas no dia | 0 | 105 | 150 |
| Ordens por técnico no dia | 1 | 6 | 14 |
| Escala do técnico | 4 h | 8 h | 12 h |
| Ordens fora da semana | 0 | 731 | 1.200 |
| Título da ordem | 8 car. | 32 car. | 78 car. |

Um técnico com 14 ordens de 30 min num dia é o caso que quebra layouts ingênuos. A linha do
técnico rola dentro de si mesma; a página não.

### Topologia

```
┌ régua de dias ────────────────────────────────────────────────────┐
│  seg 18    [ TER 19 ]    qua 20    qui 21    sex 22   sáb  dom    │
│  142 ord   105 ord       128 ord   96 ord    134 ord   —     —    │
│  86% HH    71% HH        88% HH    64% HH    91% HH               │
└───────────────────────────────────────────────────────────────────┘

┌ terça 19/08 ─────────────────────────────┐  ┌ fora da semana ──────┐
│                                          │  │ buscar OS ou título  │
│ Técnico-946BBF38      6,5h / 8h  ███████░│  │ ┌──────────────────┐ │
│  ┌────────────────────────────────────┐  │  │ │ 8f21c4 · 2h      │ │
│  │ 08:00  Troca de rolamento MB-03 2h │  │  │ │ Inspeção válvula │ │
│  │ 10:00  Inspeção pneumática   1,5h ⚠│  │  │ │ sem HH · score 88│ │
│  │ 14:00  Lubrificação linha 2    3h  │  │  │ └──────────────────┘ │
│  └────────────────────────────────────┘  │  │ … 2.548 outras       │
│                                          │  └──────────────────────┘
│ Técnico-C6CBD5B6      8,0h / 8h  ████████│
│  ┌────────────────────────────────────┐  │
│  │ 07:00  Troca de correia        4h  │  │
│  │ ┈┈ 4,5h livres ┈┈  cabem aqui: …   │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

Um dia por vez. A régua carrega o dia selecionado e serve de alvo de arrasto para os outros.
As linhas de técnico ficam **ordenadas por carga decrescente** e **não são reordenadas enquanto
houver arrasto em curso ou ajuste pendente** — bloco que pula debaixo do cursor é bug de UX.
A reordenação acontece ao trocar de dia.

### Anatomia do bloco de ordem

Hora de início e fim · título · duração · score · selos de pendência (material, sem duração
confiável) · marca de mão humana quando o bloco veio de um ajuste. O número da OS aparece no
bloco em fonte de identificador, completo no `title` — cruzar com a Tractian é o trabalho do PCM
e truncar sem tooltip já foi apontado como defeito.

### Os quatro alvos de arrasto, e os três ajustes

O modelo de interação mapeia um a um no modelo de dados. Não existe gesto sem registro:

| Gesto | Vira |
|---|---|
| Soltar em outra linha de técnico, mesmo dia | `MOVE` (mesmo dia, outro executante) |
| Soltar num chip da régua de dias | `MOVE` (mesmo executante, outro dia) |
| Soltar no painel "fora da semana" | `REMOVE` |
| Arrastar do painel para uma linha de técnico | `INCLUDE` |

Durante o arrasto, cada linha de técnico mostra quanto sobra na escala dela naquele dia, e a que
**não** comporta a duração mostra `não cabe · faltam 1,5h` — em tom de aviso, não de bloqueio.
Soltar continua permitido: o verificador avisa, ele não veta. Essa é a regra da feature inteira
aparecendo no gesto.

### Caminho de teclado, que é o caminho de verdade

Arrastar é atalho. Todo bloco é focável e responde a Enter com o mesmo menu:

```
Mover para outro dia      ▸  seg 18 · ter 19 · qua 20 …
Mover para outro técnico  ▸  [busca] Técnico-C6CBD5B6  6,5h/8h …
Tirar da semana
Por que esta ordem entrou
```

O submenu de técnico traz busca porque são 22 nomes pseudonimizados — lista sem filtro seria
cruel. Cada item do submenu mostra a carga daquele técnico no dia, então a escolha é informada
sem precisar sair do menu.

### O buraco e a sugestão

Quando um técnico fica com **1 h ou mais livre contígua** no dia, a linha mostra a faixa tracejada
`4,5h livres` e, dentro dela, até três ordens de fora que caberiam, ordenadas por score, cada uma
com `incluir aqui`. Nada entra sozinho. A sugestão é oferta, não decisão — o PCM continua sendo o
autor de todo ajuste.

### Painel "fora da semana"

Busca por número de OS e por título, com resultado por score. Cada cartão traz o motivo pelo qual
ficou de fora, a duração e o score, para a decisão de trazer ser informada. Sem resultado, o vazio
diz o que foi buscado e oferece limpar. O painel colapsa em tela estreita e vira uma aba.

### Estados

| Estado | O que a tela faz |
|---|---|
| Dia sem nenhuma alocação | Explica que o agente não alocou nada nesse dia e mostra por quê (fim de semana sem escala, ou sem capacidade), com atalho para incluir |
| Técnico sem escala no dia | A linha não aparece; um rodapé conta quantos estão sem escala e permite exibi-los |
| Arrastando | Origem esmaecida, alvos válidos realçados, HH restante em cada linha |
| Soltou e está aplicando | Bloco no destino em estado pendente; se falhar, volta para a origem com a mensagem do erro |
| Ajuste criou violação | Faixa abaixo da régua, tom de bloqueio, listando o que quebrou e oferecendo desfazer; o bloco culpado recebe marca |
| Sem ajustes | Barra de ajustes não existe. Tela limpa é o estado normal |
| Com ajustes | Barra fixa no rodapé: `3 ajustes seus · 2 violações criadas · desfazer último · ver todos` |
| Conflito de sessão (409) | "Outra sessão ajustou esta semana desde que você abriu" com botão para recarregar a revisão |
| Carregando a revisão | Esqueleto das linhas, sem spinner central: a estrutura do dia já é conhecida |

### Movimento

Um momento autoral, não efeitos espalhados: o bloco que chega ao destino assenta com uma
transição curta de posição e sombra, e a barra de carga do técnico anima até o novo valor. Isso
existe porque o efeito de um ajuste é justamente redistribuir carga — a animação carrega
informação. `prefers-reduced-motion` corta as duas.

### Acessibilidade, não negociável

- Todo bloco é `button` focável, com nome acessível completo: título, hora, duração, técnico.
- O menu é a via completa: nada só existe no arrasto.
- Cada ajuste aplicado é anunciado em região `aria-live`: *"Inspeção pneumática movida para quarta,
  Técnico-C6CBD5B6, 14h30. Nenhuma violação nova."*
- Violação criada é anunciada com `role="alert"`.
- Alvo de toque mínimo de 44 px nos blocos e nos chips de dia.
- Nenhum estado depende só de cor: violação tem ícone e texto, mão humana tem marca e rótulo.

### Responsivo

Abaixo de 900 px a régua rola horizontalmente e o painel vira aba ao lado de "no dia". Abaixo de
640 px as linhas de técnico viram cartões empilhados, o arrasto é desativado e o menu passa a ser
a única via — sem aviso, porque o menu sempre foi a via principal.

### Vocabulário

"Ajuste" para a mão humana, "regra" para restrição, "montar de novo" para re-otimizar. Nunca
"editar", que sugere escrever na origem — e o app promete o contrário em toda tela. O botão diz
o que faz e a mensagem confirma com o mesmo verbo: *mover* → *movida*.

### O que um construtor não pode inventar

O horário exato (vem de `encaixar_janela`), o texto das violações (vem do verificador), a ordem
de quem aparece primeiro na linha (carga decrescente), e o limiar do buraco (1 h). Se faltar
decisão nesses pontos, pergunte — não escolha.

## Decisão e auditoria

`POST /decision` passa a gravar, além de quem/quando/por quê:
- `revision_sequence`: qual revisão foi aprovada (0 = proposta do agente, sem ajuste);
- `known_violations`: código, gravidade e operação de cada violação em pé no momento do aceite.

A tela da etapa 5 mostra, antes dos botões, quantos ajustes humanos existem e quantas violações
estão de pé — aprovar com violação é permitido, aprovar sem saber não.

## Testes (pytest)

- replay determinístico: mesma lista de ajustes produz a mesma solução, byte a byte;
- `encaixar_janela` acha o primeiro intervalo livre e respeita a malha de 15 min;
- ajuste que estoura a escala é aceito e gera `CAPACITY_EXCEEDED`;
- `REMOVE` devolve a operação às não-alocadas com motivo `MANUAL`;
- `must_include` que não cabe aparece como regra não cumprida, e não como silêncio;
- decisão grava `revision_sequence` e `known_violations`;
- restrições não alteram o resultado quando a lista está vazia (não-regressão do greedy-v1).

Front continua sem suíte: verificação por typecheck, build, detector do Impeccable e execução
real contra a API.

## Fora de escopo

Chat com o agente (spec próprio, somente-leitura), edição de duração, edição em massa, desfazer
seletivo no meio da pilha (só o último), e escrita na Tractian — que continua não existindo.

## Nota para o chat futuro

Se o chat ganhar poder de agir, ele deve emitir exatamente o mesmo `ScheduleAdjustment`, mudando
apenas `applied_by`. Assim toda mudança na semana — arrasto, menu ou conversa — tem tipo, autor,
momento e consequência verificada, e a auditoria não ganha um caminho paralelo.
