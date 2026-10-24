import React, { useState } from 'react';
import {
  Building2,
  CheckCircle2,
  Lock,
  LogOut,
  Mail,
  ShieldCheck,
  Sparkles,
  UserCheck,
  UserPlus,
  AlertCircle,
} from 'lucide-react';
import { useAuth } from './AuthContext';

const GoogleLogoSvg: React.FC = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
    <path
      fill="#EA4335"
      d="M12 10.2v3.9h5.5c-.2 1.3-1.6 3.8-5.5 3.8-3.3 0-6-2.7-6-6s2.7-6 6-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.4 14.6 2.5 12 2.5 6.8 2.5 2.5 6.8 2.5 12s4.3 9.5 9.5 9.5c5.5 0 9.1-3.9 9.1-9.3 0-.6-.1-1.1-.2-1.6H12z"
    />
    <path
      fill="#34A853"
      d="M3.6 7.4l3.2 2.4C7.7 7.6 9.7 6 12 6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.4 14.6 2.5 12 2.5 8.3 2.5 5.1 4.6 3.6 7.4z"
    />
    <path
      fill="#FBBC05"
      d="M12 21.5c2.5 0 4.7-.8 6.3-2.3l-3-2.4c-.8.6-1.9 1-3.3 1-3.8 0-5.2-2.5-5.5-3.8l-3.2 2.5c1.5 3 4.8 5 8.7 5z"
    />
    <path
      fill="#4285F4"
      d="M21.1 12.2c0-.6-.1-1.1-.2-1.6H12v3.9h5.5c-.3 1.3-1.1 2.4-2.2 3.1l3 2.4c1.7-1.6 2.8-4 2.8-7.8z"
    />
  </svg>
);

export const EntrepreneurSessionBadge: React.FC = () => {
  const { user, logout } = useAuth();

  if (!user) {
    return null;
  }

  const initials = user.name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');

  const providerLabel =
    user.provider === 'google'
      ? 'Google Gmail'
      : user.provider === 'auth0'
      ? 'Auth0 SSO'
      : user.provider === 'demo'
      ? 'Modo Demo'
      : 'Conta Cedente';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '6px 12px',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
      }}
      aria-label={`Sessão ativa de ${user.name}`}
    >
      {user.pictureUrl ? (
        <img
          src={user.pictureUrl}
          alt=""
          style={{ width: 28, height: 28, borderRadius: '50%', objectFit: 'cover' }}
        />
      ) : (
        <div
          aria-hidden="true"
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            backgroundColor: 'var(--status-info-bg)',
            border: '1px solid var(--status-info-border)',
            color: 'var(--status-info-text)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.75rem',
            fontWeight: 700,
          }}
        >
          {initials || 'EC'}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          {user.name}
        </span>
        <span style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)' }}>
          {user.companyName} • {providerLabel}
        </span>
      </div>

      <button
        type="button"
        className="btn-secondary"
        onClick={logout}
        aria-label="Encerrar sessão e sair"
        style={{ padding: '4px 8px', fontSize: '0.75rem', marginLeft: '4px' }}
      >
        <LogOut size={13} aria-hidden="true" />
        <span>Sair</span>
      </button>
    </div>
  );
};

