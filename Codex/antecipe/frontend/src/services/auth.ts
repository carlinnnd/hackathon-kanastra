import type { AuthUser } from '../types';

const TRANSACTION = 'antecipe_auth0_transaction_v2';
type Config = { configured: boolean; domain: string | null; clientId: string | null };

async function json<T>(response: Response): Promise<T> {
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail?.mensagem || 'Não foi possível concluir a autenticação.');
  return body as T;
}

function base64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
}

export async function beginGoogleLogin(): Promise<void> {
  const cfg = await json<Config>(await fetch('/api/auth/config', { cache: 'no-store' }));
  if (!cfg.configured || !cfg.domain || !cfg.clientId) throw new Error('Auth0 não configurado no servidor.');
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const state = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
  const redirectUri = `${location.origin}/auth/callback`;
  sessionStorage.setItem(TRANSACTION, JSON.stringify({ verifier, state, redirectUri, createdAt: Date.now() }));
  const url = new URL(`https://${cfg.domain}/authorize`);
  for (const [key, value] of Object.entries({ response_type: 'code', client_id: cfg.clientId,
    redirect_uri: redirectUri, scope: 'openid profile email', connection: 'google-oauth2',
    state, code_challenge: challenge, code_challenge_method: 'S256' })) url.searchParams.set(key, value);
  location.assign(url.toString());
}

let initialization: Promise<AuthUser | null> | null = null;
export function restoreAuthSession(): Promise<AuthUser | null> {
  if (initialization) return initialization;
  initialization = (async () => {
    const params = new URLSearchParams(location.search);
    if (params.has('code') || params.has('error')) {
      const saved = sessionStorage.getItem(TRANSACTION);
      sessionStorage.removeItem(TRANSACTION);
      history.replaceState({}, '', '/');
      if (!saved) throw new Error('Sessão de login ausente. Reinicie a autenticação.');
      const tx = JSON.parse(saved);
      if (params.get('state') !== tx.state || Date.now() - tx.createdAt > 600_000 || tx.redirectUri !== `${location.origin}/auth/callback`) {
        throw new Error('Sessão de login inválida ou expirada. Reinicie a autenticação.');
      }
      if (params.has('error')) throw new Error('Login cancelado ou recusado pelo Auth0.');
      const result = await json<{ user: AuthUser }>(await fetch('/api/auth/exchange', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: params.get('code'), code_verifier: tx.verifier, redirect_uri: tx.redirectUri }),
      }));
      return result.user;
    }
    const response = await fetch('/api/auth/session', { cache: 'no-store' });
    return response.status === 401 ? null : json<AuthUser>(response);
  })();
  return initialization;
}

export async function endAuthSession(): Promise<void> {
  await json(await fetch('/api/auth/logout', { method: 'POST' }));
  initialization = null;
  sessionStorage.removeItem(TRANSACTION);
  localStorage.removeItem('kanastra_antecipe_auth_session_v1');
  sessionStorage.removeItem('antecipe_entrepreneur_session_v1');
}
