---
name: estimate-duration
description: Estimar duração de operações de manutenção usando valor planejado válido e histórico anterior ao snapshot, com fallback e confiança explícitos. Usar antes de calcular alocação e sempre que uma duração estiver ausente ou divergir do histórico.
---

# Estimativa de duração

Cobre três atividades do processo do PCM: "Levanta a duração da atividade",
"Atribui a duração da ordem" e "Revisar durações conforme histórico".

1. Validar o instante `as_of` e ignorar execuções futuras, abertas ou inválidas.
2. Chamar a ferramenta estruturada de duração.
3. Preservar a fonte, P50, P80, tamanho da amostra e confiança.
4. Tratar duração de calendário e HH total como medidas diferentes.
5. Sinalizar fallback e baixa confiança.

Não inventar duração pelo texto. Não usar intervalos pendurados como exemplos válidos.

## Fronteira com o trabalho manual

Quando existe duração planejada válida, a fonte é `planned` e a skill apenas a
confirma. O ganho aparece nas ordens sem duração cadastrada e na divergência
contra o histórico. Quantidade de pessoas é entrada cadastrada pelo PCM, não
resultado desta skill.