export const EntrepreneurAuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const {
    isAuthenticated,
    isLoading,
    isAuth0Configured,
    authError,
    clearError,
    loginWithGoogle,
    loginWithEmail,
    loginWithAuth0Redirect,
    loginAsDemoEntrepreneur,
  } = useAuth();

  const [tab, setTab] = useState<'login' | 'signup'>('login');

  const [name, setName] = useState<string>('');
  const [companyName, setCompanyName] = useState<string>('');
  const [cnpj, setCnpj] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');

  if (isLoading) {
    return (
      <div className="app-container" style={{ display: 'flex', justifyContent: 'center', paddingTop: '80px' }}>
        <div className="loading-box" role="status" aria-live="polite" style={{ maxWidth: 420, width: '100%' }}>
          <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
            Verificando sessão do Portal do Cedente...
          </div>
          <div className="progress-bar-container" style={{ marginTop: 12 }}>
            <div className="progress-bar-indeterminate" />
          </div>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <>{children}</>;
  }

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await loginWithEmail({
      mode: tab,
      email,
      password,
      name,
      companyName: companyName || 'Indústria Brasil S.A.',
      cnpj: cnpj || '11.222.333/0001-81',
    });
  };

  const handleGoogleButtonClick = async () => {
    clearError();
    await loginWithGoogle();
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '10px 12px',
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--radius-md)',
    color: 'var(--text-primary)',
    fontSize: '0.875rem',
    fontFamily: 'var(--font-sans)',
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '0.75rem',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: '6px',
    textTransform: 'uppercase',
    letterSpacing: '0.03em',
  };

  return (
    <div className="app-container" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '32px',
          alignItems: 'stretch',
          maxWidth: '1040px',
          margin: '0 auto',
          width: '100%',
        }}
      >
        {/* Coluna Esquerda: Proposta de Valor para o Empresário Cedente */}
        <section
          aria-labelledby="auth-hero-title"
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '32px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <span
                style={{
                  fontSize: '1.5rem',
                  fontWeight: 800,
                  color: 'var(--text-primary)',
                  letterSpacing: '-0.025em',
                }}
              >
                Antecipe
              </span>
              <span className="header-badge">Portal do Empresário</span>
            </div>

            <h1
              id="auth-hero-title"
              style={{
                fontSize: '1.625rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                lineHeight: 1.25,
                marginBottom: '12px',
              }}
            >
              Transforme suas vendas a prazo em caixa imediato com transparência.
            </h1>

            <p style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)', marginBottom: '28px' }}>
              Acesse sua conta para enviar lotes de duplicatas, simular o valor líquido de antecipação
              no <strong>ANTECIPE FIDC</strong> e visualizar a elegibilidade de cada nota em segundos.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <CheckCircle2 size={20} color="var(--status-success-text)" style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                    Taxa Transparente de 2,00% a.m. (Desconto Simples)
                  </strong>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Cálculo exato ao centavo para cada parcela aprovada, sem taxas ocultas.
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <ShieldCheck size={20} color="var(--status-info-text)" style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                    Diagnóstico Claro por Nota Fiscal
                  </strong>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Saiba imediatamente quais títulos foram aprovados e a orientação exata caso alguma nota seja recusada.
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <Building2 size={20} color="var(--status-warning-text)" style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                    Proteção Anti-Duplicidade e Governança FIDC
                  </strong>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Auditoria automática contra a carteira do fundo (CNPJ 92.234.400/0001-80).
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: '32px',
              paddingTop: '20px',
              borderTop: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>
              Avaliando o projeto no Hackathon Kanastra? Entre com 1 clique sem precisar preencher cadastro:
            </div>
            <button
              type="button"
              className="btn-secondary"
              onClick={loginAsDemoEntrepreneur}
              style={{
                width: '100%',
                justifyContent: 'center',
                padding: '10px 16px',
                borderColor: 'var(--status-info-border)',
                backgroundColor: 'var(--status-info-bg)',
                color: 'var(--status-info-text)',
                fontWeight: 600,
              }}
            >
              <Sparkles size={16} aria-hidden="true" />
              <span>Acesso Rápido — Empresário Demo (Indústria Brasil S.A.)</span>
            </button>
          </div>
        </section>

        {/* Coluna Direita: Card de Autenticação (Google via Auth0 Vercel + E-mail/Criar Conta) */}
        <section
          aria-label="Autenticação do empresário"
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '32px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            {/* Abas Entrar vs Criar Conta */}
            <div
              role="tablist"
              aria-label="Opções de acesso"
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '8px',
                backgroundColor: 'var(--bg-primary)',
                padding: '4px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                marginBottom: '24px',
              }}
            >
              <button
                type="button"
                role="tab"
                aria-selected={tab === 'login'}
                onClick={() => {
                  setTab('login');
                  clearError();
                }}
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  backgroundColor: tab === 'login' ? 'var(--accent-blue)' : 'transparent',
                  color: tab === 'login' ? '#ffffff' : 'var(--text-secondary)',
                  fontWeight: 600,
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                }}
              >
                <UserCheck size={15} aria-hidden="true" />
                <span>Entrar na Conta</span>
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={tab === 'signup'}
                onClick={() => {
                  setTab('signup');
                  clearError();
                }}
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  backgroundColor: tab === 'signup' ? 'var(--accent-blue)' : 'transparent',
                  color: tab === 'signup' ? '#ffffff' : 'var(--text-secondary)',
                  fontWeight: 600,
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                }}
              >
                <UserPlus size={15} aria-hidden="true" />
                <span>Criar Conta</span>
              </button>
            </div>

            {/* Botão Principal: Continuar com Google (Gmail) via Auth0 Vercel Marketplace */}
            <button
              type="button"
              onClick={handleGoogleButtonClick}
              style={{
                width: '100%',
                padding: '11px 16px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: '#ffffff',
                color: '#111827',
                fontWeight: 600,
                fontSize: '0.9375rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px',
                marginBottom: '12px',
              }}
            >
              <GoogleLogoSvg />
              <span>Continuar com Google (Gmail)</span>
            </button>

            {isAuth0Configured && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => loginWithAuth0Redirect(tab)}
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  padding: '9px 14px',
                  marginBottom: '12px',
                }}
              >
                <Lock size={14} aria-hidden="true" />
                <span>
                  {tab === 'signup' ? 'Cadastrar via Auth0 Universal Login' : 'Entrar via Auth0 Universal Login'}
                </span>
              </button>
            )}

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                margin: '16px 0',
                color: 'var(--text-muted)',
                fontSize: '0.75rem',
                textTransform: 'uppercase',
              }}
            >
              <div style={{ flex: 1, height: 1, backgroundColor: 'var(--border-subtle)' }} />
              <span>ou use seu e-mail empresarial</span>
              <div style={{ flex: 1, height: 1, backgroundColor: 'var(--border-subtle)' }} />
            </div>

            {/* Alerta de Erro */}
            {authError && (
              <div
                role="alert"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--status-danger-bg)',
                  border: '1px solid var(--status-danger-border)',
                  color: 'var(--status-danger-text)',
                  fontSize: '0.8125rem',
                  marginBottom: '16px',
                }}
              >
                <AlertCircle size={16} style={{ flexShrink: 0 }} aria-hidden="true" />
                <span>{authError}</span>
              </div>
            )}

            {/* Formulário Padrão de Login / Criar Conta */}
            <form onSubmit={handleEmailSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {tab === 'signup' && (
                <>
                  <div>
                    <label htmlFor="auth-name-input" style={labelStyle}>
                      Seu Nome Completo *
                    </label>
                    <input
                      id="auth-name-input"
                      type="text"
                      required
                      placeholder="Ex: Leandro Elias"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      style={inputStyle}
                    />
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    <div>
                      <label htmlFor="auth-company-input" style={labelStyle}>
                        Razão Social / Empresa
                      </label>
                      <input
                        id="auth-company-input"
                        type="text"
                        placeholder="Indústria Brasil S.A."
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <label htmlFor="auth-cnpj-input" style={labelStyle}>
                        CNPJ Cedente
                      </label>
                      <input
                        id="auth-cnpj-input"
                        type="text"
                        placeholder="11.222.333/0001-81"
                        value={cnpj}
                        onChange={(e) => setCnpj(e.target.value)}
                        style={inputStyle}
                      />
                    </div>
                  </div>
                </>
              )}

              <div>
                <label htmlFor="auth-email-input" style={labelStyle}>
                  E-mail *
                </label>
                <input
                  id="auth-email-input"
                  type="email"
                  required
                  placeholder="voce@suaempresa.com.br"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={inputStyle}
                />
              </div>

              <div>
                <label htmlFor="auth-password-input" style={labelStyle}>
                  Senha *
                </label>
                <input
                  id="auth-password-input"
                  type="password"
                  required
                  minLength={6}
                  placeholder="Mínimo de 6 caracteres"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={inputStyle}
                />
              </div>

              <button
                type="submit"
                className="btn-primary"
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  padding: '11px 16px',
                  marginTop: '6px',
                  fontSize: '0.9375rem',
                }}
              >
                <Mail size={16} aria-hidden="true" />
                <span>{tab === 'signup' ? 'Criar Conta e Acessar Plataforma' : 'Entrar no Portal Antecipe'}</span>
              </button>
            </form>
          </div>

          <div
            style={{
              marginTop: '20px',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              textAlign: 'center',
            }}
          >
            Integração compatível com Vercel Marketplace Auth0 (OAuth 2.0 PKCE + Web Crypto SHA-256).
          </div>
        </section>
      </div>
    </div>
  );
};

