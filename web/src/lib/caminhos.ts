/**
 * Onde a página está montada.
 *
 * Servida da raiz de um domínio, o prefixo é vazio. Servida de um subcaminho —
 * o do GitHub Pages, por exemplo — todo arquivo do `public/` mora abaixo dele,
 * e um caminho absoluto escrito à mão erraria o alvo. O `basePath` do Next
 * corrige o que ele mesmo emite; o que nasce em `string` dentro do código,
 * como o `src` de uma imagem, precisa deste prefixo.
 */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

export function asset(caminho: string): string {
  return `${BASE_PATH}${caminho}`;
}
