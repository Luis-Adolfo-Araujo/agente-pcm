#!/usr/bin/env bash
# Publica a interface no GitHub Pages, no branch gh-pages.
#
# O Pages serve um repositório de projeto sob /<repositório>/, então o build
# precisa saber o subcaminho: é o que PAGES_BASE_PATH informa. NEXT_PUBLIC_DEMO
# liga o modo sem servidor, que lê os artefatos congelados de public/demo-api.
set -euo pipefail

raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repositorio="$(basename "$(git -C "$raiz" rev-parse --show-toplevel)")"
remoto="$(git -C "$raiz" remote get-url origin)"

cd "$raiz/web"
npm ci
PAGES_BASE_PATH="/$repositorio" NEXT_PUBLIC_DEMO=1 npm run build

# O Pages não roda Jekyll aqui: sem isso ele esconde tudo que começa com _,
# e o Next serve o bundle inteiro de _next.
touch out/.nojekyll

publicacao="$(mktemp -d)"
trap 'rm -rf "$publicacao"' EXIT
cp -R out/. "$publicacao"

cd "$publicacao"
git init -q -b gh-pages
git add -A
git commit -q -m "deploy: interface do Agente Programador de PCM"
git push -f "$remoto" gh-pages

echo "Publicado. Em um minuto: https://$(git -C "$raiz" remote get-url origin | sed -E 's#.*[:/]([^/]+)/([^/]+)\.git#\1.github.io/\2#')/"
