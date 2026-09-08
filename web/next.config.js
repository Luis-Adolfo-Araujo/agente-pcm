/** @type {import('next').NextConfig} */
// A interface é toda cliente: quem serve dado é a API do agente. Exportada
// como arquivo estático, ela é montada na raiz da própria API, e o navegador
// nunca sai da origem — sem CORS e sem uma segunda URL para manter viva.
module.exports = { reactStrictMode: true, output: 'export', trailingSlash: true };
