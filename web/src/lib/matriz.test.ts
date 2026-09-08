import { describe, expect, it } from 'vitest';
import {
  decidirSolta, destinoDaCelula, estadoDaCelula, filtrarLinhas, linhasDaSemana, locaisDoBacklog,
  ocupacaoDoDia,
} from '@/lib/matriz';
import type { Assignment, Capacity, Enriched } from '@/lib/api';

function alocacao(op: string, workers: string[], inicio: string, fim: string): Assignment {
  return {
    work_order_id: `WO-${op}`,
    operation_id: op,
    worker_ids: workers,
    window: { start: inicio, end: fim },
    priority_score: 70,
    reason_codes: [],
  };
}

const capacidade = (worker: string, janelas: [string, string][]): Capacity => ({
  worker_id: worker,
  gross_minutes: 0,
  committed_minutes: 0,
  net_minutes: 0,
  slots: janelas.map(([start, end]) => ({ worker_id: worker, window: { start, end } })),
});

const SEG = '2026-08-17';
const TER = '2026-08-18';
const DIAS = [SEG, TER];
const t = (dia: string, hora: string) => `${dia}T${hora}:00-03:00`;

/** Oito horas de escala num dia, o caso comum. */
const oitoHoras = (dia: string): [string, string] => [t(dia, '08:00'), t(dia, '16:00')];

describe('estadoDaCelula', () => {
  it('chama de sem escala quem não tem escala nem carga', () => {
    expect(estadoDaCelula(0, 0)).toBe('sem-escala');
  });

  it('chama de estouro a carga que caiu em quem não tem escala', () => {
    expect(estadoDaCelula(60, 0)).toBe('estourou');
  });

  it('chama de ocioso quem tem escala e nenhuma carga', () => {
    expect(estadoDaCelula(0, 480)).toBe('ocioso');
  });

  it('fica dentro até 89 por cento', () => {
    expect(estadoDaCelula(427, 480)).toBe('dentro');
  });

  it('vira escala fechada a partir de 90 por cento', () => {
    expect(estadoDaCelula(432, 480)).toBe('cheio');
  });

  it('cem por cento cravado ainda é escala fechada, não estouro', () => {
    expect(estadoDaCelula(480, 480)).toBe('cheio');
  });

  it('vira estouro acima de cem por cento', () => {
    expect(estadoDaCelula(481, 480)).toBe('estourou');
  });
});

