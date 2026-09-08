<!-- Artefatos usados como base para a saída:

- Templates.
- Schemas.
- Exemplos canônicos.
- Formulários.
- Estrutura de relatórios.
- Arquivos de configuração que serão copiados.

O que não colocar dentro da skill:

- Secrets.
- Credenciais.
- Implementação do agent loop.
- Estado de execução.
- Policies globais.
- Clientes de banco duplicados.
- Tools inteiras já existentes no harness.
- Dumps de documentação.
- Dependências não fixadas.
- Memória de usuários.
- Regras de autorização apenas textuais.

A skill pode declarar que determinada tool é necessária, mas a autorização real pertence a policies/ e src/agent/tools/. -->