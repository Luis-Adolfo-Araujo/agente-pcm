# Casos de Uso MAIA — Agente de PCM

As histórias abaixo consolidam as capacidades comuns identificadas nos levantamentos da M. Dias Branco e da Planta Modelo. A numeração segue a ordem estimada de impacto no PCM industrial, considerando redução de esforço manual, qualidade da programação, aderência ao plano e redução de retrabalho.

US-01 — Geração automática da programação do período

Como planejador de PCM, quero que o agente proponha a programação do período distribuindo as ordens entre colaboradores, datas e horários, para que eu parta de uma proposta pronta em vez de construir manualmente uma programação do zero.

Critérios de aceite

- O PCM pode definir livremente o período da programação, incluindo dia, semana, quinzena ou intervalo personalizado.
- A proposta considera, no mínimo, o backlog priorizado, ordens sistemáticas do período, criticidade, SLA, duração estimada, disponibilidade das pessoas e restrições operacionais cadastradas.
- Nenhuma ordem bloqueada ou sem dados mínimos obrigatórios entra na programação sem uma sinalização explícita.
- Cada alocação informa os principais fatores considerados na decisão.
- A proposta permanece em estado de rascunho até ser revisada e aprovada por uma pessoa autorizada.

US-02 — Ranking composto do backlog

Como planejador de PCM, quero que o agente ordene o backlog combinando prioridade, criticidade do ativo, idade da ordem e SLA restante, para que eu deixe de perder ordens importantes por considerar apenas a prioridade informada.

Critérios de aceite

- O score cruza, no mínimo, nível de prioridade, criticidade do ativo, dias decorridos desde a abertura e SLA restante.
- Ordens próximas do vencimento ou vencidas recebem tratamento compatível com o risco e a criticidade envolvidos.
- Cada ordem exibe uma justificativa legível para seu posicionamento no ranking.
- Os pesos do score são configuráveis pelo PCM sem necessidade de alteração no código.
- O ranking pode ser filtrado por período, área, equipe, ativo, prioridade e situação do SLA.

US-03 — Cruzamento da programação com escala e capacidade

Como planejador de PCM, quero que o agente compare a carga das ordens com a escala e as horas disponíveis de cada colaborador, para que a programação seja factível e não gere sobrecarga ou ociosidade evitável.

Critérios de aceite

- O cálculo respeita jornada, turno, folga, férias, afastamentos e indisponibilidades cadastradas.
- A programação exibe, por pessoa e por período, horas alocadas e horas disponíveis.
- Sobrecarga e subalocação são destacadas visualmente.
- O agente não aloca atividades fora da escala sem alertar e solicitar validação humana.
- Mudanças na escala permitem recalcular a proposta sem perder o histórico da versão anterior.

US-04 — Sugestão de executantes por habilidade e disponibilidade

Como planejador de PCM, quero que o agente sugira os executantes mais adequados para cada ordem, considerando especialidade, habilidade, experiência e disponibilidade, para que a atividade seja direcionada a quem tem melhores condições de executá-la.

Critérios de aceite

- A sugestão respeita a escala e as regras de qualificação, certificação ou especialidade aplicáveis.
- O perfil de habilidade pode utilizar o histórico de execuções e também ser ajustado manualmente por usuário autorizado.
- O agente explica resumidamente por que cada executante foi sugerido.
- Atividades que exigem mais de uma pessoa recebem a quantidade e a composição de equipe necessárias.
- Quando não houver pessoa disponível com o perfil adequado, o agente sinaliza a restrição em vez de realizar uma alocação incompatível.

US-05 — Publicação em lote da programação

Como planejador de PCM, quero publicar a programação aprovada em lote no formato aceito pelo sistema de manutenção da indústria, para que eu não precise atualizar cada ordem manualmente.

Critérios de aceite

- A publicação utiliza o adaptador definido para cada indústria, que pode ser integração por API, arquivo de carga ou outro mecanismo autorizado.
- Os campos obrigatórios são validados antes da publicação.
- O sistema apresenta uma prévia e exige confirmação humana antes de efetivar a publicação.
- O resultado identifica registros publicados com sucesso, registros com falha e o motivo de cada falha.
- A operação possui chave de idempotência para impedir duplicidade em caso de reenvio.
- Nenhuma escrita é realizada em sistema externo quando a política do cliente determinar operação somente leitura.

US-06 — Estimativa e validação da duração das atividades

Como planejador de PCM, quero que o agente valide a duração planejada e sugira uma estimativa quando necessário, para que a programação utilize tempos compatíveis com a execução real das atividades.

Critérios de aceite

- Quando existir duração planejada, o agente a compara com o histórico de execuções semelhantes.
- Quando não existir duração, o agente sugere uma estimativa e a identifica claramente como inferida.
- A sugestão informa a quantidade de execuções históricas utilizadas e uma medida de confiança.
- Divergências relevantes entre duração planejada, média histórica e duração realizada são destacadas.
- O planejador pode manter ou alterar a duração sugerida, registrando sua decisão.

US-07 — Sugestão de prioridade na triagem

Como planejador de PCM, quero que o agente sugira a prioridade correta das solicitações recebidas, considerando descrição, ativo, sintoma e matriz de criticidade, para que solicitações inadequadamente classificadas não contaminem o backlog.

Critérios de aceite

