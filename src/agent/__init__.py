# Utiliza a anatomia H para construção de agentes.

# H = (E, T, C, S, L, V) — um harness é a soma de seis componentes:

# E — o laço: quando chamar o modelo de novo, quando parar, o que fazer no erro
# T — as ferramentas: quais existem, em que formato são chamadas
# C — o contexto: o que o modelo vê neste turno
# S — o estado: o que sobrevive a um crash
# L — lifecycle: onde política, segurança, custo e log são interceptados
# V — a trajetória: como você descobre por que falhou

# A tese: nenhum sistema é confiável em produção sem os seis.
# Ela mede cobertura, não qualidade: ter os seis não significa tê-los bem feitos.
#
# O harness é apenas uma das três camadas da arquitetura de referência:
# produto/domínio → agent runtime → plataforma operacional.
# Consulte guidelines/architecture.md para a visão completa.
