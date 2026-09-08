---
name: suggest-executants
description: Ordenar candidatos a executante por elegibilidade, equipe, capacidade e evidências históricas de ativo, atividade e localização. Usar depois de estimar duração e calcular capacidade, antes do otimizador escolher pessoa e horário.
---

# Sugestão de executantes

Cobre a atividade "Atribuir ordens aos executantes padrão" da etapa de
programação do processo do PCM.

1. Usar duração e capacidade calculadas no mesmo snapshot.
2. Aplicar qualificações obrigatórias como restrições, quando cadastradas.
3. Chamar a ferramenta estruturada para produzir candidatos ordenados.
4. Separar experiência histórica, elegibilidade e disponibilidade.
5. Sinalizar quando não houver candidato compatível.

Não inferir certificação a partir do número de execuções. A skill sugere candidatos; o otimizador decide a alocação.

## Fronteira com o trabalho manual

"Atribuir data e hora" é do otimizador, não desta skill. "Revisar ordem de
execução das atividades" não é coberta por nenhuma skill: não existe precedência
entre operações no domínio, e a sequência continua sendo decidida pelo PCM.