describe('linhasDaSemana', () => {
  it('dá linha a quem tem escala na semana mesmo sem nenhuma ordem', () => {
    const linhas = linhasDaSemana([], [capacidade('ana', [oitoHoras(SEG)])], DIAS);
    expect(linhas.map((l) => l.tecnico)).toEqual(['ana']);
    expect(linhas[0].ocupacao).toBe(0);
    expect(linhas[0].celulas.map((c) => c.estado)).toEqual(['ocioso', 'sem-escala']);
  });

  it('dá linha a quem carrega ordem sem ter escala nenhuma na semana', () => {
    const linhas = linhasDaSemana([alocacao('op-1', ['bruno'], t(SEG, '08:00'), t(SEG, '09:00'))], [], DIAS);
    expect(linhas.map((l) => l.tecnico)).toEqual(['bruno']);
    expect(linhas[0].ocupacao).toBeNull();
    expect(linhas[0].estourou).toBe(true);
  });

  it('uma célula por dia do período, na ordem dos dias', () => {
    const linhas = linhasDaSemana([], [capacidade('ana', [oitoHoras(TER)])], DIAS);
    expect(linhas[0].celulas.map((c) => c.dia)).toEqual([SEG, TER]);
  });

  it('conta a carga da célula só do dia dela', () => {
    const linhas = linhasDaSemana(
      [
        alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '12:00')),
        alocacao('op-2', ['ana'], t(TER, '08:00'), t(TER, '09:00')),
      ],
      [capacidade('ana', [oitoHoras(SEG), oitoHoras(TER)])],
      DIAS,
    );
    expect(linhas[0].celulas.map((c) => c.minutos)).toEqual([240, 60]);
    expect(linhas[0].celulas.map((c) => c.ocupacao)).toEqual([50, 12.5]);
  });

  it('põe as ordens da célula em ordem de relógio', () => {
    const linhas = linhasDaSemana(
      [
        alocacao('tarde', ['ana'], t(SEG, '14:00'), t(SEG, '15:00')),
        alocacao('manha', ['ana'], t(SEG, '08:00'), t(SEG, '09:00')),
      ],
      [capacidade('ana', [oitoHoras(SEG)])],
      DIAS,
    );
    expect(linhas[0].celulas[0].ordens.map((a) => a.operation_id)).toEqual(['manha', 'tarde']);
  });

  it('conta a ordem dividida na célula de cada executante', () => {
    const linhas = linhasDaSemana(
      [alocacao('op-1', ['ana', 'bruno'], t(SEG, '08:00'), t(SEG, '10:00'))],
      [capacidade('ana', [oitoHoras(SEG)]), capacidade('bruno', [oitoHoras(SEG)])],
      DIAS,
    );
    expect(linhas.map((l) => l.celulas[0].minutos)).toEqual([120, 120]);
  });

  it('a ocupação da semana é a soma das cargas sobre a soma das escalas, não a média das células', () => {
    const linhas = linhasDaSemana(
      [alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '16:00'))],
      // Oito horas na segunda, quatro na terça: a média das células daria 66,7%.
      [capacidade('ana', [oitoHoras(SEG), [t(TER, '08:00'), t(TER, '12:00')]])],
      DIAS,
    );
    expect(linhas[0].ocupacao).toBeCloseTo(66.67, 1);
    expect(linhas[0].minutos).toBe(480);
    expect(linhas[0].escala).toBe(720);
  });

  it('ordena por ocupação da semana, com o estouro no topo', () => {
    const linhas = linhasDaSemana(
      [
        alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '12:00')),
        alocacao('op-2', ['bruno'], t(SEG, '08:00'), t(SEG, '20:00')),
      ],
      [capacidade('ana', [oitoHoras(SEG)]), capacidade('bruno', [oitoHoras(SEG)])],
      DIAS,
    );
    expect(linhas.map((l) => l.tecnico)).toEqual(['bruno', 'ana']);
  });

  it('quem não tem escala e carrega ordem vem antes de todo mundo', () => {
    const linhas = linhasDaSemana(
      [
        alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '15:00')),
        alocacao('op-2', ['zeca'], t(SEG, '08:00'), t(SEG, '09:00')),
      ],
      [capacidade('ana', [oitoHoras(SEG)])],
      DIAS,
    );
    expect(linhas.map((l) => l.tecnico)).toEqual(['zeca', 'ana']);
  });

  it('desempata pelo nome', () => {
    const linhas = linhasDaSemana(
      [],
      [capacidade('bruno', [oitoHoras(SEG)]), capacidade('ana', [oitoHoras(SEG)])],
      DIAS,
    );
    expect(linhas.map((l) => l.tecnico)).toEqual(['ana', 'bruno']);
  });

  it('marca a linha como estourada quando qualquer célula estoura', () => {
    const linhas = linhasDaSemana(
      [alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '20:00'))],
      [capacidade('ana', [oitoHoras(SEG), oitoHoras(TER)])],
      DIAS,
    );
    // Na semana ela ocupa 75%; na segunda, 150%.
    expect(linhas[0].ocupacao).toBe(75);
    expect(linhas[0].estourou).toBe(true);
  });

  it('conta as ordens da linha uma vez só, mesmo espalhadas em vários dias', () => {
    const linhas = linhasDaSemana(
      [
        alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '09:00')),
        alocacao('op-2', ['ana'], t(TER, '08:00'), t(TER, '09:00')),
      ],
      [capacidade('ana', [oitoHoras(SEG), oitoHoras(TER)])],
      DIAS,
    );
    expect(linhas[0].ordens).toBe(2);
  });

  it('ignora alocação de fora do período', () => {
    const linhas = linhasDaSemana(
      [alocacao('op-1', ['ana'], '2026-08-25T08:00:00-03:00', '2026-08-25T09:00:00-03:00')],
      [capacidade('ana', [oitoHoras(SEG)])],
      DIAS,
    );
    expect(linhas[0].minutos).toBe(0);
    expect(linhas[0].ordens).toBe(0);
  });
});

