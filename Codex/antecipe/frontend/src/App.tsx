import React, { useEffect, useState, useRef } from 'react';
import { ShieldAlert, AlertTriangle, RefreshCw, Info, Wifi } from 'lucide-react';
import { FileUpload } from './components/FileUpload';
import { SummaryCards } from './components/SummaryCards';
import { ReceivablesTable } from './components/ReceivablesTable';
import { api } from './services/api';
import {
  SimulationEnvelope,
  HealthResponse,
  PortfolioSummary,
  StreamProgressInfo,
} from './types';
import {
  aplicarFiltroPaginacaoLocal,
  verificarSnapshotCompleto,
} from './services/publicDemoResults';
import { BulkUploadSession } from './services/bulkUpload';
import { ResultAnalytics } from './components/ResultAnalytics';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [simulation, setSimulation] = useState<SimulationEnvelope | null>(null);

  // Snapshot original completo em memória (usado para modo público efêmero em arquivos pequenos)
  const snapshotOriginalRef = useRef<SimulationEnvelope | null>(null);

  // Sessão ativa de WebSocket para streaming e paginação na mesma instância
  const bulkSessionRef = useRef<BulkUploadSession | null>(null);
  const [isWsSessionActive, setIsWsSessionActive] = useState(false);
  const [wsSessionExpiredNotice, setWsSessionExpiredNotice] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [streamProgress, setStreamProgress] = useState<StreamProgressInfo | null>(null);
  const [tipoAnalise, setTipoAnalise] = useState<'novas_operacoes' | 'carteira'>('novas_operacoes');
  const [isExporting, setIsExporting] = useState(false);

  // Filtros
  const [currentStatus, setCurrentStatus] = useState<string>('todos');
  const [currentReason, setCurrentReason] = useState<string>('todos');

  // Encerra sessão anterior ao desmontar
  useEffect(() => {
    return () => {
      if (bulkSessionRef.current) {
        bulkSessionRef.current.close();
        bulkSessionRef.current = null;
      }
    };
  }, []);

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
    const timer = window.setInterval(() => {
      api.getHealth().then(setHealth).catch(() => setHealth(null));
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const isModoPublico = Boolean(health?.aviso_demo_publica);

  // Capacidades de upload informadas pelo backend
  const uploadCaps = health?.upload_capabilities;
  const isWsDisponivel = uploadCaps?.bulk_transport === 'websocket';
  const httpMaxBytes = (uploadCaps?.http_max_bytes || 4000000) - 1024;

  const handleFileSelected = async (file: File) => {
    // Fecha sessão WebSocket anterior para liberar recursos
    if (bulkSessionRef.current) {
      bulkSessionRef.current.close();
      bulkSessionRef.current = null;
      setIsWsSessionActive(false);
    }

    setIsLoading(true);
    setErrorMessage(null);
    setWsSessionExpiredNotice(null);
    setStreamProgress(null);

    // Seleciona WebSocket SOMENTE se o backend anunciar explicitamente suporte e o arquivo exceder o limite seguro HTTP
    const deveUsarWebSocket = isWsDisponivel && (isModoPublico || file.size > httpMaxBytes);

    if (deveUsarWebSocket) {
      setStreamProgress({
        fase: 'uploading',
        bytesEnviados: 0,
        totalBytes: file.size,
      });

      const session = new BulkUploadSession(
        file,
        {
          onProgress: (info: StreamProgressInfo) => {
            setStreamProgress(info);
          },
          onError: (erro: { codigo: string; mensagem: string }) => {
            snapshotOriginalRef.current = null;
            setSimulation(null);
            setErrorMessage(`[${erro.codigo}] ${erro.mensagem}`);
            setIsLoading(false);
            setStreamProgress(null);
            setIsWsSessionActive(false);
          },
          onComplete: (simEnvelope: SimulationEnvelope) => {
            snapshotOriginalRef.current = simEnvelope;
            setSimulation(simEnvelope);
            setCurrentStatus('todos');
            setCurrentReason('todos');
            setIsLoading(false);
            setStreamProgress(null);
            setIsWsSessionActive(true);
          },
          onSessionClosed: (wasCompleted: boolean) => {
            setIsWsSessionActive(false);
            setIsLoading(false);
            setStreamProgress(null);

            if (wasCompleted) {
              // Concluiu com sucesso: preserva resumo e desabilita consultas na sessão fechada
              setWsSessionExpiredNotice(
                'A sessão interativa desta simulação foi encerrada pelo servidor. O resumo inicial foi preservado; para navegar por outras páginas ou filtros deste lote extenso, envie o arquivo novamente.'
              );
            } else {
              // Falhou antes da conclusão: limpa estado stale e emite erro claro para reenvio
              snapshotOriginalRef.current = null;
              setSimulation(null);
              setErrorMessage((prev) =>
                prev || 'A conexão foi encerrada antes da conclusão do processamento. Por favor, reenvie o arquivo.'
              );
            }
          },
        },
        uploadCaps?.bulk_path,
        tipoAnalise
      );

      bulkSessionRef.current = session;

      try {
        await session.start();
      } catch (err: unknown) {
        snapshotOriginalRef.current = null;
        setSimulation(null);
        setIsLoading(false);
        setStreamProgress(null);
        setIsWsSessionActive(false);
        if (err instanceof Error) {
          setErrorMessage(err.message);
        } else {
          setErrorMessage('Erro ao inicializar conexão de streaming WebSocket.');
        }
      }
      return;
    }

    // Se WS não estiver disponível ou arquivo for pequeno: preserva fluxo HTTP atual inalterado
    try {
      const res = await api.uploadSimulation(file, tipoAnalise);
      snapshotOriginalRef.current = res;
      setSimulation(res);
      setCurrentStatus('todos');
      setCurrentReason('todos');
    } catch (err: unknown) {
      snapshotOriginalRef.current = null;
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

    // 1. Se a sessão WebSocket estiver ativa, consulta na MESMA conexão
    if (bulkSessionRef.current && isWsSessionActive) {
      setIsLoading(true);
      try {
        const paginatedSim = await bulkSessionRef.current.query(
          newPage,
          50,
          currentStatus,
          currentReason
        );
        setSimulation(paginatedSim);
      } catch (err: unknown) {
        if (err instanceof Error) {
          setErrorMessage(err.message);
        }
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // 2. Se estiver em modo público efêmero e o snapshot for completo (lotes <= 50)
    if (
      isModoPublico &&
      snapshotOriginalRef.current &&
      verificarSnapshotCompleto(snapshotOriginalRef.current)
    ) {
      const visualizacao = aplicarFiltroPaginacaoLocal(
        snapshotOriginalRef.current,
        currentStatus,
        currentReason,
        newPage,
        50
      );
      setSimulation(visualizacao);
      return;
    }

    // 3. Modo local/persistente padrão: consulta GET via backend
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
    setCurrentStatus(status);
    setCurrentReason(reason);

    // 1. Se a sessão WebSocket estiver ativa, consulta na MESMA conexão
    if (bulkSessionRef.current && isWsSessionActive) {
      setIsLoading(true);
      try {
        const filteredSim = await bulkSessionRef.current.query(
          1,
          50,
          status,
          reason
        );
        setSimulation(filteredSim);
      } catch (err: unknown) {
        if (err instanceof Error) {
          setErrorMessage(err.message);
        }
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // 2. Se estiver em modo público efêmero e o snapshot for completo
    if (
      isModoPublico &&
      snapshotOriginalRef.current &&
      verificarSnapshotCompleto(snapshotOriginalRef.current)
    ) {
      const visualizacao = aplicarFiltroPaginacaoLocal(
        snapshotOriginalRef.current,
        status,
        reason,
        1,
        50
      );
      setSimulation(visualizacao);
      return;
    }

    // 3. Modo local/persistente padrão: consulta GET via backend
    setIsLoading(true);
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

  const handleExport = async (format: 'csv' | 'pdf' | 'violacoes') => {
    if (!simulation) return;
    setIsExporting(true);
    setErrorMessage(null);
    try {
      let blob: Blob;
      if (bulkSessionRef.current) {
        blob = await bulkSessionRef.current.exportResult(format);
      } else {
        const response = await fetch(`/api/simulations/${encodeURIComponent(simulation.simulation_id)}/export?format=${format}`);
        if (!response.ok) throw new Error('Não foi possível exportar. Reenvie o arquivo se a sessão expirou.');
        blob = await response.blob();
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `antecipe-${simulation.simulation_id}-${format}.${format === 'pdf' ? 'pdf' : 'csv'}`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Falha na exportação. Tente novamente.');
    } finally {
      setIsExporting(false);
    }
  };

  const backendOnline = health !== null && health.status === 'ok';
  const estoqueDisponivel = backendOnline && health.estoque_carregado;
  const uploadHabilitado = backendOnline && estoqueDisponivel;

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

  // Se a sessão expirou em lote extenso ou snapshot público parcial sem WS ativo
  const filtrosDesabilitados =
    Boolean(wsSessionExpiredNotice) ||
    Boolean(isModoPublico && !isWsSessionActive && simulation && !verificarSnapshotCompleto(simulation));

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

      {/* Aviso de Modo Demonstração Pública Efêmera (se aplicável) */}
      {health?.aviso_demo_publica && (
        <div
          className="alert-banner"
          style={{ borderLeftColor: 'var(--status-info-border)', marginBottom: '24px' }}
          role="region"
          aria-label="Aviso de ambiente de demonstração pública"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Info size={20} color="var(--status-info-text)" aria-hidden="true" />
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', margin: 0 }}>
              {health.aviso_demo_publica}
            </p>
          </div>
        </div>
      )}

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
          <span className="badge-tag">DATA-BASE: {(simulation?.data_base || health?.data_base_atual)?.split('-').reverse().join('/') || 'Consultando…'}</span>
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

      {/* Alerta de Sessão WebSocket Expirada */}
      {wsSessionExpiredNotice && (
        <div
          className="alert-banner"
          style={{ borderLeftColor: 'var(--status-warning-border)', marginBottom: '24px' }}
          role="region"
          aria-label="Aviso de sessão expirada"
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <AlertTriangle size={20} color="var(--status-warning-text)" aria-hidden="true" />
            <div>
              <strong style={{ color: 'var(--status-warning-text)', fontSize: '0.875rem' }}>
                Sessão Interativa Encerrada
              </strong>
              <p style={{ marginTop: 4, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                {wsSessionExpiredNotice}
              </p>
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
          style={{
            backgroundColor: 'var(--status-warning-bg)',
            borderColor: 'var(--status-warning-border)',
            color: 'var(--status-warning-text)',
          }}
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
        <section className="analysis-mode" aria-label="Finalidade do arquivo CSV">
          <label htmlFor="analysis-mode"><strong>O que este CSV representa?</strong></label>
          <select id="analysis-mode" className="select-control" value={tipoAnalise} disabled={isLoading || isExporting}
            onChange={e => setTipoAnalise(e.target.value as 'novas_operacoes' | 'carteira')}>
            <option value="novas_operacoes">Novas notas para antecipação</option>
            <option value="carteira">Estoque histórico dos fundos</option>
          </select>
          <p>{tipoAnalise === 'carteira' ? 'Analisa a carteira enviada, seus valores, vencimentos e concentração por fundo. Não classifica o histórico como novas aprovações ou recusas e não realiza aquisição.' : 'Avalia novas notas com todas as regras ativas, consulta cadastral simulada e duplicidade contra o estoque de referência. Para o arquivo histórico de 100 mil registros, selecione Estoque histórico.'}</p>
        </section>
        <FileUpload
          onFileSelected={handleFileSelected}
          isLoading={isLoading}
          disabled={!uploadHabilitado || isExporting}
        />

        {/* Indicador de Progresso Real (Streaming WebSocket ou Processamento Indeterminado) */}
        {isLoading && (
          <div
            className="loading-box"
            role="status"
            aria-live="polite"
            aria-label="Processando arquivo CSV com o motor de regras"
          >
            {streamProgress ? (
              streamProgress.fase === 'uploading' ? (
                <>
                  <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                    <Wifi size={18} color="var(--accent-blue)" aria-hidden="true" />
                    <span>Transmitindo lote via WebSocket (janela de 4 MiB)...</span>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                    Bytes confirmados: <strong>{((streamProgress.bytesEnviados || 0) / (1024 * 1024)).toFixed(2)} MB</strong> de <strong>{((streamProgress.totalBytes || 1) / (1024 * 1024)).toFixed(2)} MB</strong>
                  </p>
                  <div className="progress-bar-container">
                    <div
                      style={{
                        height: '100%',
                        backgroundColor: 'var(--accent-blue)',
                        width: `${Math.min(100, Math.round(((streamProgress.bytesEnviados || 0) / (streamProgress.totalBytes || 1)) * 100))}%`,
                        transition: 'width 0.2s ease',
                      }}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
                    Motor processando regras do fundo...
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                    Linhas processadas pelo motor: <strong>{streamProgress.linhasProcessadas?.toLocaleString('pt-BR') || 0}</strong> títulos
                  </p>
                  <div className="progress-bar-container">
                    <div className="progress-bar-indeterminate" />
                  </div>
                </>
              )
            ) : (
              <>
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
              </>
            )}
          </div>
        )}

        {/* Resumo e Detalhamento da Simulação */}
        {simulation && (
          <>
            <SummaryCards simulation={simulation} />
            <ResultAnalytics simulation={simulation} onExport={handleExport} exporting={isExporting}
              exportDisabled={isExporting || Boolean(wsSessionExpiredNotice) || isLoading} />

            <ReceivablesTable
              simulation={simulation}
              onPageChange={handlePageChange}
              onFilterChange={handleFilterChange}
              currentStatus={currentStatus}
              currentReason={currentReason}
              filtrosDesabilitados={filtrosDesabilitados}
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
