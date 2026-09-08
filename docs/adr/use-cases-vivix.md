* Priorização de Backlog

US-01 — Ranking composto por criticidade, idade e SLA
Como planejador de PCM, quero que o agente ordene o backlog combinando prioridade, criticidade do ativo, dias em aberto e SLA restante, para que eu deixe de perder ordens vencendo por olhar só o nível de prioridade.
 
Critérios de aceite
 
-       O score cruza, no mínimo: nível de prioridade (muito alto/alto/médio/baixo), SLA correspondente (1/10/30/45 dias), dias decorridos desde a abertura e criticidade do ativo.
-       Uma OS média aberta há 30 dias precisa ranquear acima de uma OS alta aberta ontem — este é o caso de teste de referência.
-       Cada OS exibe a justificativa do seu posicionamento em uma frase legível.
-       Os pesos do score são ajustáveis pelo PCM sem intervenção de TI.


US-02 — Alerta de vencimento de SLA
Como planejador de PCM, quero um filtro de um clique para "vencidas" e "vencendo nos próximos 7 dias", para que eu pare de fazer essa conta manualmente.
 
Critérios de aceite
 
-       O filtro está disponível na lista de backlog sem configuração prévia.
-       OS vencidas aparecem com o número de dias de atraso.
-       O agente informa o total de OS vencidas por prioridade e por área na abertura da reunião semanal.

US-0.3 — Agrupamento por oportunidade de execução
Como planejador de PCM, quero que o agente agrupe OS do mesmo equipamento, sistema ou área que possam ser executadas na mesma liberação, para que eu não pague duas vezes o custo de parada e liberação do mesmo ativo.
 
Critérios de aceite
 
-       O agrupamento considera o mesmo ativo, o mesmo sistema e a mesma janela de liberação.
-       O agente informa a economia estimada de tempo do agrupamento.
-       O PCM pode desagrupar livremente.

* Triagem e aprovação de solicitações

US-1.1 — Sugestão de prioridade na aprovação
Como planejador de PCM, quero que o agente sugira a prioridade correta de cada solicitação recebida, comparando o texto, o equipamento e o sintoma com a matriz de criticidade interna, para que eu não precise reavaliar manualmente cada solicitação antes de aprová-la.
 
Critérios de aceite
 
-       O agente apresenta a prioridade escolhida pelo solicitante e a prioridade sugerida lado a lado, com a justificativa em uma frase.
-       Quando houver divergência, o agente destaca a solicitação; quando houver convergência, permite aprovação em lote.
-       A matriz de criticidade é configurável pelo PCM — a regra é interna, não do sistema.
-       Aprovação e reprovação continuam sendo decisão humana; o agente nunca aprova sozinho.

US-1.2 — Detecção de solicitação duplicada
Como planejador de PCM, quero que o agente identifique solicitações que se referem ao mesmo ativo e sintoma de uma OS já aberta, para que eu não gere ordens redundantes que depois entopem o backlog.
 
Critérios de aceite
 
-       Na tela de aprovação, solicitações com possível duplicidade exibem o número da OS existente e o grau de similaridade.
-       O agente compara ativo, componente, descrição livre e janela de tempo (ex.: 30 dias).
-       O PCM pode marcar como duplicada (vincula à OS original) ou como distinta (o agente aprende com a rejeição).

* Geração da programação semanal - Dor principal

US-2.1 — Proposta automática de programação semanal
Como planejador de PCM, quero que o agente proponha a programação da semana distribuindo as OS entre os colaboradores e os dias, para que a reunião de quinta-feira parta de uma proposta pronta em vez de uma planilha em branco.
 
Critérios de aceite
 
