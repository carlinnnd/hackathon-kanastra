import React, { useEffect, useState } from 'react';
import {
  Lock,
  Mail,
  Eye,
  EyeOff,
  ArrowRight,
  Building2,
  AlertCircle,
  User,
} from 'lucide-react';
import { KanastraLogo } from './KanastraLogo';
import { api } from '../services/api';
import { AuthUser } from '../types';

interface LoginPageProps {
  onLoginSuccess: (user: AuthUser) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [name, setName] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [cargoSelect, setCargoSelect] = useState<string>('Analista de Risco FIDC');
  const [cargoOutro, setCargoOutro] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [auth0Config, setAuth0Config] = useState<{
    configured: boolean;
    domain: string | null;
    clientId: string | null;
  }>({ configured: false, domain: null, clientId: null });

  useEffect(() => {
    let active = true;
    api.restoreAuthSession().then(user => { if (active && user) onLoginSuccess(user); }).catch(error => { if (active) setErrorMsg(error.message); });
    fetch('/api/auth/config')
      .then((res) => (res.ok ? res.json() : null))
      .then((cfg) => {
        if (active && cfg && cfg.configured) {
          setAuth0Config({
            configured: true,
            domain: cfg.domain,
            clientId: cfg.clientId,
          });
        }
      })
      .catch(() => {
        // Auth0 opcional
      });
    return () => {
      active = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsSubmitting(true);
    const cargoFinal =
      cargoSelect === 'Outros'
        ? cargoOutro.trim() || 'Outros'
        : cargoSelect;

    try {
      const user = await api.login({
        email,
        password,
        cargo: cargoFinal,
        name: mode === 'signup' ? name.trim() : undefined,
        mode,
      });
      onLoginSuccess(user);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg('Não foi possível autenticar. Verifique seu e-mail e senha.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleAuth0Redirect = async () => {
    try { await api.beginGoogleLogin(); }
    catch (error) { setErrorMsg(error instanceof Error ? error.message : 'Não foi possível iniciar o login.'); }
  };

  return (
    <div className="kanastra-login-wrapper">
      <div className="kanastra-login-grid">
        {/* Painel Institucional (Esquerda) */}
        <section
          className="kanastra-login-hero"
          aria-labelledby="kanastra-hero-heading"
        >
          <div>
            <KanastraLogo size={32} subtitle="Backoffice FIDC" />

            <h1 id="kanastra-hero-heading" className="kanastra-hero-title">
              Tecnologia para gestão, enquadramento e aquisição de recebíveis em escala.
            </h1>

            <p className="kanastra-hero-description">
              Ambiente operacional do <strong>ANTECIPE FIDC</strong> para validação regulatória de
              remessas, controle de exposição por grupo econômico, antiduplicidade e cálculo de
              desembolso líquido.
            </p>

            <div className="kanastra-hero-list">
              <div className="kanastra-hero-list-item">
                <strong>Motor de Elegibilidade Regulatória</strong>
                <span>
                  Validação determinística de prazo de vencimento, piso nominal, modalidade de
                  título, situação cadastral e concentração por raiz de CNPJ.
                </span>
              </div>

              <div className="kanastra-hero-list-item">
                <strong>Consolidação Societária por Grupo Econômico</strong>
                <span>
                  Inspeção integrada de exposição entre matriz e filiais frente à carteira ativa do
                  fundo.
                </span>
              </div>

              <div className="kanastra-hero-list-item">
                <strong>Simulação de Política e Precificação</strong>
                <span>
                  Desconto comercial exato em Decimal de precisão arbitrária.
                </span>
              </div>
            </div>
          </div>

          <div className="kanastra-hero-footer">
            <span>ANTECIPE FIDC • CNPJ 92.234.400/0001-80</span>
            <span>Kanastra Backoffice</span>
          </div>
        </section>

        {/* Formulário de Autenticação (Direita) */}
        <section
          className="kanastra-login-card"
          aria-labelledby="kanastra-login-title"
        >
          <div className="kanastra-login-card-header">
            <h2 id="kanastra-login-title">
              {mode === 'login' ? 'Acesse sua conta' : 'Criar conta de acesso'}
            </h2>
            <p>Informe seu e-mail e senha para acessar o ambiente operacional.</p>
          </div>

          <div className="kanastra-auth-mode-tabs" role="tablist" aria-label="Modo de acesso">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'login'}
              className={`kanastra-auth-mode-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => {
                setMode('login');
                setErrorMsg(null);
              }}
            >
              Entrar
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'signup'}
              className={`kanastra-auth-mode-tab ${mode === 'signup' ? 'active' : ''}`}
              onClick={() => {
                setMode('signup');
                setErrorMsg(null);
              }}
            >
              Criar Conta
            </button>
          </div>

          {errorMsg && (
            <div className="error-toast" role="alert" style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={18} aria-hidden="true" />
                <span>{errorMsg}</span>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="kanastra-login-form">
            {mode === 'signup' && (
              <div className="kanastra-field-group">
                <label htmlFor="login-name">Nome ou Razão Social</label>
                <div className="kanastra-input-wrapper">
                  <User size={16} className="kanastra-input-icon" aria-hidden="true" />
                  <input
                    id="login-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Seu nome completo"
                    required
                    autoComplete="name"
                  />
                </div>
              </div>
            )}

            <div className="kanastra-field-group">
              <label htmlFor="login-email">E-mail</label>
              <div className="kanastra-input-wrapper">
                <Mail size={16} className="kanastra-input-icon" aria-hidden="true" />
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="seu@email.com"
                  required
                  autoComplete="email"
                />
              </div>
            </div>

            <div className="kanastra-field-group">
              <label htmlFor="login-password">Senha</label>
              <div className="kanastra-input-wrapper">
                <Lock size={16} className="kanastra-input-icon" aria-hidden="true" />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
                <button
                  type="button"
                  className="kanastra-password-toggle"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="kanastra-field-group">
              <label htmlFor="login-role">Perfil na operação</label>
              <div className="kanastra-input-wrapper">
                <Building2 size={16} className="kanastra-input-icon" aria-hidden="true" />
                <select
                  id="login-role"
                  value={cargoSelect}
                  onChange={(e) => setCargoSelect(e.target.value)}
                >
                  <option value="Analista de Risco FIDC">Analista de Risco FIDC</option>
                  <option value="Gestor de Portfólio">Gestor de Portfólio</option>
                  <option value="Compliance e Auditoria">Compliance e Auditoria</option>
                  <option value="Operações e Backoffice">Operações e Backoffice</option>
                  <option value="Empresário Cedente">Empresário Cedente</option>
                  <option value="Outros">Outros</option>
                </select>
              </div>
            </div>

            {cargoSelect === 'Outros' && (
              <div className="kanastra-field-group">
                <label htmlFor="login-role-custom">Especifique a função (opcional)</label>
                <div className="kanastra-input-wrapper">
                  <input
                    id="login-role-custom"
                    type="text"
                    value={cargoOutro}
                    onChange={(e) => setCargoOutro(e.target.value)}
                    placeholder="Ex.: Consultor Externo, Jurídico, Custodiante..."
                    style={{ paddingLeft: '14px' }}
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              className="btn-primary kanastra-submit-btn"
              disabled={isSubmitting}
            >
              <span>
                {isSubmitting
                  ? 'Autenticando...'
                  : mode === 'login'
                  ? 'Entrar'
                  : 'Criar Conta e Entrar'}
              </span>
              <ArrowRight size={16} aria-hidden="true" />
            </button>

            {auth0Config.configured && (
              <button
                type="button"
                className="btn-secondary"
                onClick={handleGoogleAuth0Redirect}
                style={{ width: '100%', justifyContent: 'center', marginTop: '4px' }}
              >
                Continuar com Google (Auth0 SSO)
              </button>
            )}
          </form>
        </section>
      </div>
    </div>
  );
};
