/** @type {import('next').NextConfig} */
// A interface é toda cliente, então exporta como arquivo estático. Na
// demonstração pública ela vai para um subcaminho do GitHub Pages, e é
// `PAGES_BASE_PATH` que informa qual — vazio para servir da raiz de um domínio
// próprio ou ao lado da API.
const basePath = process.env.PAGES_BASE_PATH ?? '';

module.exports = {
  reactStrictMode: true,
  output: 'export',
  trailingSlash: true,
  basePath,
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};
