import React, { useState } from 'react';
import { ChevronDown, ChevronRight, AlertTriangle, Filter } from 'lucide-react';
import { SimulationEnvelope, ResultadoItem } from '../types';
import { obterExplicacaoRecusa } from '../services/rejections';
import { formatarMoedaBRL } from '../services/currency';
import { EconomicGroupCard } from './EconomicGroupCard';

interface ReceivablesTableProps {
  simulation: SimulationEnvelope;
  onPageChange: (newPage: number) => void;
  onFilterChange: (status: string, reason: string) => void;
  currentStatus: string;
  currentReason: string;
  filtrosDesabilitados?: boolean;
}

export const ReceivablesTable: React.FC<ReceivablesTableProps> = ({
  simulation,
  onPageChange,
  onFilterChange,
  currentStatus,
  currentReason,
  filtrosDesabilitados = false,
}) => {
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});

  const toggleRow = (linha: number) => {
    setExpandedRows((prev) => ({
      ...prev,
      [linha]: !prev[linha],
    }));
  };

  const handleStatusSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onFilterChange(e.target.value, currentReason);
  };

  const handleReasonSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onFilterChange(currentStatus, e.target.value);
  };

  const { page, page_size, total, total_pages } = simulation.pagination;
  const startItem = total > 0 ? (page - 1) * page_size + 1 : 0;
  const endItem = Math.min(page * page_size, total);

  return (
    <section className="table-section" aria-labelledby="receivables-table-title">
      <div className="table-header-controls">
        <div className="table-title-group">
          <h2 id="receivables-table-title">Detalhamento dos Recebíveis</h2>
          <p>
            Resultados auditados da simulação (itens {startItem} a{' '}
            {endItem} de {total.toLocaleString('pt-BR')})
          </p>
        </div>

        <div className="filters-group" role="search" aria-label="Filtros de títulos">
          <Filter size={16} color="var(--text-secondary)" aria-hidden="true" />
          <label htmlFor="filter-status" className="sr-only">
            Filtrar por status de aprovação
          </label>
          <select
            id="filter-status"
            className="select-control"
            value={currentStatus}
            onChange={handleStatusSelect}
            disabled={filtrosDesabilitados}
            aria-label="Filtrar por status de aprovação"
          >
            <option value="todos">Todos os status</option>
            <option value="APROVADA">Aprovadas</option>
            <option value="RECUSADA">Recusadas</option>
            {simulation.tipo_analise === 'carteira' && <option value="CARTEIRA_HISTORICA">Carteira histórica</option>}
          </select>

          <label htmlFor="filter-reason" className="sr-only">
            Filtrar por motivo de recusa
          </label>
          <select
            id="filter-reason"
            className="select-control"
            value={currentReason}
            onChange={handleReasonSelect}
            disabled={filtrosDesabilitados}
            aria-label="Filtrar por motivo de recusa"
          >
            <option value="todos">Todos os motivos</option>
            {/* Códigos reais do motor / validadores_antecipe.json */}
            <option value="VALOR_MINIMO">Valor Nominal Inferior ao Mínimo [VALOR_MINIMO]</option>
            <option value="PRAZO_MAXIMO">Prazo Acima do Limite [PRAZO_MAXIMO]</option>
            <option value="NAO_VENCIDA">Título Já Vencido [NAO_VENCIDA]</option>
            <option value="SITUACAO_CADASTRAL_SACADO">Situação Cadastral Incompatível [SITUACAO_CADASTRAL_SACADO]</option>
            <option value="TIPO_RECEBIVEL">Tipo Não Aceito [TIPO_RECEBIVEL]</option>
            <option value="CNPJ_SACADO_VALIDO">CNPJ do Sacado Inválido [CNPJ_SACADO_VALIDO]</option>
            <option value="CONCENTRACAO_MAXIMA_SACADO">Concentração Raiz Excedida [CONCENTRACAO_MAXIMA_SACADO]</option>
            <option value="DUPLICIDADE_HISTORICA">Duplicidade no Estoque [DUPLICIDADE_HISTORICA]</option>
            <option value="DUPLICIDADE_LOTE">Duplicidade no Lote [DUPLICIDADE_LOTE]</option>
            <option value="PRAZO_MINIMO">Prazo Abaixo do Mínimo [PRAZO_MINIMO]</option>
            <option value="CONCENTRACAO_MAXIMA_CEDENTE">Concentração Cedente Excedida [CONCENTRACAO_MAXIMA_CEDENTE]</option>
            <option value="VALOR_EXCEDE_CAPACIDADE">Valor Excede Capacidade Técnica [VALOR_EXCEDE_CAPACIDADE]</option>
          </select>
        </div>
      </div>

      <div className="table-responsive">
        <table aria-label="Tabela de análise de elegibilidade de recebíveis">
          <thead>
            <tr>
              <th scope="col" style={{ width: '48px' }}>
                <span className="sr-only">Expandir detalhes</span>
              </th>
              <th scope="col">Linha</th>
              <th scope="col">Documento</th>
              <th scope="col">Sacado</th>
              <th scope="col">Status</th>
              <th scope="col" style={{ textAlign: 'right' }}>
                Valor Nominal
              </th>
              <th scope="col" style={{ textAlign: 'right' }}>
                Valor Líquido
              </th>
              <th scope="col">Motivo / Enquadramento</th>
            </tr>
          </thead>
          <tbody>
            {simulation.resultados.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '32px' }}>
                  Nenhum recebível encontrado com os critérios de filtro selecionados.
                </td>
              </tr>
            ) : (
              simulation.resultados.map((item: ResultadoItem) => {
                const isExpanded = !!expandedRows[item.linha];
                const temMotivos = item.motivos && item.motivos.length > 0;
                const primeiroMotivo = temMotivos ? item.motivos[0] : null;
                const explicacaoPrimeiro = primeiroMotivo
                  ? obterExplicacaoRecusa(primeiroMotivo.codigo, primeiroMotivo.mensagem)
                  : null;

                return (
                  <React.Fragment key={item.linha}>
                    <tr>
                      <td>
                        {temMotivos ? (
                          <button
                            type="button"
                            onClick={() => toggleRow(item.linha)}
                            className="btn-page"
                            style={{ padding: '4px', border: 'none', background: 'transparent' }}
                            aria-expanded={isExpanded}
                            aria-label={`Ver justificativa da política do fundo para o título da linha ${item.linha}`}
                          >
                            {isExpanded ? (
                              <ChevronDown size={18} color="var(--text-secondary)" />
                            ) : (
                              <ChevronRight size={18} color="var(--text-secondary)" />
                            )}
                          </button>
                        ) : null}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>#{item.linha}</td>
                      <td style={{ fontWeight: 600 }}>{item.documento}</td>
                      <td>{item.sacado}</td>
                      <td>
                        {item.aprovado ? (
                          <span className="badge approved">APROVADO</span>
                        ) : (
                          <span className={`badge ${item.status === 'CARTEIRA_HISTORICA' ? 'historic' : 'rejected'}`}>
                            {item.status === 'CARTEIRA_HISTORICA' ? 'HISTÓRICO' : 'RECUSADA'}
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                        {formatarMoedaBRL(item.valor_nominal)}
                      </td>
                      <td
                        style={{
                          textAlign: 'right',
                          fontFamily: 'var(--font-mono)',
                          color: item.aprovado ? 'var(--status-success-text)' : 'inherit',
                        }}
                      >
                        {item.aprovado ? formatarMoedaBRL(item.valor_liquido) : '—'}
                      </td>
                      <td>
                        {item.aprovado ? (
                          <span style={{ color: 'var(--status-success-text)', fontSize: '0.8125rem' }}>
                            Conforme política do fundo
                          </span>
                        ) : item.status === 'CARTEIRA_HISTORICA' ? (
                          <span style={{color: 'var(--text-secondary)', fontSize: '0.8125rem'}}>Estoque histórico; sem decisão de antecipação</span>
                        ) : explicacaoPrimeiro && primeiroMotivo ? (
                          <span
                            style={{
                              color: 'var(--status-danger-text)',
                              fontSize: '0.8125rem',
                              fontWeight: 500,
                            }}
                          >
                            {explicacaoPrimeiro.titulo}{' '}
                            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                              [{primeiroMotivo.codigo}]
                            </span>
                            {item.motivos.length > 1 ? (
                              <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginLeft: 4 }}>
                                (+{item.motivos.length - 1})
                              </span>
                            ) : null}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                            Não elegível
                          </span>
                        )}
                      </td>
                    </tr>

                    {isExpanded && temMotivos && (
                      <tr>
                        <td colSpan={8} style={{ padding: '0 16px 16px 48px' }}>
                          <div className="rejection-details" role="region" aria-label="Detalhes da recusa">
                            {item.motivos.map((m, idx) => {
                              const explicacao = obterExplicacaoRecusa(m.codigo, m.mensagem);
                              return (
                                <div
                                  key={idx}
                                  style={{
                                    borderBottom:
                                      idx < item.motivos.length - 1
                                        ? '1px solid rgba(255,255,255,0.08)'
                                        : 'none',
                                    paddingBottom: idx < item.motivos.length - 1 ? 8 : 0,
                                    marginBottom: idx < item.motivos.length - 1 ? 8 : 0,
                                  }}
                                >
                                  <div className="rejection-details-title">
                                    <AlertTriangle size={14} aria-hidden="true" />
                                    <span>
                                      {explicacao.titulo} [{m.codigo}]
                                    </span>
                                  </div>
                                  <div className="rejection-details-desc">
                                    {explicacao.descricao}
                                  </div>
                                  <div className="rejection-details-action">
                                    Ação recomendada: {explicacao.acaoRecomendada}
                                  </div>
                                  {m.codigo === 'CONCENTRACAO_MAXIMA_SACADO' && (
                                    <EconomicGroupCard
                                      raizCnpj={String(m.dados?.raiz_cnpj || '58206002')}
                                      dadosMotivo={m.dados}
                                    />
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="pagination-bar">
        <div className="pagination-info">
          Página <strong>{page}</strong> de <strong>{total_pages || 1}</strong> — Exibindo{' '}
          {simulation.resultados.length} de {total} itens
        </div>

        <div className="pagination-controls" aria-label="Navegação da paginação">
          <button
            type="button"
            className="btn-page"
            disabled={filtrosDesabilitados || page <= 1}
            onClick={() => onPageChange(page - 1)}
            aria-label="Ir para a página anterior"
          >
            Anterior
          </button>
          <button
            type="button"
            className="btn-page"
            disabled={filtrosDesabilitados || page >= total_pages}
            onClick={() => onPageChange(page + 1)}
            aria-label="Ir para a próxima página"
          >
            Próxima
          </button>
        </div>
      </div>
    </section>
  );
};
