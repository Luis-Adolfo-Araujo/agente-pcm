#!/usr/bin/env bash
# Publica a árvore versionada como um Space Docker no Hugging Face.
#
# O Space quer um README.md com frontmatter na raiz, e o repositório do GitHub
# quer o seu próprio. Em vez de servir aos dois com um arquivo só, o envio
# monta uma cópia e troca o README no caminho.
#
#   deploy/space/publish.sh https://huggingface.co/spaces/<usuário>/<space>
#
# A autenticação é a do próprio Hugging Face: `hf auth login`, ou o token como
# senha quando o git pedir.
set -euo pipefail

destino="${1:?uso: deploy/space/publish.sh https://huggingface.co/spaces/<usuário>/<space>}"
raiz="$(git rev-parse --show-toplevel)"
trabalho="$(mktemp -d)"
trap 'rm -rf "$trabalho"' EXIT

git -C "$raiz" archive HEAD | tar -x -C "$trabalho"
cp "$raiz/deploy/space/README.md" "$trabalho/README.md"

cd "$trabalho"
git init -q -b main
git add -A
git commit -q -m "deploy: demonstração do Agente Programador de PCM"
git push -f "$destino" main

echo "Space atualizado: $destino"
