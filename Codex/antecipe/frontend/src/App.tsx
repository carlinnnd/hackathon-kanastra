import React, { useEffect, useState } from 'react';
import { ShieldAlert, AlertTriangle, RefreshCw } from 'lucide-react';
import { FileUpload } from './components/FileUpload';
import { SummaryCards } from './components/SummaryCards';
import { ReceivablesTable } from './components/ReceivablesTable';
import { api } from './services/api';
import { SimulationEnvelope, HealthResponse, PortfolioSummary } from './types';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [simulation, setSimulation] = useState<SimulationEnvelope | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filtros
  const [currentStatus, setCurrentStatus] = useState<string>('todos');
  const [currentReason, setCurrentReason] = useState<string>('todos');

  // Carrega health e resumo do portfólio na montagem
  const checkBackendState = async () => {
    try {
      const [hRes, pRes] = await Promise.allSettled([
        api.getHealth(),
        api.getPortfolioSummary(),
      ]);

      if (hRes.status === 'fulfilled') {
        setHealth(hRes.value);
      } else {
        setHealth(null);
      }

      if (pRes.status === 'fulfilled') {
        setPortfolio(pRes.value);
      } else {
        setPortfolio(null);
      }
    } catch {
      setHealth(null);
      setPortfolio(null);
    }
  };

  useEffect(() => {
    checkBackendState();
  }, []);

  const handleFileSelected = async (file: File) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await api.uploadSimulation(file);
      setSimulation(res);
      setCurrentStatus('todos');
      setCurrentReason('todos');
    } catch (err: unknown) {
      // Limpa resultado anterior em caso de erro para não exibir dados obsoletos como novos
      setSimulation(null);
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Erro inesperado ao processar arquivo.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handlePageChange = async (newPage: number) => {
    if (!simulation) return;
    setIsLoading(true);
    try {
      const res = await api.getSimulation(
        simulation.simulation_id,
        newPage,
        50,
        currentStatus,
        currentReason
      );
      setSimulation(res);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleFilterChange = async (status: string, reason: string) => {
    if (!simulation) return;
    setIsLoading(true);
    setCurrentStatus(status);
    setCurrentReason(reason);
    try {
      const res = await api.getSimulation(
        simulation.simulation_id,
        1,
        50,
        status,
        reason
      );
      setSimulation(res);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const backendOnline = health !== null && health.status === 'ok';
  const estoqueDisponivel = backendOnline && health.estoque_carregado;
  const uploadHabilitado = backendOnline && estoqueDisponivel;

  // Metadata real do backend ou indicação de offline
  const fonteCadastralReal =
    simulation?.auditoria.cadastro_fonte ||
    health?.cadastro_fonte ||
    (backendOnline ? 'CONSULTANDO' : 'OFFLINE');

  const versaoRegraReal =
    simulation?.rule_version !== undefined
      ? `V${simulation.rule_version}`
      : health?.rule_version !== undefined
      ? `V${health.rule_version}`
      : (backendOnline ? '—' : 'OFFLINE');

  const estoqueStatusReal =
    portfolio?.total_recebiveis !== undefined
      ? `${portfolio.total_recebiveis.toLocaleString('pt-BR')} títulos`
      : health?.total_registros_estoque !== undefined && health.estoque_carregado
      ? `${health.total_registros_estoque.toLocaleString('pt-BR')} títulos`
      : backendOnline
      ? 'NÃO CARREGADO'
      : 'OFFLINE';

  return (
    <div className="app-container">
      {/* Cabeçalho Institucional */}
      <header className="header" role="banner">
        <div className="header-title-group">
          <h1>
            <span>Antecipe</span>
            <span className="header-badge">Motor de Simulação FIDC</span>
          </h1>
          <p className="header-subtitle">
            Plataforma de esteira de simulação de elegibilidade, análise de risco e antecipação de recebíveis.
          </p>
        </div>

        <div className="header-meta">
          <div
            className="status-pill"
            aria-live="polite"
            aria-label={`Status do backend: ${backendOnline ? 'Operacional' : 'Indisponível'}`}
          >
            <span
              className={`status-indicator ${backendOnline ? 'online' : 'offline'}`}
              aria-hidden="true"
            />
            <span>
              {backendOnline
                ? `Motor Conectado (${health?.fundo || 'FIDC'})`
                : 'Motor Offline / Conectando'}
            </span>
          </div>

          <button
            type="button"
            className="btn-secondary"
            onClick={checkBackendState}
            aria-label="Atualizar status do motor e carteira"
            style={{ padding: '6px 12px', fontSize: '0.8125rem' }}
          >
            <RefreshCw size={14} aria-hidden="true" />
            <span>Verificar</span>
          </button>
        </div>
      </header>

      {/* Faixa de Contexto de Risco e Simulação Cadastral */}
      <section className="alert-banner" aria-labelledby="banner-context-title">
        <div className="alert-banner-text">
          <strong id="banner-context-title">
            Ambiente de Simulação de Risco & Análise de Elegibilidade
          </strong>
          <p>
            Operação de simulação (sem desembolso financeiro ou cessão definitiva). Fonte
            cadastral: <strong>{fonteCadastralReal}</strong>. Concentração por raiz do CNPJ do sacado e
            duplicidade auditadas pelo motor.
          </p>
        </div>

        <div className="alert-banner-badges">
          <span className="badge-tag">DATA-BASE: 2026-10-22</span>
          <span className="badge-tag">REGRA ATIVA: {versaoRegraReal}</span>
          <span className="badge-tag">ESTOQUE: {estoqueStatusReal}</span>
        </div>
      </section>

      {/* Avisos do Portfólio / Governança */}
      {portfolio?.avisos && portfolio.avisos.length > 0 && (
        <div
          className="alert-banner"
          style={{ borderLeftColor: 'var(--status-warning-border)', marginBottom: '24px' }}
          role="region"
          aria-label="Avisos da carteira do fundo"
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <AlertTriangle size={20} color="var(--status-warning-text)" aria-hidden="true" />
            <div>
              <strong style={{ color: 'var(--status-warning-text)', fontSize: '0.875rem' }}>
                Avisos de Carteira e Governança:
              </strong>
              <ul style={{ marginTop: 4, paddingLeft: 18, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                {portfolio.avisos.map((aviso, i) => (
                  <li key={i}>{aviso}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Avisos da Simulação Atual */}
      {simulation?.avisos && simulation.avisos.length > 0 && (
        <div
          className="alert-banner"
          style={{ borderLeftColor: 'var(--status-warning-border)', marginBottom: '24px' }}
          role="region"
          aria-label="Avisos da simulação"
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <AlertTriangle size={20} color="var(--status-warning-text)" aria-hidden="true" />
            <div>
              <strong style={{ color: 'var(--status-warning-text)', fontSize: '0.875rem' }}>
                Avisos da Simulação:
              </strong>
              <ul style={{ marginTop: 4, paddingLeft: 18, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                {simulation.avisos.map((aviso, i) => (
                  <li key={i}>{aviso}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Alerta de Indisponibilidade do Backend ou Estoque Ausente */}
      {!uploadHabilitado && (
        <div
          className="error-toast"
          role="alert"
          aria-live="polite"
          style={{ backgroundColor: 'var(--status-warning-bg)', borderColor: 'var(--status-warning-border)', color: 'var(--status-warning-text)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <AlertTriangle size={20} aria-hidden="true" />
            <span>
              {!backendOnline
                ? 'Motor backend indisponível ou desconectado. Inicie o servidor FastAPI em http://localhost:8000 e clique em "Verificar".'
                : 'Estoque do FIDC não carregado no motor. O envio de arquivos está temporariamente suspenso.'}
            </span>
          </div>
        </div>
      )}

      {/* Alerta de Erro de Conexão ou Validação */}
      {errorMessage && (
        <div className="error-toast" role="alert" aria-live="assertive">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <ShieldAlert size={20} aria-hidden="true" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setErrorMessage(null)}
            style={{ padding: '4px 10px', fontSize: '0.75rem' }}
            aria-label="Fechar mensagem de erro"
          >
            Fechar
          </button>
        </div>
      )}

      {/* Seção Principal de Upload */}
      <main>
        <FileUpload
          onFileSelected={handleFileSelected}
          isLoading={isLoading}
          disabled={!uploadHabilitado}
        />

        {/* Indicador Honesto de Processamento Indeterminado */}
        {isLoading && (
          <div
            className="loading-box"
            role="status"
            aria-live="polite"
            aria-label="Processando arquivo CSV com o motor de regras"
          >
            <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
              Processando lote e avaliando elegibilidade...
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: 4 }}>
              O motor está validando regras de prazo, valores, duplicidade e limites de
              concentração com o estoque FIDC.
            </p>
            <div className="progress-bar-container">
              <div className="progress-bar-indeterminate" />
            </div>
          </div>
        )}

        {/* Resumo e Detalhamento da Simulação */}
        {simulation && (
          <>
            <SummaryCards simulation={simulation} />

            <ReceivablesTable
              simulation={simulation}
              onPageChange={handlePageChange}
              onFilterChange={handleFilterChange}
              currentStatus={currentStatus}
              currentReason={currentReason}
            />

            {/* Metadados de Auditoria e Rastreabilidade */}
            <section className="audit-card" aria-label="Metadados de auditoria da simulação">
              <div className="audit-meta-item">
                Identificador da Simulação:{' '}
                <strong>{simulation.simulation_id}</strong>
              </div>
              <div className="audit-meta-item">
                Fonte Cadastral: <strong>{simulation.auditoria.cadastro_fonte}</strong>
              </div>
              <div className="audit-meta-item">
                Carteira de Referência:{' '}
                <strong>{simulation.auditoria.carteira_referencia}</strong>
              </div>
              <div className="audit-meta-item">
                Hash de Configuração:{' '}
                <span style={{ fontFamily: 'var(--font-mono)' }}>
                  {simulation.auditoria.configuration_hash.substring(0, 12)}...
                </span>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
};
