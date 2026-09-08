import type { Assignment, Backlog, Capacity } from '@/lib/api';
import { carga, diaDe, escalaDoDia, minutosDe } from '@/lib/semana';

/**
 * O que a célula está dizendo. É estado, e não uma faixa de cor, porque o
 * mesmo nome precisa aparecer no rótulo: a matriz nunca informa só por cor.
 */
export type EstadoCelula = 'sem-escala' | 'ocioso' | 'dentro' | 'cheio' | 'estourou';

/** O dia de uma pessoa, visto de cima — uma barra, não uma fila de relógio. */
export type CelulaSemana = {
  dia: string;
  /** Em ordem de relógio, para quando a linha abre. */
  ordens: Assignment[];
  minutos: number;
  escala: number;
  /**
   * Percentual da escala ocupado. `null` quando não há escala declarada: sem
   * divisor a ocupação não existe, e escrever 0% ali seria afirmar folga onde
   * não há jornada nenhuma.
   */
  ocupacao: number | null;
  estado: EstadoCelula;
};

export type LinhaSemana = {
  tecnico: string;
  celulas: CelulaSemana[];
  minutos: number;
  escala: number;
  ocupacao: number | null;
  /** Qualquer célula estourada — inclusive carga caída em dia sem escala. */
  estourou: boolean;
  ordens: number;
};

/**
 * Carga sem escala é estouro, não folga: a ordem está num dia em que a pessoa
 * não tem jornada declarada. Cem por cento cravado ainda é escala fechada; o
 * estouro começa no minuto seguinte.
 */
export function estadoDaCelula(minutos: number, escala: number): EstadoCelula {
  if (escala === 0) return minutos > 0 ? 'estourou' : 'sem-escala';
  if (minutos === 0) return 'ocioso';
  const ocupacao = (minutos / escala) * 100;
  if (ocupacao > 100) return 'estourou';
  return ocupacao >= 90 ? 'cheio' : 'dentro';
}

function ocupacaoDe(minutos: number, escala: number): number | null {
  return escala > 0 ? (minutos / escala) * 100 : null;
}

/**
 * A semana inteira, uma linha por pessoa.
 *
 * Entra quem tem escala em algum dia do período e também quem carrega ordem sem
 * ter escala nenhuma — esconder o segundo caso apagaria da tela justamente a
 * alocação que não deveria existir, que é a mesma regra de `colunasDoDia`.
 */
export function linhasDaSemana(
  assignments: Assignment[],
  capacidades: Capacity[],
  dias: string[],
): LinhaSemana[] {
  const noPeriodo = new Set(dias);
  const porTecnico = new Map<string, Map<string, Assignment[]>>();

  const garantir = (tecnico: string) => {
    if (!porTecnico.has(tecnico)) porTecnico.set(tecnico, new Map());
    return porTecnico.get(tecnico)!;
  };

  capacidades.forEach((c) => {
    if (c.slots.some((slot) => noPeriodo.has(diaDe(slot.window.start)))) garantir(c.worker_id);
  });
  assignments.forEach((a) => {
    const dia = diaDe(a.window.start);
    if (!noPeriodo.has(dia)) return;
    a.worker_ids.forEach((w) => {
      const doDia = garantir(w);
      doDia.set(dia, [...(doDia.get(dia) ?? []), a]);
    });
  });

  return [...porTecnico.entries()]
    .map(([tecnico, porDia]): LinhaSemana => {
      const celulas = dias.map((dia): CelulaSemana => {
        const ordens = [...(porDia.get(dia) ?? [])]
          .sort((a, b) => a.window.start.localeCompare(b.window.start));
        const minutos = carga(ordens);
        const escala = escalaDoDia(capacidades, tecnico, dia);
        return { dia, ordens, minutos, escala, ocupacao: ocupacaoDe(minutos, escala), estado: estadoDaCelula(minutos, escala) };
      });
      const minutos = celulas.reduce((soma, c) => soma + c.minutos, 0);
      const escala = celulas.reduce((soma, c) => soma + c.escala, 0);
      return {
        tecnico,
        celulas,
        minutos,
        escala,
        ocupacao: ocupacaoDe(minutos, escala),
        estourou: celulas.some((c) => c.estado === 'estourou'),
        ordens: new Set(celulas.flatMap((c) => c.ordens.map((a) => a.operation_id))).size,
      };
    })
    .sort((a, b) => porOcupacao(a, b) || a.tecnico.localeCompare(b.tecnico));
}

/**
 * Maior ocupação primeiro, e quem não tem escala nenhuma antes de todos: uma
 * ordem alocada fora de qualquer jornada é o pior caso da semana, e ele não
 * pode ficar no fim da lista só porque a divisão não fecha.
 */
function porOcupacao(a: LinhaSemana, b: LinhaSemana): number {
  if (a.ocupacao === null && b.ocupacao === null) return 0;
  if (a.ocupacao === null) return -1;
  if (b.ocupacao === null) return 1;
  return b.ocupacao - a.ocupacao;
}

