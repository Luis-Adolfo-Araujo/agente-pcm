---
name: treat-notes
description: Triar um lote de notas de manutenção sugerindo duplicidade, tipo de nota e prioridade, com bloqueio determinístico e adjudicação restrita à faixa cinzenta. Usar antes da criação das ordens, nunca dentro do workflow de programação.
---

# Tratamento de notas

Cobre a etapa "Tratamento das notas" do processo de PCM, nas atividades de
duplicidade, tipo de nota e prioridade.

1. Validar `tenant_id` e `as_of` do lote.
2. Gerar pares candidatos por ativo e janela temporal, ou por similaridade de
   texto quando o ativo é desconhecido.
3. Pontuar cada par de forma determinística e resolver os extremos sem modelo.
4. Consultar o adjudicador somente na faixa cinzenta, entregando apenas os dois
   textos, datas e ativo.
5. Devolver sugestão com confiança, origem e política por campo.

Ativo desconhecido é ausência de informação, não prova de que os ativos diferem:
a parcela sai do cálculo em vez de pontuar zero.

## Fronteira

Esta skill não entra em `generate_schedule` e não é carregada pelo
`ProgrammerAgent`. Ela produz sugestões sobre notas; existe um portão humano
antes de qualquer ordem chegar ao snapshot de planejamento. Nenhuma inferência
preenche campo consumido pelas skills determinísticas.

Duração, material e executante não são responsabilidade desta skill:
`estimate-duration`, `check-materials` e `suggest-executants` já os resolvem
sobre ordens, de forma determinística.

## Falha segura

Sem adjudicador disponível, ou quando ele falha, a faixa cinzenta vira
`needs_review`. Nunca `unique`: devolver trabalho ao humano custa menos que
afirmar unicidade errada.
