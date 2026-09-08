---
name: calculate-capacity
description: Calcular capacidade líquida de manutenção por pessoa e período usando escala, indisponibilidades e compromissos existentes. Usar antes de sugerir executantes e gerar a programação.
---

# Capacidade de manutenção

Sustenta a atividade "Balancear recursos" da etapa de programação do processo
do PCM.

1. Restringir slots ao período solicitado e ao timezone do tenant.
2. Subtrair compromissos confirmados sem dupla contagem.
3. Chamar a ferramenta estruturada e preservar capacidade bruta, comprometida e líquida.
4. Sinalizar pessoas sem escala conhecida.
5. Nunca retornar capacidade negativa.

Não interpretar frequência histórica como disponibilidade atual.

## Fronteira com o trabalho manual

A capacidade calculada é insumo do otimizador, que decide o balanceamento. A
skill informa quanto existe; ela não escolhe quem faz o quê.
