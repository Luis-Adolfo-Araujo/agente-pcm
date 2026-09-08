* Copiloto de PCM (M Dias Branco)



Épico 1 — Porteiro Inteligente (Tratamento de Notas → Priorização)

US-01 — Upload de lote de notas
Como Programador de PCM, quero fazer upload de uma planilha de notas em aberto, para que o copiloto avalie o lote inteiro de uma vez em vez de nota a nota.
Critérios de aceite:
	•	O sistema aceita o template padrão exportado do SAP
	•	Aceita lotes de pelo menos 1.500 notas (volume diário médio: 15.000/mês)
	•	Retorna erro legível quando colunas obrigatórias estão ausentes
	•	O arquivo de saída preserva as colunas originais e adiciona colunas de insight

US-02 — Detecção de duplicidade
Como Programador de PCM, quero que o copiloto identifique notas duplicadas, para eliminar retrabalho no tratamento.
Critérios de aceite:
	•	Coluna duplicidade indicando Sim/Não e a nota de referência
	•	Recomendação explícita de cancelamento
	•	Duplicidade avaliada por similaridade semântica de descrição + equipamento + janela temporal, não só por match exato

US-03 — Validação do tipo de nota
Como Programador de PCM, quero que o copiloto valide se o tipo de nota está correto, para reduzir correção manual a jusante.
Critérios de aceite: coluna com tipo sugerido + flag quando diverge do informado + justificativa curta

US-04 — Sugestão de prioridade
Como Programador de PCM, quero receber a prioridade sugerida para cada nota, com base nos critérios de priorização vigentes e no histórico.

US-05 — Componente defeituoso e modo de falha
Como Programador de PCM, quero que o copiloto infira componente defeituoso e modo de falha a partir da descrição da nota, para padronizar o registro sem depender da qualidade do texto de origem.
Critérios de aceite: valores restritos ao catálogo válido do SAP + indicador de confiança quando a inferência for fraca

US-06 — Identificação de Lista de Tarefa existente
Como Programador de PCM, quero saber se já existe LT/procedimento padrão aplicável à solicitação, para não recriar plano de trabalho do zero.

US-07 — Levantamento de material, duração e recursos
Como Programador de PCM, quero que o copiloto sugira material necessário, duração e quantidade de pessoas com base no histórico de execuções similares.
Critérios de aceite: material identificado por código SAP (não descrição livre) + referência ao histórico usado ("baseado em N ordens similares")

US-08 — Centro de trabalho e especialidade
Como Programador de PCM, quero a especialidade e o centro de trabalho sugeridos, para direcionar a nota corretamente.

US-09 — Descrição revisada para conversão em ordem
Como Programador de PCM, quero que o copiloto reescreva a descrição no padrão de ordem, para que a conversão nota → ordem não exija reedição.

US-10 — Tipo de atividade e tipo de desativação
Como Programador de PCM, quero receber tipo de atividade e se a intervenção é com máquina parada ou rodando.



* Épico 2 — Copiloto de Programação

US-11 — Upload de ordens a programar
Como Programador de PCM, quero subir o conjunto de ordens que desejo programar, definindo eu mesmo o período, para acomodar minha cadência de trabalho.
Critérios de aceite: usuário define recorte (dia / semana / quinzena / período X-Y livre) no momento do upload; sem período fixo imposto pelo sistema

US-12 — Upload da escala de trabalho
Como Programador de PCM, quero informar a escala do período — quem está disponível, em que horários — para que a alocação sugerida seja factível.

US-13 — Priorização da carteira de ordens
Como Programador de PCM, quero uma ordem de execução sugerida para a carteira, para saber por onde começar.

US-14 — Alocação sugerida de executantes
Como Programador de PCM, quero que o copiloto sugira quem executa cada ordem, com base no padrão histórico de alocação e na disponibilidade informada.
Critérios de aceite: respeita a escala; respeita regras de negócio cadastradas (ver US-21); indica quando a atividade exige mais de uma pessoa

