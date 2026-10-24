import React, { createContext, useContext, useEffect, useState } from 'react';

export type AuthProviderType = 'google' | 'email' | 'auth0' | 'demo';

export interface EntrepreneurUser {
  id: string;
  name: string;
  email: string;
  companyName: string;
  cnpj: string;
  provider: AuthProviderType;
  pictureUrl?: string;
  authenticatedAt: string;
}

export interface AuthContextValue {
  user: EntrepreneurUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAuth0Configured: boolean;
  auth0Domain: string | null;
  authError: string | null;
  clearError: () => void;
  loginWithGoogle: () => Promise<void>;
  loginWithEmail: (params: {
    mode: 'login' | 'signup';
    email: string;
    password: string;
    name?: string;
    companyName?: string;
    cnpj?: string;
  }) => Promise<void>;
  loginWithAuth0Redirect: (screenHint?: 'login' | 'signup', connection?: string) => Promise<void>;
  loginAsDemoEntrepreneur: () => void;
  saveRuntimeAuth0Config: (domain: string, clientId: string) => void;
  logout: () => void;
}

export const SESSION_STORAGE_KEY = 'antecipe_entrepreneur_session_v1';
export const ACCOUNTS_STORAGE_KEY = 'antecipe_entrepreneur_accounts_v1';
export const PKCE_VERIFIER_KEY = 'antecipe_auth0_pkce_verifier';
export const AUTH0_CONFIG_STORAGE_KEY = 'antecipe_auth0_config_v1';

interface StoredAccountMetadata {
  id: string;
  name: string;
  email: string;
  companyName: string;
  cnpj: string;
  passwordDigest: string;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Resolve credenciais públicas da integração Vercel Marketplace Auth0
 * (https://vercel.com/marketplace/auth0) suportando variáveis VITE_*, NEXT_PUBLIC_*
 * ou configuração salva no localStorage durante os testes.
 */
export function resolveAuth0Config(): { domain: string; clientId: string } | null {
  const env = (import.meta as unknown as { env?: Record<string, string | undefined> }).env || {};
  let rawDomain =
    env.VITE_AUTH0_DOMAIN ||
    env.NEXT_PUBLIC_AUTH0_DOMAIN ||
    env.VITE_AUTH0_ISSUER_BASE_URL ||
    env.NEXT_PUBLIC_AUTH0_ISSUER_BASE_URL ||
    '';
  let rawClientId = env.VITE_AUTH0_CLIENT_ID || env.NEXT_PUBLIC_AUTH0_CLIENT_ID || '';

  if ((!rawDomain || !rawClientId) && typeof window !== 'undefined') {
    try {
      const saved = window.localStorage.getItem(AUTH0_CONFIG_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as { domain?: string; clientId?: string };
        rawDomain = rawDomain || parsed.domain || '';
        rawClientId = rawClientId || parsed.clientId || '';
      }
    } catch {
      // Ignora erro de leitura
    }
  }

  const domain = rawDomain.trim().replace(/^https?:\/\//, '').replace(/\/$/, '');
  const clientId = rawClientId.trim();

  if (domain && clientId) {
    return { domain, clientId };
  }
  return null;
}

function base64UrlEncode(buffer: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < buffer.byteLength; i += 1) {
    binary += String.fromCharCode(buffer[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function sha256Hex(input: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const hashBuffer = await window.crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

async function generatePkcePair(): Promise<{ verifier: string; challenge: string }> {
  const randomBytes = new Uint8Array(32);
  window.crypto.getRandomValues(randomBytes);
  const verifier = base64UrlEncode(randomBytes);
  const encoder = new TextEncoder();
  const digest = await window.crypto.subtle.digest('SHA-256', encoder.encode(verifier));
  const challenge = base64UrlEncode(new Uint8Array(digest));
  return { verifier, challenge };
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<EntrepreneurUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [auth0Config, setAuth0Config] = useState<{ domain: string; clientId: string } | null>(() =>
    resolveAuth0Config()
  );

  const isAuth0Configured = auth0Config !== null;

  const saveSession = (nextUser: EntrepreneurUser) => {
    setUser(nextUser);
    try {
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(nextUser));
    } catch {
      // Ignora erro caso sessionStorage esteja indisponível
    }
  };

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        let currentConfig = resolveAuth0Config();

        // Se estiver rodando na Vercel com o backend FastAPI e variáveis AUTH0_*, descobre via /api/auth/config
        if (!currentConfig) {
          try {
            const cfgRes = await fetch('/api/auth/config');
            if (cfgRes.ok) {
              const serverCfg = (await cfgRes.json()) as {
                configured?: boolean;
                domain?: string | null;
                clientId?: string | null;
              };
              if (serverCfg.configured && serverCfg.domain && serverCfg.clientId) {
                currentConfig = { domain: serverCfg.domain, clientId: serverCfg.clientId };
              }
            }
          } catch {
            // Sem rota de backend ativa no momento
          }
        }

        setAuth0Config(currentConfig);

        const params = new URLSearchParams(window.location.search);
        const code = params.get('code');
        const errorParam = params.get('error_description') || params.get('error');

        if (errorParam) {
          setAuthError(`Autenticação recusada pelo provedor: ${errorParam}`);
          window.history.replaceState({}, document.title, window.location.pathname);
        } else if (code && currentConfig) {
          const verifier = window.sessionStorage.getItem(PKCE_VERIFIER_KEY);
          window.sessionStorage.removeItem(PKCE_VERIFIER_KEY);
          const cleanRedirectUri =
            window.sessionStorage.getItem('antecipe_auth0_last_redirect_uri') ||
            window.location.origin + '/auth/callback';
          window.history.replaceState({}, document.title, window.location.pathname);

          // 1. Tenta trocar o código via endpoint de servidor (/api/auth/exchange) caso instalado via Vercel Marketplace
          try {
            const exchangeRes = await fetch('/api/auth/exchange', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                code,
                redirect_uri: cleanRedirectUri,
                code_verifier: verifier || undefined,
              }),
            });
            if (exchangeRes.ok) {
              const profile = (await exchangeRes.json()) as {
                id?: string;
                name?: string;
                email?: string;
                pictureUrl?: string;
                provider?: 'google' | 'auth0';
              };
              saveSession({
                id: profile.id || `auth0-${Date.now()}`,
                name: profile.name || 'Empresário Cedente',
                email: profile.email || 'cedente@empresa.com.br',
                companyName: 'Indústria Brasil S.A.',
                cnpj: '11.222.333/0001-81',
                provider: profile.provider || 'google',
                pictureUrl: profile.pictureUrl,
                authenticatedAt: new Date().toISOString(),
              });
              setIsLoading(false);
              return;
            }
          } catch {
            // Se não houver backend ativo, prossegue com troca PKCE direta no navegador
          }

          // 2. Fallback: Troca direta OAuth2 PKCE no navegador
          if (verifier) {
            const tokenRes = await fetch(`https://${currentConfig.domain}/oauth/token`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                grant_type: 'authorization_code',
                client_id: currentConfig.clientId,
                code_verifier: verifier,
                code,
                redirect_uri: cleanRedirectUri,
              }),
            });

            if (tokenRes.ok) {
              const tokenData = (await tokenRes.json()) as { access_token?: string };
              if (tokenData.access_token) {
                const userRes = await fetch(`https://${currentConfig.domain}/userinfo`, {
                  headers: { Authorization: `Bearer ${tokenData.access_token}` },
                });
                if (userRes.ok) {
                  const profile = (await userRes.json()) as {
                    sub?: string;
                    name?: string;
                    email?: string;
                    picture?: string;
                  };
                  const loggedUser: EntrepreneurUser = {
                    id: profile.sub || `auth0-${Date.now()}`,
                    name: profile.name || profile.email || 'Empresário Cedente',
                    email: profile.email || 'cedente@empresa.com.br',
                    companyName: 'Indústria Brasil S.A.',
                    cnpj: '11.222.333/0001-81',
                    provider: profile.sub?.includes('google') ? 'google' : 'auth0',
                    pictureUrl: profile.picture,
                    authenticatedAt: new Date().toISOString(),
                  };
                  saveSession(loggedUser);
                  setIsLoading(false);
                  return;
                }
              }
            }
            setAuthError('Não foi possível validar o código OAuth2 com o Auth0. Confira a Callback URL.');
          }
        }

