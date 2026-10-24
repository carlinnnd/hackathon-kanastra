import React from 'react';
import { SimulationEnvelope } from '../types';
import { formatarMoedaBRL } from '../services/currency';

export const ResultAnalytics: React.FC<{
  simulation: SimulationEnvelope;
  onExport: (format: 'csv' | 'pdf' | 'violacoes') => void;
  exportDisabled: boolean;
  exporting: boolean;
}> = ({simulation, onExport, exportDisabled, exporting}) => {
  const a = simulation.analytics;
  if (!a) return null;
  const historical = simulation.tipo_analise === 'carteira';
  const bars = (values: [string, number][]) => {
    const max = Math.max(1, ...values.map(([, n]) => n));
    return <ul className="analysis-bars">{values.map(([label, n]) => <li key={label}>
      <div><span>{label.replaceAll('_', ' ')}</span><strong>{n.toLocaleString('pt-BR')}</strong></div>
      <div className="analysis-track" aria-hidden="true"><span style={{width: `${n / max * 100}%`}} /></div>
    </li>)}</ul>;
  };
  return <section className="result-analysis" aria-labelledby="analysis-title">
    <div className="analysis-heading"><div><h2 id="analysis-title">{historical ? 'Leitura da carteira' : 'Resultado financeiro e elegibilidade'}</h2>
      <p>{a.metodologia}</p></div>
      <div className="export-actions" aria-label="Exportar resultados">
        <button className="btn-secondary" onClick={() => onExport('csv')} disabled={exportDisabled}>CSV completo</button>
        <button className="btn-secondary" onClick={() => onExport('pdf')} disabled={exportDisabled}>PDF executivo</button>
        <button className="btn-secondary" onClick={() => onExport('violacoes')} disabled={exportDisabled}>CSV de violações</button>
      </div>
    </div>
    <p className="analysis-caption" role="status">{exporting ? 'Gerando exportação completa. Aguarde o download…' : exportDisabled ? 'Sessão encerrada. Reenvie o arquivo para exportar o resultado completo.' : 'CSV: todas as linhas, incluindo campos originais. PDF: síntese financeira e auditoria. Cadastro simulado.'}</p>
    {!historical && <div className="finance-strip">
      <div><span>Nominal elegível</span><strong>{formatarMoedaBRL(a.valor_nominal_elegivel)}</strong></div>
      <div><span>Desconto total</span><strong>{formatarMoedaBRL(a.valor_desconto)}</strong></div>
      <div><span>Aprovação em valor</span><strong>{a.aprovacao_valor_pct.replace('.', ',')}%</strong></div>
      <div><span>Prazo médio ponderado</span><strong>{a.prazo_medio_ponderado?.replace('.', ',') || '—'} dias</strong></div>
    </div>}
    <div className="analysis-grid">
      <article><h3>{historical ? 'Registros históricos' : 'Decisões do lote'}</h3>{bars(Object.entries(a.status_counts))}</article>
      <article><h3>Faixas de vencimento</h3><p>Em dias, a partir da data-base.</p>{bars(Object.entries(a.faixas_vencimento))}</article>
      <article><h3>Principais motivos</h3>{a.motivos.length ? bars(a.motivos.slice(0, 8).map(m => [m.codigo, m.quantidade])) : <p>{historical ? 'Não se aplica decisão de aprovação ou recusa ao estoque histórico.' : 'Nenhuma violação identificada.'}</p>}
        <p>Motivos podem se sobrepor. O valor de uma nota com várias violações aparece em mais de um motivo.</p>
        <details><summary>Impacto nominal por motivo</summary><ul>{a.motivos.map(m => <li key={m.codigo}>{m.codigo}: {formatarMoedaBRL(m.valor_nominal)}</li>)}</ul></details>
      </article>
      <article><h3>Maiores exposições por raiz</h3><p>{historical ? 'Carteira enviada, calculada separadamente para cada fundo.' : 'Projeção da carteira após somente as aprovações do lote.'}</p>
        <div className="table-responsive"><table><thead><tr><th>Fundo / raiz</th><th>Nominal</th><th>Participação</th></tr></thead>
          <tbody>{a.exposicoes.slice(0, 8).map(v => <tr key={`${v.doc_fundo}-${v.raiz}`}><td>{v.doc_fundo ? `${v.doc_fundo} / ` : ''}{v.raiz}</td><td>{formatarMoedaBRL(v.valor_nominal)}</td><td>{v.percentual.replace('.', ',')}%</td></tr>)}</tbody></table></div>
        <p>Maiores 8 grupos exibidos. O CSV contém todos os títulos.</p>
      </article>
    </div>
  </section>;
};