US-15 — Data e hora de início e fim
Como Programador de PCM, quero data/hora sugeridas para cada ordem, respeitando a escala e a sequência de execução.

US-16 — Validação de duração contra apontamentos reais
Como Programador de PCM, quero saber quando a duração planejada diverge da média histórica de execução, para corrigir estimativas irreais.
Critérios de aceite: exibe média histórica + quantidade de apontamentos que sustentam a média + flag de divergência

US-17 — Disponibilidade de material e gatilho de compra
Como Programador de PCM, quero saber se o material da ordem está disponível em estoque e, se não estiver, ser alertado da necessidade de requisição de compra.
Critérios de aceite: status por ordem (disponível / indisponível / parcial) + sinalização de necessidade de RC

* Épico 3 — Portal, Dashboard e Balanceamento Visual

US-18 — Portal com chat e upload
Como Programador de PCM, quero uma interface única onde converso com o copiloto, subo arquivos e vejo resultados, para não trabalhar apenas via troca de planilhas.

US-19 — Visualização de balanceamento de recursos
Como Programador de PCM, quero ver graficamente a carga alocada por pessoa e por especialidade, para identificar desbalanceamentos (ex.: João com 60h e José com 20h no mesmo período).
Critérios de aceite: visão por pessoa e por especialidade; drill-down ao clicar; formato Gantt ou barras

US-20 — Ajuste manual direto na tela
Como Programador de PCM, quero arrastar e ajustar a alocação diretamente no gráfico, para equalizar a carga sem editar planilha.
Critérios de aceite: ajuste por drag (estilo Kanban/Gantt do SAP); ao salvar, o delta é enviado como feedback ao agente (ver US-22)

* Épico 4 — Human-in-the-Loop e Regras de Negócio Vivas

US-21 — Cadastro de regra em linguagem natural
Como Programador de PCM, quero escrever regras próprias em linguagem natural, para que a IA incorpore minha experiência nas próximas programações.
Exemplo: "Sempre que for atividade da embaladora XYZ, atribuir ao padrinho da máquina, [nome]."
Critérios de aceite:
	•	Regras persistem entre sessões e entre lotes
	•	Regras são visíveis, editáveis e removíveis pelo autor
	•	O copiloto indica qual regra motivou uma sugestão específica
	•	Escopo da regra é explícito (global / área / equipamento)

US-22 — Feedback de correção como aprendizado
Como Programador de PCM, quero que minhas correções manuais alimentem o copiloto, para que ele não repita o mesmo erro.

US-23 — Rastreabilidade sugestão vs. decisão
Como Coordenador de Manutenção, quero ver o que o copiloto sugeriu e o que o programador efetivamente decidiu, para auditar e medir confiabilidade.

* Épico 5 — Saída para SAP

US-24 — Exportação em template de carga em massa
Como Programador de PCM, quero exportar o resultado no template exato de carga do SAP, para subir em massa com o mínimo de atrito.
Critérios de aceite: template obtido a partir de extração do próprio SAP; sem necessidade de reordenar colunas ou reformatar campos; validação prévia de campos obrigatórios antes do download

US-25 — Base de consulta no Data Lake
Como Time de Dados/TI, quero que o copiloto consuma exclusivamente o Data Lake (D-1) como base de histórico e consulta, sem escrita direta no SAP, para atender à política de cibersegurança.
Critérios de aceite: nenhuma conexão de escrita ao ERP; o copiloto exibe a data-base dos dados consultados ao usuário

* Épico 6 — Medição do Business Case

US-26 — Taxa de aceitação por tipo de sugestão
Como Coordenador de Manutenção, quero acompanhar a taxa de aceitação de cada tipo de sugestão (prioridade, modo de falha, material, executante...), para saber onde o copiloto é confiável e onde ainda não é.

US-27 — Tempo real economizado por etapa
Como Coordenador de Manutenção, quero medir o tempo efetivo gasto por etapa após a adoção, para validar a redução projetada de 3.258h/mês.