-       A proposta cobre o ciclo real: sábado a sexta, gerada a tempo da reunião de quinta.
-       Absorve as duas entradas: ordens sistemáticas geradas para a semana + OS do backlog priorizadas pelo ÉPICO 3.
-       Volume de referência: 120 a 200 OS distribuídas entre 15 a 18 pessoas.
-       Nenhuma OS bloqueada entra na proposta.
-       Cada alocação vem com a justificativa (prioridade, SLA, habilidade, disponibilidade).
-       A proposta é editável: o PCM e os coordenadores movem, removem e reatribuem livremente antes de publicar.

US-2.2 — Cruzamento de tempo estimado com capacidade
Como planejador de PCM, quero que a proposta compare o tempo estimado de cada OS com as horas disponíveis de cada pessoa, para que a equipe fique o mais produtiva possível sem sobrecarga.
 
Critérios de aceite
 
-       OS sistemáticas usam o tempo estimado do plano; OS não sistemáticas usam o tempo estimado no planejamento.
-       Quando não houver estimativa, o agente sugere uma com base no histórico de atividades semelhantes e marca como estimativa inferida.
-       O mapa exibe, por pessoa e por dia, horas alocadas / horas disponíveis, com destaque para sobre e subalocação.

US-2.3 — Alocação por habilidade
Como coordenador de manutenção, quero que o agente considere a especialidade de cada mantenedor ao sugerir o executante, para que a atividade caia com quem a executa melhor.
 
Critérios de aceite
 
-       O perfil de habilidade é derivado do histórico de execuções (tipo de ativo, tipo de atividade, tempo realizado vs. estimado) e é editável manualmente.
-       Ao sugerir um executante, o agente informa por que aquela pessoa (ex.: "executou 14 atividades neste tipo de redutor, tempo médio 18% abaixo do estimado").
-       O agente aponta quando uma atividade não tem nenhum executante disponível com o perfil adequado na semana.

US-2.4 — Reserva de recurso compartilhado
Como planejador de PCM, quero que a proposta considere a disponibilidade de recursos compartilhados, para que duas atividades não sejam programadas dependendo do mesmo munck no mesmo horário.
 
Critérios de aceite
 
-       Recursos compartilhados (munck, guindaste, equipe terceirizada contratada, ferramenta especial) são cadastráveis com disponibilidade por dia.
-       O agente bloqueia alocações conflitantes e explica o conflito.
-       Atividades que dependem de terceiro sob contrato exibem o contrato vinculado.

US-2.5 — Visão em grade colaborador × data
Como planejador de PCM, quero ver toda a semana numa única tela, com colaboradores nas linhas e datas nas colunas, para que eu deixe de manter a planilha paralela.
 
Critérios de aceite
 
-       Uma tela exibe 15 a 18 pessoas × 7 dias com as OS alocadas, sem rolagem infinita nem sobreposição visual.
-       Cada célula mostra número da OS, atividade resumida e horário.
-       A grade é agrupável por equipe (ADM, turno, terceiros) e traz visualmente quem está de folga ou de férias.
-       Critério de sucesso do épico: o PCM consegue fechar a programação da semana sem abrir o Excel.
 
US-2.6 — Gravação da programação no sistema em lote
Como planejador de PCM, quero publicar a programação aprovada e ter executante, data e horário gravados automaticamente em cada OS, para que eu não relance 120 a 200 ordens manualmente toda semana.
 
Critérios de aceite
 
-       Uma ação de publicação grava todas as alocações da semana nas OS correspondentes.
-       O agente retorna um relatório de confirmação: gravadas com sucesso, falhas e o motivo de cada falha.
-       Alterações posteriores no mapa sincronizam de forma incremental, sem reescrever a semana inteira.
-       Meta: eliminar 100% da redigitação manual.

* Acompanhamento diário e replanejamento

US-3.1 — Digest diário de execução
Como planejador de PCM, quero receber toda manhã o resultado do dia anterior, para que eu pare de conferir ordem por ordem para saber o que aconteceu.
 
Critérios de aceite
 
