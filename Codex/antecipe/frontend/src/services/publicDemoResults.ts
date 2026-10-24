/**
 * Gerenciador puro de visualização de simulação em memória para modo público efêmero.
 * Quando o backend opera sem persistência compartilhada (ex: serverless Vercel /tmp),
 * consultas subsequentes GET /api/simulations/{id} em instâncias distintas retornam 404.
 *
 * Se o snapshot inicial retornado no POST contiver TODOS os itens (resultados.length === total_itens),
 * as operações de filtro e paginação são aplicadas como view pura sobre esse snapshot original,
 * PRESERVANDO intactos os totais globais (total_itens, aprovados, recusados, nominal, líquido).
 *
 * Se o lote exceder o tamanho da página (> 50) e for parcial, sinaliza a necessidade
 * de instância persistente e desabilita filtros locais para não induzir a conclusões incompletas.
 */

import { SimulationEnvelope, ResultadoItem } from '../types';

export function aplicarFiltroPaginacaoLocal(
  snapshotOriginal: SimulationEnvelope,
  statusFiltro: string,
  motivoFiltro: string,
  page: number = 1,
  pageSize: number = 50
): SimulationEnvelope {
  // Filtra itens preservando a lista original
  let itensFiltrados = snapshotOriginal.resultados;

  if (statusFiltro === 'aprovado') {
    itensFiltrados = itensFiltrados.filter((item: ResultadoItem) => item.aprovado);
  } else if (statusFiltro === 'recusado') {
    itensFiltrados = itensFiltrados.filter((item: ResultadoItem) => !item.aprovado);
  }

  if (motivoFiltro && motivoFiltro !== 'todos') {
    itensFiltrados = itensFiltrados.filter((item: ResultadoItem) =>
      item.motivos && item.motivos.some((m) => m.codigo === motivoFiltro)
    );
  }

  const totalFiltrados = itensFiltrados.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltrados / pageSize));
  const validPage = Math.min(Math.max(1, page), totalPages);

  const startIdx = (validPage - 1) * pageSize;
  const itensPaginados = itensFiltrados.slice(startIdx, startIdx + pageSize);

  // Retorna envelope com totais globais e contagens originais INALTERADOS,
  // adaptando apenas a paginação e a lista visível de resultados.
  return {
    ...snapshotOriginal,
    resultados: itensPaginados,
    pagination: {
      page: validPage,
      page_size: pageSize,
      total: totalFiltrados,
      total_pages: totalPages,
    },
  };
}

export function verificarSnapshotCompleto(simulation: SimulationEnvelope): boolean {
  return simulation.resultados.length === simulation.total_itens;
}
