---
name: check-materials
description: Avaliar prontidão de materiais de operações de manutenção a partir de requisitos, saldo, reservas e prazo esperado. Usar antes da programação para distinguir disponível, parcial, indisponível e desconhecido, sem confundir falta de saldo com falta de cadastro.
---

# Disponibilidade de materiais

Cobre a atividade "Verificar disponibilidade de materiais" da etapa de
programação do processo do PCM.

1. Chamar a ferramenta estruturada usando o snapshot de estoque autorizado.
2. Comparar quantidade requerida com saldo líquido e reservas.
3. Considerar entrada esperada apenas quando sua data estiver registrada.
4. Separar falta de saldo de falta de informação.
5. Entregar itens bloqueadores e próxima ação, sem abrir compra automaticamente.

Não reduzir a prioridade da OS por falta de material. Marcar a prontidão como bloqueada.

## Ordem sem material cadastrado

Ausência de requisito cadastrado não declara dispensa de material. No Planta Modelo ela
costuma indicar diagnóstico ainda desconhecido ou item sem saldo, então o status
é `unknown` com o código `material_requirement_not_registered`, nunca
"não requer material". Se essa ausência impede ou não a programação é decisão de
política, em `MaterialConfig.block_unregistered_material`.

## Fronteira com o trabalho manual

Buscar o código do material e vinculá-lo à ordem continua sendo a etapa manual
"Atribuição de materiais". Esta skill avalia o que já está vinculado.
