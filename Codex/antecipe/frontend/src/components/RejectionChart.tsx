import React from 'react';
import { BarChart3, Filter, TrendingDown, CheckCircle2, XCircle } from 'lucide-react';
import { SimulationEnvelope } from '../types';
import { obterExplicacaoRecusa } from '../services/rejections';
import { formatarMoedaBRL } from '../services/currency';

interface RejectionChartProps {
  simulation: SimulationEnvelope;
  currentReason: string;
  onSelectReason: (reason: string) => void;
}

export const RejectionChart: React.FC<RejectionChartProps> = ({
  simulation,
  currentReason,
  onSelectReason,
}) => {
  // Consolida motivos a partir do resumo global do lote (backend) ou fallback nos itens carregados
  const mapaMotivos: Record<string, number> = React.useMemo(() => {
    if (simulation.resumo_motivos && Object.keys(simulation.resumo_motivos).length > 0) {
      return simulation.resumo_motivos;
    }
    if (simulation.analytics?.motivos && simulation.analytics.motivos.length > 0) {
      const fromAnalytics: Record<string, number> = {};
      for (const m of simulation.analytics.motivos) {
        fromAnalytics[m.codigo] = m.quantidade;
      }
      return fromAnalytics;
    }
    const acc: Record<string, number> = {};
    for (const item of simulation.resultados) {
      if (!item.aprovado && item.motivos) {
        for (const m of item.motivos) {
          acc[m.codigo] = (acc[m.codigo] || 0) + 1;
        }
      }
    }
    return acc;
  }, [simulation]);

  const entradasOrdenadas = React.useMemo(() => {
    return Object.entries(mapaMotivos).sort((a, b) => b[1] - a[1]);
  }, [mapaMotivos]);

  const maiorContagem = entradasOrdenadas.length > 0 ? entradasOrdenadas[0][1] : 1;

  // Cálculo seguro em centavos (BigInt) do deságio/retorno retido nos aprovados visíveis ou estimados
  const metricasFinanceiras = React.useMemo(() => {
    let nominalAprovadosCentavos = 0n;
    let liquidoAprovadosCentavos = 0n;
    for (const r of simulation.resultados) {
      if (r.aprovado && r.valor_nominal && r.valor_liquido) {
        const nom = BigInt(r.valor_nominal.replace(/\D/g, '') || '0');
        const liq = BigInt(r.valor_liquido.replace(/\D/g, '') || '0');
        nominalAprovadosCentavos += nom;
        liquidoAprovadosCentavos += liq;
      }
    }
    const desagioAmostraCentavos =
      nominalAprovadosCentavos > liquidoAprovadosCentavos
        ? nominalAprovadosCentavos - liquidoAprovadosCentavos
        : 0n;
    const desagioStr = (Number(desagioAmostraCentavos) / 100).toFixed(2);
    return {
      desagioAmostraStr: desagioStr,
    };
  }, [simulation.resultados]);

  if (entradasOrdenadas.length === 0 && simulation.recusados === 0) {
    return null;
  }

  return (
    <section
      className="table-section"
      style={{ padding: '20px', marginBottom: '24px' }}
      aria-labelledby="rejection-chart-title"
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '16px',
          marginBottom: '18px',
        }}
      >
        <div>
          <h2
            id="rejection-chart-title"
            style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}
          >
            <BarChart3 size={17} color="#34d399" aria-hidden="true" />
            <span>Distribuição de Motivos de Recusa</span>
          </h2>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: 2 }}>
            Selecione um motivo abaixo para filtrar os registros na tabela.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div
            style={{
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 12px',
              fontSize: '0.75rem',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <TrendingDown size={14} color="#34d399" aria-hidden="true" />
            <span style={{ color: 'var(--text-secondary)' }}>Critério de Precificação:</span>
            <strong style={{ color: 'var(--text-primary)' }}>
              Desconto Comercial Simples
            </strong>
          </div>

          {Number(metricasFinanceiras.desagioAmostraStr) > 0 && (
            <div
              style={{
                backgroundColor: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: '6px 12px',
                fontSize: '0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span style={{ color: 'var(--text-secondary)' }}>Deságio Comercial (página):</span>
              <strong style={{ color: '#6ee7b7', fontFamily: 'var(--font-mono)' }}>
                {formatarMoedaBRL(metricasFinanceiras.desagioAmostraStr)}
              </strong>
            </div>
          )}

          {currentReason !== 'todos' && (
            <button
              type="button"
              className="btn-secondary"
              style={{ padding: '5px 10px', fontSize: '0.75rem' }}
              onClick={() => onSelectReason('todos')}
            >
              <Filter size={12} aria-hidden="true" />
              <span>Limpar filtro ({currentReason})</span>
            </button>
          )}
        </div>
      </div>

      {/* Barra Proporcional Aprovados vs Recusados */}
      <div style={{ marginBottom: '20px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.75rem',
            marginBottom: '6px',
          }}
        >
          <span style={{ color: '#6ee7b7', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600 }}>
            <CheckCircle2 size={13} aria-hidden="true" />
            Elegíveis Aprovados: {simulation.aprovados.toLocaleString('pt-BR')} (
            {simulation.total_itens > 0
              ? ((simulation.aprovados / simulation.total_itens) * 100).toFixed(1)
              : '0.0'}
            %)
          </span>
          <span style={{ color: '#fca5a5', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600 }}>
            <XCircle size={13} aria-hidden="true" />
            Barrados pelas Regras: {simulation.recusados.toLocaleString('pt-BR')} (
            {simulation.total_itens > 0
              ? ((simulation.recusados / simulation.total_itens) * 100).toFixed(1)
              : '0.0'}
            %)
          </span>
        </div>
        <div
          style={{
            height: '10px',
            width: '100%',
            backgroundColor: 'var(--status-danger-bg)',
            borderRadius: '9999px',
            overflow: 'hidden',
            display: 'flex',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div
            style={{
              width: `${
                simulation.total_itens > 0
                  ? Math.min(100, (simulation.aprovados / simulation.total_itens) * 100)
                  : 0
              }%`,
              backgroundColor: '#10b981',
              transition: 'width 0.3s ease',
            }}
          />
        </div>
      </div>

      {/* Barras Horizontais por Código de Recusa */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
        {entradasOrdenadas.map(([codigo, count]) => {
          const info = obterExplicacaoRecusa(codigo);
          const pctLote =
            simulation.total_itens > 0 ? ((count / simulation.total_itens) * 100).toFixed(1) : '0.0';
          const barWidth = Math.max(6, Math.round((count / maiorContagem) * 100));
          const isSelected = currentReason === codigo;

          return (
            <button
              key={codigo}
              type="button"
              onClick={() => onSelectReason(isSelected ? 'todos' : codigo)}
              style={{
                textAlign: 'left',
                backgroundColor: isSelected ? 'rgba(37, 99, 235, 0.14)' : 'var(--bg-surface-elevated)',
                border: isSelected ? '1px solid var(--border-focus)' : '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '10px 12px',
                cursor: 'pointer',
                color: 'var(--text-primary)',
                transition: 'all 0.15s ease',
              }}
              aria-pressed={isSelected}
              aria-label={`Filtrar por ${info.titulo} (${count} ocorrências)`}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 4,
                }}
              >
                <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#fca5a5' }}>
                  {info.titulo}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                  }}
                >
                  {count.toLocaleString('pt-BR')} ({pctLote}%)
                </span>
              </div>

              <div
                style={{
                  fontSize: '0.7rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  marginBottom: 6,
                }}
              >
                [{codigo}]
              </div>

              <div
                style={{
                  width: '100%',
                  height: '6px',
                  backgroundColor: 'rgba(255,255,255,0.06)',
                  borderRadius: '9999px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${barWidth}%`,
                    height: '100%',
                    backgroundColor: codigo === 'CONCENTRACAO_MAXIMA_SACADO' ? '#f59e0b' : '#ef4444',
                    borderRadius: '9999px',
                  }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
};