- A prioridade informada pelo solicitante e a prioridade sugerida são apresentadas lado a lado.
- Divergências são destacadas e acompanhadas de uma justificativa curta.
- A matriz de criticidade e as regras de priorização são configuráveis por indústria.
- Solicitações convergentes podem ser tratadas em lote, quando permitido pela política do cliente.
- Aprovação, rejeição ou alteração de prioridade permanecem decisões humanas.

US-08 — Ajuste humano da programação

Como planejador de PCM, quero mover, remover e reatribuir ordens diretamente na programação proposta, para que eu possa incorporar restrições e conhecimentos operacionais que não estejam disponíveis nos dados.

Critérios de aceite

- O usuário pode alterar executante, data, horário e sequência antes da publicação.
- O sistema recalcula carga, conflitos e impacto no restante da programação após cada ajuste.
- Violações de escala, habilidade, capacidade ou regra de negócio são exibidas antes da confirmação.
- O usuário pode confirmar justificadamente uma exceção quando possuir permissão para isso.
- A versão original da sugestão é preservada para comparação e auditoria.

US-09 — Visualização semanal e balanceamento de recursos

Como planejador de PCM, quero visualizar a programação completa por colaborador, equipe e data, para que eu identifique rapidamente sobrecargas, ociosidade e conflitos sem depender de planilhas paralelas.

Critérios de aceite

- A interface apresenta colaboradores ou equipes nas linhas e datas ou períodos nas colunas.
- Cada alocação exibe, no mínimo, identificação da ordem, atividade resumida, horário e duração.
- Folgas, férias, indisponibilidades, sobrecarga e subalocação possuem identificação visual distinta.
- A visualização permite agrupamento por equipe, especialidade, área ou tipo de vínculo.
- O usuário consegue acessar os detalhes de uma ordem a partir da própria programação.

US-10 — Detecção de solicitações duplicadas

Como planejador de PCM, quero que o agente identifique solicitações possivelmente duplicadas, para que ordens redundantes não gerem retrabalho nem aumentem artificialmente o backlog.

Critérios de aceite

- A comparação considera, no mínimo, ativo, componente ou sintoma, descrição e janela temporal configurável.
- A análise utiliza similaridade semântica e não apenas correspondência exata de texto.
- Cada possível duplicidade apresenta a solicitação ou ordem de referência e o grau de similaridade.
- O PCM pode confirmar a duplicidade, vincular os registros ou classificá-los como distintos.
- A decisão humana fica registrada e pode ser utilizada na avaliação futura do detector.

US-11 — Configuração de regras pelo PCM

Como planejador de PCM, quero cadastrar e ajustar regras de planejamento sem depender da equipe de TI, para que o agente reflita as particularidades operacionais de cada indústria, planta, área e equipamento.

Critérios de aceite

- Usuários autorizados podem criar, visualizar, editar, ativar, desativar e remover regras.
- Toda regra possui escopo explícito, como indústria, planta, área, equipe, classe de ativo ou equipamento.
- O sistema valida conflitos entre regras e informa qual delas possui precedência.
- Alterações são versionadas com autor, data, justificativa e período de vigência.
- O agente identifica as regras que influenciaram cada recomendação.

US-12 — Justificativa das recomendações

Como planejador de PCM, quero entender por que o agente priorizou ou alocou cada ordem, para que eu possa revisar a recomendação com segurança e explicar a decisão aos demais envolvidos.

Critérios de aceite

- Toda recomendação de prioridade, executante, duração ou data apresenta uma justificativa curta e legível.
- A justificativa referencia fatores efetivamente utilizados, como criticidade, SLA, disponibilidade, habilidade, histórico ou regra de negócio.
- O texto não apresenta dados ou motivos que não estejam presentes nas evidências da execução.
- O usuário pode consultar os dados e as regras que sustentaram a recomendação.
- Recomendações com baixa confiança ou dados incompletos são identificadas explicitamente.

US-13 — Aprendizado a partir de correções humanas

Como planejador de PCM, quero que minhas correções sejam registradas e utilizadas para melhorar sugestões futuras, para que o agente não repita continuamente os mesmos erros de priorização e programação.

Critérios de aceite

- O sistema registra o valor sugerido, o valor escolhido pelo usuário e o contexto da correção.
- O usuário pode informar o motivo da alteração por categoria ou texto complementar.
- Correções não modificam automaticamente regras críticas sem validação e aprovação apropriadas.
- O histórico de feedback pode ser utilizado em avaliações, ajustes de regras e evolução dos modelos.
- O sistema permite medir se erros anteriormente corrigidos voltaram a ocorrer.

US-14 — Rastreabilidade entre sugestão e decisão

Como coordenador de manutenção, quero comparar o que o agente sugeriu com o que o PCM decidiu e publicou, para que eu possa auditar o processo e medir a confiabilidade das recomendações.

Critérios de aceite

- Cada execução registra a sugestão original, os ajustes realizados, a decisão final e o responsável por cada alteração.
- O histórico preserva data, versão das regras, versão do planejamento e fontes de dados utilizadas.
- O sistema permite consultar diferenças por tipo de recomendação, período, equipe e usuário.
- A rastreabilidade permanece disponível após a publicação da programação.
- Os registros permitem calcular taxas de aceitação e alteração sem expor informações não autorizadas.