-       O digest traz: programado vs. executado no dia, executado fora do dia programado, não iniciado, iniciado e não concluído, e o motivo quando registrado.
-       Compara horas apontadas com horas estimadas, destacando desvios relevantes em ambas as direções.
-       É entregue no início do expediente, sem ação do usuário.
-       Existe também um resumo semanal consolidado para o gestor.

US-3.2 — Higiene de ordens penduradas
Como planejador de PCM, quero que o agente aponte ordens em situação inconsistente, para que o backlog reflita a realidade da operação.
 
Critérios de aceite
 
-       O agente lista OS em progresso há mais tempo que o estimado, OS iniciadas e nunca finalizadas, e OS provavelmente executadas mas ainda abertas.
-       Distingue os casos citados na reunião: esqueceu de fechar · iniciou e não concluiu · foi executada por outra pessoa · nem chegou a iniciar.
-       Sugere a ação para cada caso e permite tratamento em lote.
-       Lembrete: o apontamento só sobe para o SAP no fechamento da ordem — ordens penduradas travam custo e indicador.

US-3.3 — Replanejamento de atividade não concluída
Como coordenador de manutenção, quero reprogramar rapidamente a atividade que não terminou no dia, para que o remanejamento não me custe uma nova rodada de planejamento manual.
 
Critérios de aceite
 
-       Ao registrar uma atividade abortada ou incompleta, o agente propõe uma nova data considerando capacidade e o SLA original.
-       Trata o caso observado na reunião: a atividade consumiu um dia inteiro em preparação (montagem de estrutura, liberação, limpeza) e a execução escorregou para o dia seguinte.
-       Registra o motivo da não conclusão em categorias reaproveitáveis para análise.
-       O impacto no restante da semana é mostrado antes de confirmar.

US-3.4 — Absorção de corretiva sem perder rastro
Como coordenador de manutenção, quero encaixar uma corretiva urgente indicando o que sai do lugar, para que o que deixou de ser feito continue rastreado.
 
Critérios de aceite
 
-       Ao inserir uma emergência, o agente sugere qual atividade de menor prioridade ceder espaço e mostra o impacto no SLA da atividade deslocada.
-       A atividade deslocada volta ao backlog com o histórico do deslocamento, e não simplesmente "não executada".
-       Nota de escopo: no indicador mensal esta não foi apontada como dor relevante — a prioridade aqui é a rastreabilidade, não a otimização.

* Indicadores, custo e aprendizado 

US-4.1 — Aderência à programação
Como gestor de manutenção, quero um indicador automático de aderência da programação, para que eu saiba quanto do que foi planejado aconteceu no dia planejado.
 
Critérios de aceite
 
-       Calcula: % de OS executadas, % executadas no dia programado, % executadas pelo executante programado.
-       Disponível por dia, por semana, por equipe e por coordenador.
-       Série histórica preservada para acompanhar evolução.

US-4.2 — Taxa de apontamento (tempo de chave na mão)
Como gestor de manutenção, quero o indicador de horas apontadas sobre horas disponíveis calculado automaticamente, para que eu deixe de montar essa conta na planilha.
 
Critérios de aceite
 
-       Base de horas disponíveis conforme o regime de cada colaborador (ADM 10h/5h; turno conforme escala 3x3).
-       Sinaliza apontamento acima de 100% (indício de hora extra ou atividade fora do horário) e abaixo do piso definido.
-       Consolidação semanal por pessoa, equipe e planta.

US-4.3 — Custo consolidado por OS
Como gestor de manutenção, quero ver o custo total de uma ordem sem sair para o SAP, para que o acompanhamento diário de custo pare de depender de extração manual.
 
Critérios de aceite
 
-       Consolida as três parcelas usadas hoje: atividade (HH apontado), material (compra direta e retirada de almoxarifado) e serviço (mão de obra externa, contrato guarda-chuva, usinagem, locação de equipamento).
-       Mostra o acumulado do mês contra a meta, com a variação do dia — replicando o acompanhamento diário que já é feito.
-       Para contratos guarda-chuva, exibe o saldo restante a autorizar.