        const rawSession = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
        if (rawSession) {
          const parsed = JSON.parse(rawSession) as EntrepreneurUser;
          if (parsed && parsed.email && parsed.name) {
            setUser(parsed);
          }
        }
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    void initializeAuth();
  }, []);

  const clearError = () => setAuthError(null);

  const saveRuntimeAuth0Config = (domain: string, clientId: string) => {
    const cleanDomain = domain.trim().replace(/^https?:\/\//, '').replace(/\/$/, '');
    const cleanClientId = clientId.trim();
    if (!cleanDomain || !cleanClientId) {
      setAuthError('Informe o Domain e o Client ID do Auth0.');
      return;
    }
    try {
      window.localStorage.setItem(
        AUTH0_CONFIG_STORAGE_KEY,
        JSON.stringify({ domain: cleanDomain, clientId: cleanClientId })
      );
    } catch {
      // Ignora erro de escrita
    }
    setAuth0Config({ domain: cleanDomain, clientId: cleanClientId });
    setAuthError(null);
  };

  const loginWithAuth0Redirect = async (
    screenHint: 'login' | 'signup' = 'login',
    connection?: string
  ) => {
    setAuthError(null);
    const activeConfig = resolveAuth0Config();
    if (!activeConfig) {
      setAuthError(
        'Configuração do Auth0 ausente. Defina VITE_AUTH0_DOMAIN e VITE_AUTH0_CLIENT_ID na Vercel (https://vercel.com/marketplace/auth0).'
      );
      return;
    }

    const { verifier, challenge } = await generatePkcePair();
    window.sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);

    const redirectUri = window.location.origin + '/auth/callback';
    window.sessionStorage.setItem('antecipe_auth0_last_redirect_uri', redirectUri);
    const authorizeUrl = new URL(`https://${activeConfig.domain}/authorize`);
    authorizeUrl.searchParams.set('response_type', 'code');
    authorizeUrl.searchParams.set('client_id', activeConfig.clientId);
    authorizeUrl.searchParams.set('redirect_uri', redirectUri);
    authorizeUrl.searchParams.set('scope', 'openid profile email');
    authorizeUrl.searchParams.set('code_challenge', challenge);
    authorizeUrl.searchParams.set('code_challenge_method', 'S256');
    if (screenHint === 'signup') {
      authorizeUrl.searchParams.set('screen_hint', 'signup');
    }
    if (connection) {
      authorizeUrl.searchParams.set('connection', connection);
    }

    window.location.assign(authorizeUrl.toString());
  };

  const loginWithGoogle = async () => {
    setAuthError(null);
    await loginWithAuth0Redirect('login', 'google-oauth2');
  };

  const loginWithEmail = async (params: {
    mode: 'login' | 'signup';
    email: string;
    password: string;
    name?: string;
    companyName?: string;
    cnpj?: string;
  }) => {
    setAuthError(null);
    const cleanEmail = params.email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setAuthError('Por favor, informe um e-mail válido.');
      return;
    }
    if (!params.password || params.password.length < 6) {
      setAuthError('A senha deve possuir no mínimo 6 caracteres.');
      return;
    }

    const passwordDigest = await sha256Hex(`${cleanEmail}::${params.password}`);
    let accounts: StoredAccountMetadata[] = [];
    try {
      const raw = window.localStorage.getItem(ACCOUNTS_STORAGE_KEY);
      if (raw) {
        accounts = JSON.parse(raw) as StoredAccountMetadata[];
      }
    } catch {
      accounts = [];
    }

    const existing = accounts.find((acc) => acc.email === cleanEmail);

    if (params.mode === 'signup') {
      if (existing) {
        setAuthError('Já existe uma conta cadastrada com este e-mail. Use a aba "Entrar na Conta".');
        return;
      }
      const cleanName = (params.name || '').trim();
      if (!cleanName) {
        setAuthError('Informe o seu nome completo para criar a conta.');
        return;
      }
      const newAccount: StoredAccountMetadata = {
        id: `usr-${Date.now()}`,
        name: cleanName,
        email: cleanEmail,
        companyName: (params.companyName || 'Indústria Brasil S.A.').trim(),
        cnpj: (params.cnpj || '11.222.333/0001-81').trim(),
        passwordDigest,
      };
      accounts.push(newAccount);
      try {
        window.localStorage.setItem(ACCOUNTS_STORAGE_KEY, JSON.stringify(accounts));
      } catch {
        // Ignora erro de quota
      }

      saveSession({
        id: newAccount.id,
        name: newAccount.name,
        email: newAccount.email,
        companyName: newAccount.companyName,
        cnpj: newAccount.cnpj,
        provider: 'email',
        authenticatedAt: new Date().toISOString(),
      });
      return;
    }

    if (!existing) {
      setAuthError('Conta não encontrada para este e-mail. Use a aba "Criar Conta" para se cadastrar primeiro.');
      return;
    }

    if (existing.passwordDigest !== passwordDigest) {
      setAuthError('Credenciais inválidas. Verifique o e-mail e a senha informados.');
      return;
    }

    saveSession({
      id: existing.id,
      name: existing.name,
      email: existing.email,
      companyName: existing.companyName,
      cnpj: existing.cnpj,
      provider: 'email',
      authenticatedAt: new Date().toISOString(),
    });
  };

  const loginAsDemoEntrepreneur = () => {
    setAuthError(null);
    saveSession({
      id: 'demo-cedente-01',
      name: 'Empresário Cedente (Demo)',
      email: 'financeiro@industriabrasil.com.br',
      companyName: 'Indústria Brasil S.A.',
      cnpj: '11.222.333/0001-81',
      provider: 'demo',
      authenticatedAt: new Date().toISOString(),
    });
  };

  const logout = () => {
    const previousProvider = user?.provider;
    setUser(null);
    setAuthError(null);
    try {
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // Ignora erro de storage
    }

    const activeConfig = resolveAuth0Config();
    if (activeConfig && (previousProvider === 'auth0' || previousProvider === 'google')) {
      const logoutUrl = new URL(`https://${activeConfig.domain}/v2/logout`);
      logoutUrl.searchParams.set('client_id', activeConfig.clientId);
      logoutUrl.searchParams.set('returnTo', window.location.origin + window.location.pathname);
      window.location.assign(logoutUrl.toString());
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        isAuth0Configured,
        auth0Domain: auth0Config?.domain || null,
        authError,
        clearError,
        loginWithGoogle,
        loginWithEmail,
        loginWithAuth0Redirect,
        loginAsDemoEntrepreneur,
        saveRuntimeAuth0Config,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth deve ser utilizado dentro de um <AuthProvider>.');
  }
  return ctx;
}

