import React, { useEffect, useState } from 'react';
import {
  Sliders,
  Play,
  RotateCcw,
  ArrowRight,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  Save,
} from 'lucide-react';
import { RuleConfiguration, PersonalPolicy, WhatIfResult } from '../types';
import { api } from '../services/api';
import { formatarMoedaBRL } from '../services/currency';

interface WhatIfSimulatorTabProps {
  onRulesUpdated?: () => void;
}

const tipoDaApi = (tipo: string) => tipo === 'Duplicata Mercantil' ? 'Duplicata' : tipo === 'Duplicata de Servico' ? 'Duplicata de Serviço' : tipo;

const TIPOS_RECEBIVEIS_OPCOES = [
  'Duplicata Mercantil',
  'Duplicata de Servico',
  'Cheque',
  'Nota Comercial',
  'CCB',
];

export const WhatIfSimulatorTab: React.FC<WhatIfSimulatorTabProps> = ({ onRulesUpdated }) => {
  const [baseRules, setBaseRules] = useState<RuleConfiguration | null>(null);
  const [policies, setPolicies] = useState<PersonalPolicy[]>([]);
  const [activePolicy, setActivePolicy] = useState("default");
  const [policiesReady, setPoliciesReady] = useState(false);
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Parâmetros editáveis de todos os validadores e precificação
  const [concSacadoMax, setConcSacadoMax] = useState<number>(10.0);
  const [prazoMaxDias, setPrazoMaxDias] = useState<number>(180);
  const [valorMinimo, setValorMinimo] = useState<number>(100.0);
  const [prazoMinDias, setPrazoMinDias] = useState<number>(30);
  const [concCedenteMax, setConcCedenteMax] = useState<number>(8.0);
  const [taxaMensalPct, setTaxaMensalPct] = useState<number>(2.0);
  const [baseDias, setBaseDias] = useState<number>(30);
  const [tiposAceitos, setTiposAceitos] = useState<string[]>([
    'Duplicata Mercantil',
    'Duplicata de Servico',
  ]);
  const [validatorActiveMap, setValidatorActiveMap] = useState<Record<string, boolean>>({});
  const [changeReason, setChangeReason] = useState<string>('');
  const [sampleRows, setSampleRows] = useState<number>(100);

  const syncFormFromConfig = (cfg: RuleConfiguration) => {
    setTaxaMensalPct(Number(cfg.precificacao?.taxa_mensal_percentual ?? 2.0));
    setBaseDias(Number(cfg.precificacao?.base_dias ?? 30));
    const activeMap: Record<string, boolean> = {};
    for (const v of cfg.validadores || []) {
      activeMap[v.codigo] = Boolean(v.ativo);
      if (v.codigo === 'CONCENTRACAO_MAXIMA_SACADO') {
        setConcSacadoMax(Number(v.parametros?.percentual_maximo ?? 10.0));
      } else if (v.codigo === 'PRAZO_MAXIMO') {
        setPrazoMaxDias(Number(v.parametros?.prazo_maximo_dias ?? 180));
      } else if (v.codigo === 'VALOR_MINIMO') {
        setValorMinimo(Number(v.parametros?.valor_minimo ?? 100.0));
      } else if (v.codigo === 'PRAZO_MINIMO') {
        setPrazoMinDias(Number(v.parametros?.prazo_minimo_dias ?? 30));
      } else if (v.codigo === 'CONCENTRACAO_MAXIMA_CEDENTE') {
        setConcCedenteMax(Number(v.parametros?.percentual_maximo ?? 8.0));
      } else if (v.codigo === 'TIPO_RECEBIVEL') {
        const tipos = v.parametros?.tipos_aceitos;
        if (Array.isArray(tipos) && tipos.length > 0) {
          setTiposAceitos(tipos.map(String));
        }
      }
    }
    setValidatorActiveMap(activeMap);
  };

  const loadRules = async () => {
    setPoliciesReady(false);
    try {
      const cfg = await api.getActiveRules();
      setBaseRules(cfg);

      syncFormFromConfig(cfg);
      const saved = await api.getPersonalPolicies();
      setPolicies(saved);
      setActivePolicy(saved.find(p => p.is_active)?.id || 'default');
      setPoliciesReady(true);
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message);
      throw err;
    }
  };

  useEffect(() => {
    loadRules().catch(() => undefined);
  }, []);

  const buildCurrentConfiguration = (): RuleConfiguration | null => {
    if (!baseRules) return null;
    const cloned: RuleConfiguration = JSON.parse(JSON.stringify(baseRules));
    cloned.precificacao.taxa_mensal_percentual = Number(taxaMensalPct);
    cloned.precificacao.base_dias = Math.max(1, Math.round(Number(baseDias)));
    for (const v of cloned.validadores) {
      if (v.codigo in validatorActiveMap) {
        v.ativo = Boolean(validatorActiveMap[v.codigo]);
      }
      if (v.codigo === 'CONCENTRACAO_MAXIMA_SACADO') {
        v.parametros.percentual_maximo = Number(concSacadoMax);
      } else if (v.codigo === 'PRAZO_MAXIMO') {
        v.parametros.prazo_maximo_dias = Math.round(Number(prazoMaxDias));
      } else if (v.codigo === 'VALOR_MINIMO') {
        v.parametros.valor_minimo = Number(valorMinimo);
      } else if (v.codigo === 'PRAZO_MINIMO') {
        v.parametros.prazo_minimo_dias = Math.round(Number(prazoMinDias));
      } else if (v.codigo === 'CONCENTRACAO_MAXIMA_CEDENTE') {
        v.parametros.percentual_maximo = Number(concCedenteMax);
      } else if (v.codigo === 'TIPO_RECEBIVEL') {
        v.parametros.tipos_aceitos = tiposAceitos.map(tipoDaApi);
      }
    }
    return cloned;
  };

  const handleToggleValidator = (codigo: string) => {
    setValidatorActiveMap((prev) => ({
      ...prev,
      [codigo]: !prev[codigo],
    }));
  };

  const handleToggleTipoRecebivel = (tipo: string) => {
    tipo = tipoDaApi(tipo);
    setTiposAceitos((prev) => {
      if (prev.includes(tipo)) {
        if (prev.length === 1) return prev; // mantém ao menos 1 tipo
        return prev.filter((t) => t !== tipo);
      }
      return [...prev, tipo];
    });
  };

  const handleRunWhatIf = async () => {
    const cfg = buildCurrentConfiguration();
    if (!cfg) return;
    setWhatIfResult(null);
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await api.runWhatIfSimulation(cfg, sampleRows);
      setWhatIfResult(res);
      setSuccessMsg('OK: impacto simulado com sucesso. Confira os resultados abaixo.');
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAndApplyRules = async () => {
    const cfg = buildCurrentConfiguration();
    if (!cfg) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const saved = await api.savePersonalPolicy(changeReason.trim(), cfg);
      setBaseRules(saved.configuration);
      syncFormFromConfig(saved.configuration);
      setPolicies(previous => [saved, ...previous.map(p => ({...p, is_active: false}))]);
      setActivePolicy(saved.id);
      setChangeReason('');
      setWhatIfResult(null);
      setSuccessMsg('Política salva na sua conta e selecionada para as próximas análises.');
      if (onRulesUpdated) onRulesUpdated();
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRestoreDefaults = async () => {
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await api.activatePersonalPolicy('default');
      await loadRules();
      setWhatIfResult(null);
      setSuccessMsg('Política padrão selecionada. Suas opções salvas foram preservadas.');
      if (onRulesUpdated) onRulesUpdated();
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section aria-labelledby="what-if-title">
      <div className="table-section" style={{ padding: '24px', marginBottom: '24px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: '16px',
            marginBottom: '20px',
          }}
        >
          <div>
            <h2
              id="what-if-title"
              style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <Sliders size={18} color="#34d399" aria-hidden="true" />
              <span>Configuração de Política, Parâmetros do Fundo e Simulador &ldquo;What-If&rdquo;</span>
            </h2>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: 4 }}>
              Altere qualquer parâmetro das regras de negócio ou precificação diretamente por esta interface. Você pode{' '}
              <strong>simular o impacto</strong> antes ou <strong>salvar e selecionar uma política da sua conta</strong> sem editar arquivos JSON.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleRestoreDefaults}
              disabled={loading || saving || !policiesReady}
            >
              <RotateCcw size={15} aria-hidden="true" />
              <span>Restaurar Padrão do Regulamento</span>
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleRunWhatIf}
              disabled={loading || saving || !baseRules}
            >
              <Play size={15} aria-hidden="true" />
              <span>{loading ? 'Simulando...' : 'Simular Impacto (What-If)'}</span>
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={handleSaveAndApplyRules}
              disabled={loading || saving || !baseRules || !policiesReady || !changeReason.trim()}
            >
              <Save size={15} aria-hidden="true" />
              <span>{saving ? 'Salvando Política...' : 'Salvar como nova política'}</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="error-toast" role="alert" style={{ marginBottom: '16px' }}>
            <XCircle size={16} aria-hidden="true" /><span>Erro: {error}</span>
          </div>
        )}

        {successMsg && (
          <div
            role="status"
            style={{
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.35)',
              color: '#a7f3d0',
              padding: '12px 16px',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '0.84rem',
            }}
          >
            <CheckCircle2 size={16} color="#34d399" aria-hidden="true" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Controles Numéricos e de Precificação */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '16px',
            marginBottom: '20px',
          }}
        >
          <div className="metric-card">
            <label
              htmlFor="wi-conc-sacado"
              className="metric-title"
              style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}
            >
              <span>Teto Concentração Raiz Sacado (%)</span>
              <input
                type="checkbox"
                checked={Boolean(validatorActiveMap['CONCENTRACAO_MAXIMA_SACADO'] ?? true)}
                onChange={() => handleToggleValidator('CONCENTRACAO_MAXIMA_SACADO')}
                title="Ativar/Desativar regra CONCENTRACAO_MAXIMA_SACADO"
              />
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input
                id="wi-conc-sacado"
                type="range"
                min={1}
                max={50}
                step={0.5}
                value={concSacadoMax}
                onChange={(e) => setConcSacadoMax(parseFloat(e.target.value) || 0)}
                style={{ flex: 1 }}
              />
              <input
                type="number"
                min={0.5}
                max={100}
                step={0.5}
                value={concSacadoMax}
                onChange={(e) => setConcSacadoMax(parseFloat(e.target.value) || 0)}
                aria-label="Valor numérico concentração sacado"
                className="select-control"
                style={{ width: '82px', fontFamily: 'var(--font-mono)', textAlign: 'right' }}
              />
            </div>
            <div className="metric-sub">Padrão do regulamento: 10,0% por raiz de CNPJ (8 dígitos)</div>
          </div>

          <div className="metric-card">
            <label
              htmlFor="wi-prazo-max"
              className="metric-title"
              style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}
            >
              <span>Prazo Máximo de Vencimento (Dias)</span>
              <input
                type="checkbox"
                checked={Boolean(validatorActiveMap['PRAZO_MAXIMO'] ?? true)}
                onChange={() => handleToggleValidator('PRAZO_MAXIMO')}
                title="Ativar/Desativar regra PRAZO_MAXIMO"
              />
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input
                id="wi-prazo-max"
                type="range"
                min={15}
                max={720}
                step={5}
                value={prazoMaxDias}
                onChange={(e) => setPrazoMaxDias(parseInt(e.target.value, 10) || 0)}
                style={{ flex: 1 }}
              />
              <input
                type="number"
                min={1}
                max={3650}
                step={1}
                value={prazoMaxDias}
                onChange={(e) => setPrazoMaxDias(parseInt(e.target.value, 10) || 0)}
                aria-label="Valor numérico prazo máximo em dias"
                className="select-control"
                style={{ width: '82px', fontFamily: 'var(--font-mono)', textAlign: 'right' }}
              />
            </div>
            <div className="metric-sub">Padrão do regulamento: 180 dias corridos</div>
          </div>

          <div className="metric-card">
            <label
              htmlFor="wi-valor-min"
              className="metric-title"
              style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}
            >
              <span>Valor Nominal Mínimo (R$)</span>
              <input
                type="checkbox"
                checked={Boolean(validatorActiveMap['VALOR_MINIMO'] ?? true)}
                onChange={() => handleToggleValidator('VALOR_MINIMO')}
                title="Ativar/Desativar regra VALOR_MINIMO"
              />
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input
                id="wi-valor-min"
                type="range"
                min={10}
                max={2000}
                step={10}
                value={valorMinimo}
                onChange={(e) => setValorMinimo(parseFloat(e.target.value) || 0)}
                style={{ flex: 1 }}
              />
              <input
                type="number"
                min={0}
                max={1000000}
                step={10}
                value={valorMinimo}
                onChange={(e) => setValorMinimo(parseFloat(e.target.value) || 0)}
                aria-label="Valor numérico nominal mínimo"
                className="select-control"
                style={{ width: '92px', fontFamily: 'var(--font-mono)', textAlign: 'right' }}
              />
            </div>
            <div className="metric-sub">Padrão do regulamento: R$ 100,00 por título</div>
          </div>

          <div className="metric-card">
            <label
              htmlFor="wi-taxa-mensal"
              className="metric-title"
              style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}
            >
              <span>Taxa de Desconto Comercial (% a.m.)</span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Base {baseDias}d</span>
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input
                id="wi-taxa-mensal"
                type="range"
                min={0.1}
                max={10.0}
                step={0.1}
                value={taxaMensalPct}
                onChange={(e) => setTaxaMensalPct(parseFloat(e.target.value) || 0)}
                style={{ flex: 1 }}
              />
              <input
                type="number"
                min={0}
                max={30}
                step={0.05}
                value={taxaMensalPct}
                onChange={(e) => setTaxaMensalPct(parseFloat(e.target.value) || 0)}
                aria-label="Taxa mensal percentual"
                className="select-control"
                style={{ width: '82px', fontFamily: 'var(--font-mono)', textAlign: 'right' }}
              />
            </div>
            <div className="metric-sub">Padrão do regulamento: 2,00% a.m. (Desconto Simples)</div>
          </div>

          <div className="metric-card">
            <label
              htmlFor="wi-prazo-min"
              className="metric-title"
              style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}
            >
              <span>Prazo Mínimo de Vencimento (Dias)</span>
              <input
                type="checkbox"
                checked={Boolean(validatorActiveMap['PRAZO_MINIMO'] ?? false)}
                onChange={() => handleToggleValidator('PRAZO_MINIMO')}
                aria-label="Ativar regra de prazo mínimo"
              />
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input
                id="wi-prazo-min"
                type="number"
                min={0}
                max={360}
                step={1}
                value={prazoMinDias}
                onChange={(e) => setPrazoMinDias(parseInt(e.target.value, 10) || 0)}
                className="select-control"
                style={{ width: '92px', fontFamily: 'var(--font-mono)' }}
              />
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {validatorActiveMap['PRAZO_MINIMO'] ? 'Regra ATIVA' : 'Regra INATIVA'}
              </span>
            </div>
            <div className="metric-sub">Carência mínima do vencimento frente à data-base</div>
          </div>

          <div className="metric-card">
            <label
              htmlFor="wi-conc-cedente"
              className="metric-title"
              style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}
            >
              <span>Concentração Máxima por Cedente (%)</span>
              <input
                type="checkbox"
                checked={Boolean(validatorActiveMap['CONCENTRACAO_MAXIMA_CEDENTE'] ?? false)}
                onChange={() => handleToggleValidator('CONCENTRACAO_MAXIMA_CEDENTE')}
                aria-label="Ativar regra de concentração máxima por cedente"
              />
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input
                id="wi-conc-cedente"
                type="number"
                min={1}
                max={100}
                step={0.5}
                value={concCedenteMax}
                onChange={(e) => setConcCedenteMax(parseFloat(e.target.value) || 0)}
                className="select-control"
                style={{ width: '92px', fontFamily: 'var(--font-mono)' }}
              />
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {validatorActiveMap['CONCENTRACAO_MAXIMA_CEDENTE'] ? 'Regra ATIVA' : 'Regra INATIVA'}
              </span>
            </div>
            <div className="metric-sub">Limite de exposição individual por cedente</div>
          </div>
        </div>

        {/* Seleção de Tipos de Recebível Aceitos e Motivo da Alteração */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '16px',
            marginBottom: '16px',
            padding: '14px 16px',
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, marginBottom: '8px', color: 'var(--text-primary)' }}>
              Modalidades Aceitas (`TIPO_RECEBIVEL`):
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {TIPOS_RECEBIVEIS_OPCOES.map((tipo) => {
                const checked = tiposAceitos.includes(tipoDaApi(tipo));
                return (
                  <button
                    key={tipo}
                    type="button"
                    onClick={() => handleToggleTipoRecebivel(tipo)}
                    className={checked ? 'badge approved' : 'badge warning'}
                    style={{
                      cursor: 'pointer',
                      padding: '5px 10px',
                      border: checked
                        ? '1px solid rgba(16, 185, 129, 0.5)'
                        : '1px solid var(--border-subtle)',
                    }}
                  >
                    {checked ? '✓ ' : '+ '}
                    {tipo}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label
              htmlFor="wi-change-reason"
              style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '6px' }}
            >
              Nome da nova política:
            </label>
            <input
              id="wi-change-reason"
              maxLength={100}
              type="text"
              className="select-control"
              style={{ width: '100%' }}
              value={changeReason}
              onChange={(e) => setChangeReason(e.target.value)}
              placeholder="Ex.: Política comercial de outubro"
            />
          </div>
        </div>

        {/* Seleção rápida de tamanho de amostra e presets */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Cenários Rápidos:</span>
            <button
              type="button"
              className="btn-secondary"
              style={{ padding: '5px 10px', fontSize: '0.75rem' }}
              onClick={() => {
                setConcSacadoMax(15.0);
                setPrazoMaxDias(240);
                setValorMinimo(50.0);
              }}
            >
              Política Flexibilizada (Raiz 15% / 240d / R$ 50)
            </button>
            <button
              type="button"
              className="btn-secondary"
              style={{ padding: '5px 10px', fontSize: '0.75rem' }}
              onClick={() => {
                setConcSacadoMax(8.0);
                setPrazoMaxDias(90);
                setValidatorActiveMap((prev) => ({ ...prev, PRAZO_MINIMO: true }));
              }}
            >
              Política Conservadora (Raiz 8% / 90d / Prazo Mín Ativo)
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label htmlFor="wi-sample-size" style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              Amostra do What-If:
            </label>
            <select
              id="wi-sample-size"
              className="select-control"
              value={sampleRows}
              onChange={(e) => setSampleRows(Number(e.target.value))}
            >
              <option value={100}>100 títulos sintéticos</option>
              <option value={1000}>1.000 títulos sintéticos</option>
            </select>
          </div>
        </div>
      </div>

      {/* Resultado Comparativo Lado a Lado */}
      {whatIfResult && (
        <div
          className="summary-grid"
          style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', marginBottom: '24px' }}
        >
          <div className="metric-card" style={{ borderLeft: '4px solid var(--border-subtle)' }}>
            <div className="metric-title">Política selecionada atual</div>
            <div className="metric-value" style={{ color: 'var(--text-primary)' }}>
              {whatIfResult.baseline.aprovados} / {whatIfResult.baseline.total_itens} aprovados
            </div>
            <div className="metric-sub">
              Taxa de aprovação: {whatIfResult.baseline.taxa_aprovacao_pct}% | Líquido:{' '}
              <strong>{formatarMoedaBRL(whatIfResult.baseline.total_liquido)}</strong>
            </div>
          </div>

          <div className="metric-card" style={{ borderLeft: '4px solid #34d399' }}>
            <div className="metric-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <ArrowRight size={14} color="#34d399" />
              <span>Cenário Simulado &ldquo;What-If&rdquo;</span>
            </div>
            <div className="metric-value" style={{ color: '#34d399' }}>
              {whatIfResult.what_if.aprovados} / {whatIfResult.what_if.total_itens} aprovados
            </div>
            <div className="metric-sub">
              Taxa de aprovação: {whatIfResult.what_if.taxa_aprovacao_pct}% | Líquido:{' '}
              <strong>{formatarMoedaBRL(whatIfResult.what_if.total_liquido)}</strong>
            </div>
          </div>

          <div
            className="metric-card"
            style={{
              borderLeft:
                whatIfResult.delta.aprovados_delta >= 0 ? '4px solid #10b981' : '4px solid #ef4444',
            }}
          >
            <div className="metric-title">Impacto Líquido (Delta What-If vs Ativa)</div>
            <div
              className="metric-value"
              style={{
                color: whatIfResult.delta.aprovados_delta >= 0 ? '#10b981' : '#ef4444',
              }}
            >
              {whatIfResult.delta.aprovados_delta >= 0 ? '+' : ''}
              {whatIfResult.delta.aprovados_delta} títulos
            </div>
            <div className="metric-sub">
              Diferença de Desembolso Líquido:{' '}
              <strong>{formatarMoedaBRL(whatIfResult.delta.liquido_delta_brl)}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Governança: Lista Oficial dos 9 Validadores com chaveamento direto e Histórico de Versões */}
      {baseRules && (
        <div className="table-section" style={{ padding: '20px' }}>
          <h3
            style={{
              fontSize: '1rem',
              fontWeight: 600,
              marginBottom: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <ShieldCheck size={18} color="#10b981" aria-hidden="true" />
            <span>Matriz de Validadores do Fundo ({baseRules.validadores.length} regras configuráveis)</span>
          </h3>

          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>Código da Regra</th>
                  <th>Status Configurado (Clique para Alternar)</th>
                  <th>Parâmetros Ativos</th>
                </tr>
              </thead>
              <tbody>
                {(buildCurrentConfiguration()?.validadores || baseRules.validadores).map((val) => {
                  const isAtivo = Boolean(validatorActiveMap[val.codigo] ?? val.ativo);
                  return (
                    <tr key={val.codigo}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{val.codigo}</td>
                      <td>
                        <button
                          type="button"
                          onClick={() => handleToggleValidator(val.codigo)}
                          className={`badge ${isAtivo ? 'approved' : 'warning'}`}
                          style={{ cursor: 'pointer', border: 'none' }}
                          title="Clique para ativar ou desativar esta regra"
                        >
                          {isAtivo ? (
                            <>
                              <CheckCircle2 size={11} style={{ marginRight: 4 }} />
                              ATIVO
                            </>
                          ) : (
                            'INATIVO (IGNORADO)'
                          )}
                        </button>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        {JSON.stringify(val.parametros)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
            <label htmlFor="saved-policy" style={{ display: 'block', marginBottom: 8 }}>Minhas políticas salvas</label>
            <select id="saved-policy" className="select-control" value={activePolicy}
              disabled={loading || saving || !policiesReady}
              onChange={async (event) => {
                const id = event.target.value;
                setSaving(true); setError(null); setSuccessMsg(null); setWhatIfResult(null);
                try {
                  await api.activatePersonalPolicy(id);
                  await loadRules();
                  setSuccessMsg('OK: política selecionada para as próximas análises.');
                  onRulesUpdated?.();
                } catch (err) { setError(err instanceof Error ? err.message : 'Não foi possível selecionar a política.'); }
                finally { setSaving(false); }
              }}>
              <option value="default">Padrão do regulamento</option>
              {policies.map(policy => <option key={policy.id} value={policy.id}>{policy.name}</option>)}
            </select>
            <p className="metric-sub">As opções ficam vinculadas à sua conta. Alterações salvas criam uma nova opção; análises concluídas mantêm as regras utilizadas.</p>
          </div>
        </div>
      )}
    </section>
  );
};