describe('ocupacaoDoDia', () => {
  it('soma as cargas do dia sobre as escalas do dia', () => {
    const linhas = linhasDaSemana(
      [alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '12:00'))],
      [capacidade('ana', [oitoHoras(SEG)]), capacidade('bruno', [oitoHoras(SEG)])],
      DIAS,
    );
    // 240 minutos alocados numa equipe com 960 de escala na segunda.
    expect(ocupacaoDoDia(linhas, SEG)).toBe(25);
  });

  it('sem escala nenhuma no dia, a ocupação não existe', () => {
    const linhas = linhasDaSemana([], [capacidade('ana', [oitoHoras(SEG)])], DIAS);
    expect(ocupacaoDoDia(linhas, TER)).toBeNull();
  });
});

const enriquecida = (op: string, titulo: string, local: string | null): Enriched => ({
  operation: {
    work_order_id: `WO-${op}`,
    operation_id: op,
    title: titulo,
    priority_level: null,
    criticality: null,
    asset_id: null,
    location_id: local,
    planned_duration_minutes: null,
    due_at: null,
  },
  priority: { score: 0, band: 'low', model: '', reason_codes: [], missing_fields: [], components: [] },
  duration: { minutes: null, p50_minutes: null, p80_minutes: null, source: '', sample_size: 0, confidence: 0 },
  materials: { status: 'available', blocking: false, reason_codes: [] },
  executants: [],
  scheduled: true,
});

describe('locaisDoBacklog', () => {
  it('lista os locais distintos, em ordem, sem os que faltam', () => {
    const locais = locaisDoBacklog({
      backlog: [
        enriquecida('op-1', 'Trocar selo', 'LOC-B'),
        enriquecida('op-2', 'Lubrificar', 'LOC-A'),
        enriquecida('op-3', 'Inspeção', null),
        enriquecida('op-4', 'Alinhar', 'LOC-A'),
      ],
      capacities: [],
    });
    expect(locais.distintos).toEqual(['LOC-A', 'LOC-B']);
    expect(locais.porOrdem.get('op-1')).toBe('LOC-B');
    expect(locais.porOrdem.has('op-3')).toBe(false);
  });
});

