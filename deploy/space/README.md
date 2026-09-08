---
title: Agente Programador de PCM
emoji: 🔧
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Programação semanal de manutenção sobre uma planta fictícia
---

# Agente Programador de PCM

Monte a programação semanal de manutenção de uma planta inteira e veja por que
cada ordem entrou ou ficou de fora.

A planta é fictícia e gerada por semente: 96 ativos, 22 técnicos, 1.200 ordens
abertas, 1.466 execuções no histórico e 1.800 itens de estoque. Nenhum dado de
cliente participa da demonstração.

O backlog não cabe na semana de propósito. A rodada devolve 469 ordens
programadas, 529 sem hora-homem, 138 sem material e 64 bloqueadas — as quatro
saídas que quem programa precisa distinguir.

Nenhuma decisão numérica depende de LLM. As skills são determinísticas, um
verificador independente confere a proposta antes de ela aparecer, e a
aprovação é de uma pessoa.

Código, arquitetura e o gerador do mundo:
https://github.com/Luis-Adolfo-Araujo/agente-pcm
