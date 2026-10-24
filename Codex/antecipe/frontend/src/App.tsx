import React, { useEffect, useState, useRef } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  Info,
  Layers,
  Calculator,
  Sliders,
  LogOut,
  Wifi,
  Loader2,
} from 'lucide-react';
import { FileUpload } from './components/FileUpload';
import { SummaryCards } from './components/SummaryCards';
import { ReceivablesTable } from './components/ReceivablesTable';
import { RejectionChart } from './components/RejectionChart';
import { SingleEvaluateTab } from './components/SingleEvaluateTab';
import { WhatIfSimulatorTab } from './components/WhatIfSimulatorTab';
import { KanastraLogo } from './components/KanastraLogo';
import { LoginPage } from './components/LoginPage';
import { ResultAnalytics } from './components/ResultAnalytics';
import { api } from './services/api';
import {
  SimulationEnvelope,
  HealthResponse,
  PortfolioSummary,
  RuleVersion,
  AuthUser,
  StreamProgressInfo,
} from './types';
import {
  aplicarFiltroPaginacaoLocal,
  verificarSnapshotCompleto,
} from './services/publicDemoResults';
import { BulkUploadSession } from './services/bulkUpload';

export const App: React.FC = () => {
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => api.getAuthSession());
  const [activeTab, setActiveTab] = useState<'lote' | 'individual' | 'what-if'>('lote');

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [activeRuleVersion, setActiveRuleVersion] = useState<RuleVersion | null>(null);
  const [simulation, setSimulation] = useState<SimulationEnvelope | null>(null);

  const snapshotOriginalRef = useRef<SimulationEnvelope | null>(null);
  const bulkSessionRef = useRef<BulkUploadSession | null>(null);
  const [isWsSessionActive, setIsWsSessionActive] = useState(false);
  const [wsSessionExpiredNotice, setWsSessionExpiredNotice] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [loadingFileLabel, setLoadingFileLabel] = useState<string>('');
  const [uploadBytes, setUploadBytes] = useState<{ loaded: number; total: number }>({ loaded: 0, total: 0 });
  const [loadingElapsedSec, setLoadingElapsedSec] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [streamProgress, setStreamProgress] = useState<StreamProgressInfo | null>(null);
  const [tipoAnalise, setTipoAnalise] = useState<'novas_operacoes' | 'carteira'>('novas_operacoes');
  const [isExporting, setIsExporting] = useState(false);

  // Filtros
  const [currentStatus, setCurrentStatus] = useState<string>('todos');
  const [currentReason, setCurrentReason] = useState<string>('todos');

  useEffect(() => {
    return () => {
      if (bulkSessionRef.current) {
        bulkSessionRef.current.close();
        bulkSessionRef.current = null;
      }
    };
  }, []);

  // Cronômetro simples de tempo decorrido durante o envio de lotes CSV
  useEffect(() => {
    if (!isLoading) {
      setLoadingElapsedSec(0);
      return;
    }
    const startMs = Date.now();
    const timer = window.setInterval(() => {
      setLoadingElapsedSec(Math.floor((Date.now() - startMs) / 1000));
    }, 500);
    return () => window.clearInterval(timer);
  }, [isLoading]);

  const checkBackendState = async () => {
    try {
      const [hRes, pRes, rRes] = await Promise.allSettled([
        api.getHealth(),
        api.getPortfolioSummary(),
        api.getRuleVersions(),
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

      if (rRes.status === 'fulfilled') {
        const active = rRes.value.find((v) => v.is_active) || rRes.value[0] || null;
        setActiveRuleVersion(active);
      } else {
        setActiveRuleVersion(null);
      }
    } catch {
      setHealth(null);
      setPortfolio(null);
      setActiveRuleVersion(null);
    }
  };

  useEffect(() => {
    checkBackendState();
    const timer = window.setInterval(() => {
      api.getHealth().then(setHealth).catch(() => setHealth(null));
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [authUser]);

  const isModoPublico = Boolean(health?.aviso_demo_publica);
  const uploadCaps = health?.upload_capabilities;
  const isWsDisponivel = uploadCaps?.bulk_transport === 'websocket';
  const httpMaxBytes = (uploadCaps?.http_max_bytes || 4000000) - 1024;

  const handleFileSelected = async (file: File) => {
    if (bulkSessionRef.current) {
      bulkSessionRef.current.close();
      bulkSessionRef.current = null;
      setIsWsSessionActive(false);
    }

    setIsLoading(true);
    setUploadBytes({ loaded: 0, total: file.size });
    setLoadingFileLabel(`${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`);
    setErrorMessage(null);
    setWsSessionExpiredNotice(null);
    setStreamProgress(null);

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
            if (info.bytesEnviados !== undefined && info.totalBytes) {
              setUploadBytes({ loaded: info.bytesEnviados, total: info.totalBytes });
            }
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
            setUploadBytes({ loaded: file.size, total: file.size });
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
              setWsSessionExpiredNotice(
                'A sessão interativa desta simulação foi encerrada pelo servidor. O resumo inicial foi preservado; para navegar por outras páginas ou filtros deste lote extenso, envie o arquivo novamente.'
              );
            } else {
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

    try {
      const res = await api.uploadSimulation(file, tipoAnalise, (loaded, total) => {
        setUploadBytes({ loaded, total });
      });
      setUploadBytes({ loaded: file.size, total: file.size });
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

    if (bulkSessionRef.current && isWsSessionActive) {
      setIsLoading(true);
      try {
        const filteredSim = await bulkSessionRef.current.query(1, 50, status, reason);
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
      if (bulkSessionRef.current && isWsSessionActive) {
        blob = await bulkSessionRef.current.exportResult(format);
      } else {
        const response = await fetch(
          `/api/simulations/${encodeURIComponent(simulation.simulation_id)}/export?format=${format}`
        );
        if (!response.ok) {
          throw new Error('Não foi possível exportar. Reenvie o arquivo se a sessão expirou.');
        }
        blob = await response.blob();
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `antecipe-${simulation.simulation_id}-${format}.${format === 'pdf' ? 'pdf' : 'csv'}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
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

  const versaoRegraReal =
    simulation?.rule_version !== undefined
      ? `v${simulation.rule_version}`
      : activeRuleVersion?.version_number !== undefined
      ? `v${activeRuleVersion.version_number}`
      : health?.rule_version !== undefined
      ? `v${health.rule_version}`
      : backendOnline
      ? 'v1'
      : 'Offline';

  const estoqueStatusReal =
    portfolio?.total_recebiveis !== undefined
      ? `${portfolio.total_recebiveis.toLocaleString('pt-BR')} títulos`
      : health?.total_registros_estoque !== undefined && health.estoque_carregado
      ? `${health.total_registros_estoque.toLocaleString('pt-BR')} títulos`
      : backendOnline
      ? 'Não carregado'
      : 'Offline';

  const handleLogout = async () => {
    try {
      await api.logout();
      bulkSessionRef.current?.close();
      bulkSessionRef.current = null;
      snapshotOriginalRef.current = null;
      setSimulation(null);
      setAuthUser(null);
    } catch {
      setErrorMessage('Não foi possível encerrar a sessão. Tente novamente.');
    }
  };

  if (!authUser) {
    return <LoginPage onLoginSuccess={(user) => setAuthUser(user)} />;
  }

  const userInitials = authUser.nome
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join('');

  // Exibe avisos de governança somente quando necessário (lote com concentração ou avisos na simulação)
  const motivosCount = simulation?.resumo_motivos || {};
  const temRecusaConcentracaoNoLote =
    (motivosCount['CONCENTRACAO_MAXIMA_SACADO'] || 0) > 0 ||
    Boolean(
      simulation?.analytics?.motivos?.some(
        (m) => m.codigo === 'CONCENTRACAO_MAXIMA_SACADO' && m.quantidade > 0
      )
    );
  const avisosRelevantes = [
    ...(simulation?.avisos || []),
    ...(temRecusaConcentracaoNoLote && portfolio?.avisos ? portfolio.avisos : []),
  ];

  const filtrosDesabilitados =
    Boolean(wsSessionExpiredNotice) ||
    Boolean(isModoPublico && !isWsSessionActive && simulation && !verificarSnapshotCompleto(simulation));

  // Porcentagem efetiva da barra de progresso baseada estritamente no peso/bytes do arquivo
  const effectiveProgressPct =
    uploadBytes.total > 0
      ? Math.min(100, Math.round((uploadBytes.loaded / uploadBytes.total) * 100))
      : 0;

  return (
    <div className="kanastra-shell">
      {/* Topbar Kanastra */}
      <header className="kanastra-topbar" role="banner">
        <div className="kanastra-topbar-inner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '28px', flexWrap: 'wrap' }}>
            <KanastraLogo size={28} subtitle="Backoffice FIDC" />

            <nav className="kanastra-nav-tabs" aria-label="Módulos da plataforma">
              <button
                type="button"
                className={`kanastra-nav-tab ${activeTab === 'lote' ? 'active' : ''}`}
                onClick={() => setActiveTab('lote')}
              >
                <Layers size={15} aria-hidden="true" />
                <span>Remessas CSV</span>
              </button>

              <button
                type="button"
                className={`kanastra-nav-tab ${activeTab === 'individual' ? 'active' : ''}`}
                onClick={() => setActiveTab('individual')}
              >
                <Calculator size={15} aria-hidden="true" />
                <span>Análise Individual</span>
              </button>

              <button
                type="button"
                className={`kanastra-nav-tab ${activeTab === 'what-if' ? 'active' : ''}`}
                onClick={() => setActiveTab('what-if')}
              >
                <Sliders size={15} aria-hidden="true" />
                <span>Política e Regras</span>
              </button>
            </nav>
          </div>

          <div className="kanastra-user-area">
            <div className="kanastra-user-badge" title={`${authUser.email} • ${authUser.cargo}`}>
              <div className="kanastra-user-avatar" aria-hidden="true">
                {userInitials || 'AT'}
              </div>
              <div className="kanastra-user-info">
                <span className="kanastra-user-name">{authUser.nome}</span>
                <span className="kanastra-user-role">{authUser.cargo}</span>
              </div>
            </div>

            <button
              type="button"
              className="btn-secondary"
              onClick={handleLogout}
              style={{ padding: '6px 11px', fontSize: '0.78rem' }}
              title="Encerrar sessão"
            >
              <LogOut size={13} aria-hidden="true" />
              <span>Sair</span>
            </button>
          </div>
        </div>
      </header>

      <div className="app-container">
        {/* Aviso de Modo Demonstração Pública Efêmera (se aplicável) */}
        {health?.aviso_demo_publica && (
          <div
            className="alert-banner"
            style={{ borderLeftColor: 'var(--status-info-border)', marginBottom: '20px' }}
            role="region"
            aria-label="Aviso de ambiente de demonstração pública"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Info size={18} color="var(--status-info-text)" aria-hidden="true" />
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', margin: 0 }}>
                {health.aviso_demo_publica}
              </p>
            </div>
          </div>
        )}

        {/* Alerta de Sessão WebSocket Expirada */}
        {wsSessionExpiredNotice && (
          <div
            className="alert-banner"
            style={{ borderLeftColor: 'var(--status-warning-border)', marginBottom: '20px' }}
            role="region"
            aria-label="Aviso de sessão expirada"
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <AlertTriangle size={18} color="var(--status-warning-text)" aria-hidden="true" />
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

        {/* Faixa de Contexto do Fundo */}
        <section className="kanastra-subheader" aria-label="Fundo sob gestão">
          <div className="kanastra-subheader-meta">
            <span className="kanastra-fund-title">ANTECIPE FIDC</span>
            <span className="kanastra-meta-sep">•</span>
            <span>Data-base: {(simulation?.data_base || health?.data_base_atual)?.split('-').reverse().join('/') || new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo' }).format(new Date())}</span>
          </div>
        </section>

        {/* Alerta de Sessão WebSocket Expirada */}
        {wsSessionExpiredNotice && (
          <div
            className="alert-banner"
            style={{ borderLeftColor: 'var(--status-warning-border)', marginBottom: '20px' }}
            role="region"
            aria-label="Aviso de sessão expirada"
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <AlertTriangle size={18} color="var(--status-warning-text)" aria-hidden="true" />
              <div>
                <strong style={{ color: 'var(--status-warning-text)', fontSize: '0.84rem' }}>
                  Sessão Interativa Encerrada
                </strong>
                <p style={{ marginTop: 4, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {wsSessionExpiredNotice}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Alerta de Indisponibilidade do Backend */}
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
              <AlertTriangle size={18} aria-hidden="true" />
              <span>
                {!backendOnline
                  ? 'Servidor de validação indisponível. Verifique o serviço FastAPI em http://localhost:8000.'
                  : 'A carteira histórica do fundo não foi localizada no banco de dados.'}
              </span>
            </div>
          </div>
        )}

        {/* Alerta de Erro de Conexão ou Validação */}
        {errorMessage && (
          <div className="error-toast" role="alert" aria-live="assertive">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <ShieldAlert size={18} aria-hidden="true" />
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

        {/* Conteúdo Principal por Aba */}
        <main>
          {activeTab === 'individual' && <SingleEvaluateTab />}

          {activeTab === 'what-if' && (
            <WhatIfSimulatorTab onRulesUpdated={checkBackendState} />
          )}

          {activeTab === 'lote' && (
            <>
              <section className="analysis-mode" aria-label="Finalidade do arquivo CSV">
                <label htmlFor="analysis-mode">
                  <strong>Finalidade da remessa CSV</strong>
                </label>
                <select
                  id="analysis-mode"
                  className="select-control"
                  value={tipoAnalise}
                  disabled={isLoading || isExporting}
                  onChange={(e) =>
                    setTipoAnalise(e.target.value as 'novas_operacoes' | 'carteira')
                  }
                >
                  <option value="novas_operacoes">
                    Novas operações para antecipação (avaliação de elegibilidade e deságio)
                  </option>
                  <option value="carteira">
                    Auditoria descritiva de estoque histórico (sem nova aquisição)
                  </option>
                </select>
                <p>
                  {tipoAnalise === 'carteira'
                    ? 'Analisa descritivamente o estoque enviado, seus valores, vencimentos e concentração por fundo.'
                    : 'Avalia os títulos da planilha frente às regras ativas do fundo, situação cadastral, concentração por raiz de CNPJ e antiduplicidade.'}
                </p>
              </section>

              <FileUpload
                onFileSelected={handleFileSelected}
                isLoading={isLoading}
                disabled={!uploadHabilitado || isExporting}
              />

              {/* Barra de Carregamento baseada exclusivamente no peso do arquivo CSV */}
              {isLoading && (
                <div
                  className="loading-box"
                  role="status"
                  aria-live="polite"
                  aria-label="Carregando lote CSV"
                >
                  <div className="loading-header-row">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Loader2 size={18} color="#34d399" className="spin-icon" aria-hidden="true" />
                      <strong style={{ fontSize: '0.96rem', color: 'var(--text-primary)' }}>
                        {effectiveProgressPct >= 100
                          ? 'Upload concluído. Processando resultado...'
                          : 'Transmitindo arquivo CSV...'}
                      </strong>
                    </div>
                    <span className="loading-pct-badge">{effectiveProgressPct}%</span>
                  </div>

                  <div
                    className="progress-bar-container"
                    role="progressbar"
                    aria-valuenow={effectiveProgressPct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label="Progresso do envio do arquivo CSV"
                  >
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${effectiveProgressPct}%` }}
                    />
                  </div>

                  <div className="loading-meta-row">
                    <span>
                      {loadingFileLabel ? `Arquivo: ${loadingFileLabel}` : 'Planilha CSV'}
                    </span>
                    <span>
                      {uploadBytes.total > 0
                        ? `${((uploadBytes.loaded || 0) / (1024 * 1024)).toFixed(2)} MB / ${(
                            uploadBytes.total /
                            (1024 * 1024)
                          ).toFixed(2)} MB`
                        : '0.00 MB / 0.00 MB'}
                    </span>
                  </div>
                </div>
              )}

              {/* Resumo, Gráficos, Exportações e Detalhamento da Simulação */}
              {simulation && (
                <>
                  <SummaryCards simulation={simulation} />

                  <RejectionChart
                    simulation={simulation}
                    currentReason={currentReason}
                    onSelectReason={(reasonCode) => {
                      const nextStatus = reasonCode === 'todos' ? 'todos' : 'RECUSADA';
                      handleFilterChange(nextStatus, reasonCode);
                    }}
                  />

                  <ResultAnalytics
                    simulation={simulation}
                    onExport={handleExport}
                    exporting={isExporting}
                    exportDisabled={isExporting || Boolean(wsSessionExpiredNotice) || isLoading}
                  />

                  <ReceivablesTable
                    simulation={simulation}
                    onPageChange={handlePageChange}
                    onFilterChange={handleFilterChange}
                    currentStatus={currentStatus}
                    currentReason={currentReason}
                    filtrosDesabilitados={filtrosDesabilitados}
                  />

                  <section className="audit-card" aria-label="Metadados de auditoria da simulação">
                    <div className="audit-meta-item">
                      ID da Operação: <strong>{simulation.simulation_id}</strong>
                    </div>
                    <div className="audit-meta-item">
                      Fonte Cadastral: <strong>{simulation.auditoria.cadastro_fonte}</strong>
                    </div>
                    <div className="audit-meta-item">
                      Carteira de Referência:{' '}
                      <strong>{simulation.auditoria.carteira_referencia}</strong>
                    </div>
                    <div className="audit-meta-item">
                      Hash da Regra:{' '}
                      <span style={{ fontFamily: 'var(--font-mono)' }}>
                        {simulation.auditoria.configuration_hash.substring(0, 12)}...
                      </span>
                    </div>
                  </section>
                </>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
};
