import React from 'react';
import { CheckCircle2, XCircle, DollarSign, Layers } from 'lucide-react';
import { SimulationEnvelope } from '../types';
import { formatarMoedaBRL } from '../services/currency';

interface SummaryCardsProps {
  simulation: SimulationEnvelope;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({ simulation }) => {
  const percentualAprovacao =
    simulation.total_itens > 0
      ? ((simulation.aprovados / simulation.total_itens) * 100).toFixed(1)
      : '0.0';

  return (
    <section aria-labelledby="summary-cards-title">
      <h2 id="summary-cards-title" className="sr-only">
        Resumo da Análise de Elegibilidade
      </h2>

      <div className="summary-grid">
        <div className="metric-card">
          <div className="metric-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Layers size={14} aria-hidden="true" />
            <span>Total de Títulos Analisados</span>
          </div>
          <div className="metric-value">{simulation.total_itens.toLocaleString('pt-BR')}</div>
          <div className="metric-sub">Lote submetido para simulação</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <CheckCircle2 size={14} color="#10b981" aria-hidden="true" />
            <span style={{ color: '#6ee7b7' }}>Títulos Aprovados</span>
          </div>
          <div className="metric-value" style={{ color: '#10b981' }}>
            {simulation.aprovados.toLocaleString('pt-BR')}
          </div>
          <div className="metric-sub">{percentualAprovacao}% aprovados pela política do fundo</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <XCircle size={14} color="#ef4444" aria-hidden="true" />
            <span style={{ color: '#fca5a5' }}>Títulos Recusados</span>
          </div>
          <div className="metric-value" style={{ color: '#ef4444' }}>
            {simulation.recusados.toLocaleString('pt-BR')}
          </div>
          <div className="metric-sub">Não atendem aos critérios do fundo</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <DollarSign size={14} color="#3b82f6" aria-hidden="true" />
            <span>Volume Líquido Projetado</span>
          </div>
          <div className="metric-value" style={{ color: '#60a5fa' }}>
            {formatarMoedaBRL(simulation.total_liquido)}
          </div>
          <div className="metric-sub">
            Nominal: {formatarMoedaBRL(simulation.total_nominal)}
          </div>
        </div>
      </div>
    </section>
  );
};