describe('filtrarLinhas', () => {
  const linhas = () => linhasDaSemana(
    [
      alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '12:00')),
      alocacao('op-2', ['ana'], t(TER, '08:00'), t(TER, '09:00')),
      alocacao('op-3', ['bruno'], t(SEG, '08:00'), t(SEG, '20:00')),
    ],
    [capacidade('ana', [oitoHoras(SEG), oitoHoras(TER)]), capacidade('bruno', [oitoHoras(SEG)])],
    DIAS,
  );
  const indices = {
    titulos: new Map([['op-1', 'Trocar selo mecânico'], ['op-2', 'Lubrificar mancal'], ['op-3', 'Alinhar acoplamento']]),
    ids: new Map([['op-1', 'WO-op-1'], ['op-2', 'WO-op-2'], ['op-3', 'WO-op-3']]),
    locais: new Map([['op-1', 'LOC-A'], ['op-2', 'LOC-B'], ['op-3', 'LOC-A']]),
  };
  const vazio = { busca: '', soEstouro: false, local: '' };

  it('sem filtro devolve tudo como está', () => {
    expect(filtrarLinhas(linhas(), vazio, indices)).toEqual(linhas());
  });

  it('a busca casa com o título, sem acento e sem caixa', () => {
    const filtradas = filtrarLinhas(linhas(), { ...vazio, busca: 'mecanico' }, indices);
    expect(filtradas.map((l) => l.tecnico)).toEqual(['ana']);
    expect(filtradas[0].celulas.flatMap((c) => c.ordens.map((a) => a.operation_id))).toEqual(['op-1']);
  });

  it('a busca casa com o identificador da OS', () => {
    const filtradas = filtrarLinhas(linhas(), { ...vazio, busca: 'wo-op-3' }, indices);
    expect(filtradas.map((l) => l.tecnico)).toEqual(['bruno']);
  });

  it('a busca esconde a linha que não tem nenhuma ordem correspondente', () => {
    expect(filtrarLinhas(linhas(), { ...vazio, busca: 'lubrificar' }, indices).map((l) => l.tecnico))
      .toEqual(['ana']);
  });

  it('o filtro não mexe na ocupação: ela conta a semana inteira', () => {
    const filtradas = filtrarLinhas(linhas(), { ...vazio, busca: 'lubrificar' }, indices);
    // Só a ordem de uma hora sobra na tela, mas ana ocupa 5h de 16h de escala.
    expect(filtradas[0].celulas[0].ordens).toEqual([]);
    expect(filtradas[0].celulas[0].minutos).toBe(240);
    expect(filtradas[0].celulas[0].ocupacao).toBe(50);
    expect(filtradas[0].ocupacao).toBeCloseTo(31.25, 2);
  });

  it('só quem estourou deixa fora quem cabe na escala', () => {
    expect(filtrarLinhas(linhas(), { ...vazio, soEstouro: true }, indices).map((l) => l.tecnico))
      .toEqual(['bruno']);
  });

  it('o local deixa só as linhas com ordem naquele local', () => {
    expect(filtrarLinhas(linhas(), { ...vazio, local: 'LOC-B' }, indices).map((l) => l.tecnico))
      .toEqual(['ana']);
  });

  it('busca e local se somam em vez de se substituírem', () => {
    expect(filtrarLinhas(linhas(), { ...vazio, busca: 'alinhar', local: 'LOC-B' }, indices)).toEqual([]);
  });
});

describe('decidirSolta', () => {
  const ordem = alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '12:00'));

  it('soltar na própria célula não é movimento', () => {
    expect(decidirSolta(ordem, 'ana', 'ana', SEG)).toBe('nada');
  });

  it('outra pessoa no mesmo dia é troca de executante', () => {
    expect(decidirSolta(ordem, 'ana', 'bruno', SEG)).toBe('troca');
  });

  it('outro dia é remanejo, mesmo mantendo a pessoa', () => {
    expect(decidirSolta(ordem, 'ana', 'ana', TER)).toBe('remanejo');
  });

  it('outro dia com outra pessoa é um remanejo só, não remanejo mais troca', () => {
    expect(decidirSolta(ordem, 'ana', 'bruno', TER)).toBe('remanejo');
  });

  it('o dia de origem sai da janela da ordem, não de quem arrastou', () => {
    const naTerca = alocacao('op-2', ['ana'], t(TER, '08:00'), t(TER, '09:00'));
    expect(decidirSolta(naTerca, 'ana', 'bruno', TER)).toBe('troca');
    expect(decidirSolta(naTerca, 'ana', 'bruno', SEG)).toBe('remanejo');
  });
});

describe('destinoDaCelula', () => {
  const linhas = () => linhasDaSemana(
    [alocacao('op-1', ['ana'], t(SEG, '08:00'), t(SEG, '12:00'))],
    [capacidade('ana', [oitoHoras(SEG)]), capacidade('bruno', [oitoHoras(SEG)])],
    DIAS,
  );

  it('dá a carga e a escala que a célula já tem', () => {
    expect(destinoDaCelula(linhas(), 'ana', SEG)).toEqual({ worker_id: 'ana', carga: 240, escala: 480 });
  });

  it('quem não tem escala no dia vem com escala zero, não some', () => {
    expect(destinoDaCelula(linhas(), 'bruno', TER)).toEqual({ worker_id: 'bruno', carga: 0, escala: 0 });
  });

  it('quem não está na matriz não tem destino', () => {
    expect(destinoDaCelula(linhas(), 'carla', SEG)).toBeNull();
  });
});