/** A ocupação da equipe num dia: soma das cargas sobre soma das escalas. */
export function ocupacaoDoDia(linhas: LinhaSemana[], dia: string): number | null {
  let minutos = 0;
  let escala = 0;
  linhas.forEach((linha) => {
    const celula = linha.celulas.find((c) => c.dia === dia);
    if (!celula) return;
    minutos += celula.minutos;
    escala += celula.escala;
  });
  return ocupacaoDe(minutos, escala);
}

export type Locais = { distintos: string[]; porOrdem: Map<string, string> };

/**
 * Os locais que o backlog tem. São ids crus da origem: a tela rotula "Local
 * (código)" em vez de fingir que conhece o nome deles.
 */
export function locaisDoBacklog(backlog: Backlog): Locais {
  const porOrdem = new Map<string, string>();
  backlog.backlog.forEach((item) => {
    const local = item.operation.location_id;
    if (local) porOrdem.set(item.operation.operation_id, local);
  });
  return { distintos: [...new Set(porOrdem.values())].sort((a, b) => a.localeCompare(b)), porOrdem };
}

export type FiltroSemana = { busca: string; soEstouro: boolean; local: string };

export type IndicesDoFiltro = {
  titulos: Map<string, string>;
  /** O identificador da OS, que é o que quem programa tem no papel. */
  ids: Map<string, string>;
  locais: Map<string, string>;
};

/** Sem acento e sem caixa: quem digita "mecanico" quer achar "mecânico". */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

/**
 * O filtro esconde linha e cartão. Ele **não** mexe em `minutos`, `escala`,
 * `ocupacao` nem `estado`: esses continuam contando a semana inteira.
 *
 * Recalcular a barra sobre o recorte faria a tela mentir sobre capacidade —
 * filtrar por um local e ver a ocupação encolher diria que sobrou HH que não
 * sobrou. O recorte muda o que se vê, nunca o que se afirma.
 */
export function filtrarLinhas(
  linhas: LinhaSemana[],
  filtro: FiltroSemana,
  indices: IndicesDoFiltro,
): LinhaSemana[] {
  const busca = normalizar(filtro.busca.trim());
  const recorta = busca.length > 0 || filtro.local.length > 0;

  const casa = (a: Assignment) => {
    if (filtro.local && indices.locais.get(a.operation_id) !== filtro.local) return false;
    if (!busca) return true;
    const titulo = normalizar(indices.titulos.get(a.operation_id) ?? '');
    const id = normalizar(indices.ids.get(a.operation_id) ?? a.work_order_id);
    return titulo.includes(busca) || id.includes(busca);
  };

  return linhas
    .filter((linha) => !filtro.soEstouro || linha.estourou)
    .map((linha) => (recorta
      ? { ...linha, celulas: linha.celulas.map((c) => ({ ...c, ordens: c.ordens.filter(casa) })) }
      : linha))
    .filter((linha) => !recorta || linha.celulas.some((c) => c.ordens.length > 0));
}

/** Quantas ordens a linha mostra depois do filtro. */
export function ordensVisiveis(linha: LinhaSemana): number {
  return linha.celulas.reduce((soma, c) => soma + c.ordens.length, 0);
}

/** Os minutos que a célula mostra depois do filtro, para o rótulo da expansão. */
export function minutosVisiveis(celula: CelulaSemana): number {
  return celula.ordens.reduce((soma, a) => soma + minutosDe(a), 0);
}

export type Solta = 'nada' | 'troca' | 'remanejo';

/**
 * O que a solta numa célula significa.
 *
 * O dia de origem sai da janela da ordem, e não de quem arrastou: `Arraste` só
 * carrega a pessoa, e a matriz mostra a mesma pessoa em cinco dias.
 *
 * Mudar de dia é um remanejo só, mesmo levando outra pessoa junto — `Remanejo`
 * já carrega `paraDia` e `paraTecnico`. Gravar também uma troca ensinaria o
 * agente a desconfiar de uma escolha de executante que estava certa para o dia
 * original.
 */
export function decidirSolta(
  ordem: Assignment,
  deTecnico: string,
  paraTecnico: string,
  paraDia: string,
): Solta {
  if (diaDe(ordem.window.start) !== paraDia) return 'remanejo';
  return deTecnico === paraTecnico ? 'nada' : 'troca';
}

/** Carga e escala que a célula de destino já tem, para o aviso do popover. */
export function destinoDaCelula(
  linhas: LinhaSemana[],
  tecnico: string,
  dia: string,
): { worker_id: string; carga: number; escala: number } | null {
  const linha = linhas.find((l) => l.tecnico === tecnico);
  const celula = linha?.celulas.find((c) => c.dia === dia);
  if (!celula) return null;
  return { worker_id: tecnico, carga: celula.minutos, escala: celula.escala };
}
