/**
 * Antecipe FIDC — Portal do Empresário (Auth Gate & Header Session Badge)
 * Integra autenticação OAuth 2.0 PKCE (Google via Vercel Marketplace Auth0),
 * Cadastro/Login de E-mail com hash SHA-256 e Acesso Rápido Demo diretamente
 * na aplicação principal da Vercel.
 */
(function () {
  const SESSION_STORAGE_KEY = 'antecipe_entrepreneur_session_v1';
  const ACCOUNTS_STORAGE_KEY = 'antecipe_entrepreneur_accounts_v1';
  const PKCE_VERIFIER_KEY = 'antecipe_auth0_pkce_verifier';
  const AUTH0_CONFIG_STORAGE_KEY = 'antecipe_auth0_config_v1';

  let currentTab = 'login';
  let serverAuth0Config = null;
  let showManualConfig = false;

  function getAuth0Config() {
    try {
      const raw = window.localStorage.getItem(AUTH0_CONFIG_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        const domain = (parsed.domain || '').trim().replace(/^https?:\/\//, '').replace(/\/$/, '');
        const clientId = (parsed.clientId || '').trim();
        if (domain && clientId) {
          return { domain, clientId, useServerExchange: Boolean(parsed.useServerExchange) };
        }
      }
    } catch (e) {}
    if (serverAuth0Config && serverAuth0Config.domain && serverAuth0Config.clientId) {
      return serverAuth0Config;
    }
    return null;
  }

  function base64UrlEncode(buffer) {
    let binary = '';
    for (let i = 0; i < buffer.byteLength; i += 1) {
      binary += String.fromCharCode(buffer[i]);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  async function sha256Hex(input) {
    const encoder = new TextEncoder();
    const data = encoder.encode(input);
    const hashBuffer = await window.crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(hashBuffer))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  }

  async function generatePkcePair() {
    const randomBytes = new Uint8Array(32);
    window.crypto.getRandomValues(randomBytes);
    const verifier = base64UrlEncode(randomBytes);
    const encoder = new TextEncoder();
    const digest = await window.crypto.subtle.digest('SHA-256', encoder.encode(verifier));
    const challenge = base64UrlEncode(new Uint8Array(digest));
    return { verifier, challenge };
  }

  function getLoggedUser() {
    try {
      const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function saveSession(userObj) {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(userObj));
    syncView();
  }

  function logout() {
    const user = getLoggedUser();
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    syncView();

    try {
      const cfg = getAuth0Config();
      if (user && (user.provider === 'auth0' || user.provider === 'google') && cfg) {
        const logoutUrl = new URL('https://' + cfg.domain + '/v2/logout');
        logoutUrl.searchParams.set('client_id', cfg.clientId);
        logoutUrl.searchParams.set('returnTo', window.location.origin + '/');
        window.location.assign(logoutUrl.toString());
      }
    } catch (e) {}
  }

  function showFeedback(msg, isSuccess) {
    const banner = document.getElementById('ag-feedback-banner');
    const text = document.getElementById('ag-feedback-text');
    if (!banner || !text) return;
    text.textContent = msg;
    banner.style.display = 'flex';
    banner.style.backgroundColor = isSuccess ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)';
    banner.style.borderColor = isSuccess ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)';
    banner.style.color = isSuccess ? '#34d399' : '#f87171';
  }

  function hideFeedback() {
    const banner = document.getElementById('ag-feedback-banner');
    if (banner) banner.style.display = 'none';
  }

  async function startAuth0Redirect(screenHint, connection) {
    const cfg = getAuth0Config();
    if (!cfg) {
      showManualConfig = true;
      const box = document.getElementById('ag-manual-auth0-box');
      if (box) box.style.display = 'block';
      showFeedback(
        'Para entrar com Google, conecte o projeto no painel Auth0 da Vercel ("Connect to Project") ou cole abaixo o AUTH0_DOMAIN e AUTH0_CLIENT_ID do seu client-antecipe.'
      );
      const input = document.getElementById('ag-cfg-domain');
      if (input) input.focus();
      return;
    }

    const { verifier, challenge } = await generatePkcePair();
    window.sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);

    const returnUrl = window.location.origin + '/auth/callback';
    window.sessionStorage.setItem('antecipe_auth0_last_redirect_uri', returnUrl);
    const url = new URL('https://' + cfg.domain + '/authorize');
    url.searchParams.set('response_type', 'code');
    url.searchParams.set('client_id', cfg.clientId);
    url.searchParams.set('redirect_uri', returnUrl);
    url.searchParams.set('scope', 'openid profile email');
    url.searchParams.set('code_challenge', challenge);
    url.searchParams.set('code_challenge_method', 'S256');
    if (screenHint === 'signup') url.searchParams.set('screen_hint', 'signup');
    if (connection) url.searchParams.set('connection', connection);

    window.location.assign(url.toString());
  }

  function ensureAuthGateDom() {
    if (document.getElementById('antecipe-auth-gate-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'antecipe-auth-gate-overlay';
    overlay.innerHTML = `
      <div style="max-width: 1120px; margin: 0 auto; padding: 32px 24px;">
        <header style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;padding-bottom:24px;margin-bottom:28px;border-bottom:1px solid #1e293b">
          <div>
            <h1 style="font-size:1.5rem;font-weight:700;color:#f8fafc;display:flex;align-items:center;gap:12px;margin:0">
              <span>Antecipe</span>
              <span style="font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;padding:4px 10px;border-radius:9999px;background:rgba(59,130,246,0.12);color:#60a5fa;border:1px solid rgba(59,130,246,0.3)">Portal do Empresário • FIDC</span>
            </h1>
            <p style="color:#94a3b8;font-size:0.875rem;margin:6px 0 0">
              Identifique sua empresa para simular e antecipar notas fiscais e duplicatas com o motor de elegibilidade.
            </p>
          </div>
          <div style="display:flex;align-items:center;gap:10px">
            <span id="ag-auth0-status-pill" style="font-size:0.75rem;font-family:monospace;padding:4px 10px;border-radius:9999px;background:#111827;border:1px solid #1e293b;color:#94a3b8">
              Verificando Auth0...
            </span>
          </div>
        </header>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:28px;align-items:start">
          <!-- Coluna Esquerda: Benefícios ao Cedente -->
          <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:28px;display:flex;flex-direction:column;gap:20px">
            <div>
              <span style="font-size:0.75rem;font-family:monospace;padding:4px 8px;border-radius:4px;background:rgba(59,130,246,0.12);color:#60a5fa;border:1px solid rgba(59,130,246,0.3)">
                ANTECIPAÇÃO DE RECEBÍVEIS B2B
              </span>
              <h2 style="font-size:1.35rem;font-weight:700;color:#f8fafc;margin:12px 0 8px">
                Transforme suas vendas a prazo em caixa imediato
              </h2>
              <p style="font-size:0.875rem;color:#94a3b8;line-height:1.6;margin:0">
                Envie sua planilha CSV de duplicatas e receba na hora o diagnóstico completo das regras do FIDC Antecipe, limites de concentração por CNPJ sacado e valor líquido aprovado.
              </p>
            </div>

            <div style="display:flex;flex-direction:column;gap:12px">
              <div style="padding:14px;background:#1a2234;border-radius:8px;border:1px solid #1e293b">
                <strong style="display:block;font-size:0.85rem;color:#f8fafc;margin-bottom:4px">
                  ✓ Login Oficial Google (Auth0 Vercel) ou Conta Própria
                </strong>
                <span style="font-size:0.78rem;color:#94a3b8">
                  Entre com sua conta Google corporativa, crie sua conta com senha protegida por hash SHA-256 ou use o perfil de demonstração em 1 clique.
                </span>
              </div>
              <div style="padding:14px;background:#1a2234;border-radius:8px;border:1px solid #1e293b">
                <strong style="display:block;font-size:0.85rem;color:#f8fafc;margin-bottom:4px">
                  ✓ Motor Completo: Novas Operações & Estoque Histórico
                </strong>
                <span style="font-size:0.78rem;color:#94a3b8">
                  Após autenticar, acesse imediatamente o simulador de lotes CSV, análise de carteira de 100k títulos e exportação de relatórios.
                </span>
              </div>
            </div>
          </div>

          <!-- Coluna Direita: Card de Login / Cadastro -->
          <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:28px">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;background:#1a2234;padding:4px;border-radius:8px;margin-bottom:20px;border:1px solid #1e293b">
              <button id="ag-tab-login" type="button" style="padding:10px;border:none;border-radius:6px;font-weight:600;font-size:0.85rem;cursor:pointer;background:#3b82f6;color:#fff">
                Entrar na Conta
              </button>
              <button id="ag-tab-signup" type="button" style="padding:10px;border:none;border-radius:6px;font-weight:600;font-size:0.85rem;cursor:pointer;background:transparent;color:#94a3b8">
                Criar Conta
              </button>
            </div>

            <div id="ag-feedback-banner" style="display:none;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;border-radius:8px;border:1px solid transparent;margin-bottom:16px;font-size:0.8125rem">
              <span id="ag-feedback-text"></span>
              <button id="ag-feedback-close" type="button" style="background:transparent;border:1px solid currentColor;color:inherit;border-radius:4px;padding:2px 8px;font-size:0.72rem;cursor:pointer">Fechar</button>
            </div>

            <!-- Botão Oficial Google (Gmail) -->
            <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:18px">
              <button id="ag-btn-google" type="button" style="width:100%;padding:11px 16px;border-radius:8px;border:1px solid #334155;background:#fff;color:#0f172a;font-weight:600;font-size:0.875rem;display:flex;align-items:center;justify-content:center;gap:10px;cursor:pointer">
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                  <path fill="#4285F4" d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"/>
                  <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"/>
                  <path fill="#FBBC05" d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.13-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"/>
                  <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96z"/>
                </svg>
                <span>Continuar com Google (Gmail)</span>
              </button>
            </div>

            <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;color:#64748b;font-size:0.75rem">
              <div style="flex:1;height:1px;background:#1e293b"></div>
              <span>ou acesse com seu e-mail empresarial</span>
              <div style="flex:1;height:1px;background:#1e293b"></div>
            </div>

            <!-- Formulário E-mail e Senha -->
            <form id="ag-email-form" style="display:flex;flex-direction:column;gap:12px">
              <div id="ag-signup-fields" style="display:none;flex-direction:column;gap:12px">
                <div>
                  <label style="display:block;font-size:0.78rem;font-weight:600;color:#94a3b8;margin-bottom:4px" for="ag-name">Seu Nome Completo *</label>
                  <input id="ag-name" type="text" placeholder="Ex.: Leandro Elias" style="width:100%;padding:9px 12px;background:#1a2234;border:1px solid #334155;border-radius:8px;color:#f8fafc;font-size:0.875rem" />
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                  <div>
                    <label style="display:block;font-size:0.78rem;font-weight:600;color:#94a3b8;margin-bottom:4px" for="ag-company">Razão Social / Empresa</label>
                    <input id="ag-company" type="text" placeholder="Indústria Brasil S.A." style="width:100%;padding:9px 12px;background:#1a2234;border:1px solid #334155;border-radius:8px;color:#f8fafc;font-size:0.875rem" />
                  </div>
                  <div>
                    <label style="display:block;font-size:0.78rem;font-weight:600;color:#94a3b8;margin-bottom:4px" for="ag-cnpj">CNPJ Cedente</label>
                    <input id="ag-cnpj" type="text" placeholder="11.222.333/0001-81" style="width:100%;padding:9px 12px;background:#1a2234;border:1px solid #334155;border-radius:8px;color:#f8fafc;font-size:0.875rem" />
                  </div>
                </div>
              </div>

              <div>
                <label style="display:block;font-size:0.78rem;font-weight:600;color:#94a3b8;margin-bottom:4px" for="ag-email">E-mail Corporativo *</label>
                <input id="ag-email" type="email" required placeholder="voce@suaempresa.com.br" style="width:100%;padding:9px 12px;background:#1a2234;border:1px solid #334155;border-radius:8px;color:#f8fafc;font-size:0.875rem" />
              </div>

              <div>
                <label style="display:block;font-size:0.78rem;font-weight:600;color:#94a3b8;margin-bottom:4px" for="ag-password">Senha (mín. 6 caracteres) *</label>
                <input id="ag-password" type="password" required minlength="6" placeholder="••••••••" style="width:100%;padding:9px 12px;background:#1a2234;border:1px solid #334155;border-radius:8px;color:#f8fafc;font-size:0.875rem" />
              </div>

              <button id="ag-btn-submit" type="submit" style="width:100%;margin-top:4px;padding:11px 16px;border-radius:8px;border:none;background:#3b82f6;color:#fff;font-weight:600;font-size:0.875rem;cursor:pointer">
                Entrar no Portal Antecipe
              </button>
            </form>

            <!-- Acesso Rápido Empresário Demo -->
            <div style="margin-top:18px;padding-top:16px;border-top:1px solid #1e293b">
              <button id="ag-btn-demo" type="button" style="width:100%;padding:10px 14px;border-radius:8px;border:1px solid rgba(59,130,246,0.35);background:rgba(59,130,246,0.1);color:#60a5fa;font-weight:600;font-size:0.82rem;cursor:pointer">
                ⚡ Acesso Rápido — Empresário Demo (CNPJ 11.222.333/0001-81)
              </button>
            </div>

            <!-- Painel opcional para colar AUTH0_DOMAIN e AUTH0_CLIENT_ID do client-antecipe -->
            <div style="margin-top:14px;text-align:center">
              <button id="ag-toggle-cfg" type="button" style="background:none;border:none;color:#64748b;font-size:0.75rem;text-decoration:underline;cursor:pointer">
                ⚙️ Configurar chaves Auth0 Vercel (client-antecipe)
              </button>
            </div>

            <div id="ag-manual-auth0-box" style="display:none;margin-top:12px;padding:14px;background:#1a2234;border:1px solid #334155;border-radius:8px">
              <p style="font-size:0.75rem;color:#94a3b8;margin:0 0 10px">
                Cole abaixo o <strong>AUTH0_DOMAIN</strong> e o <strong>AUTH0_CLIENT_ID</strong> da sua integração <code>client-antecipe</code> na Vercel:
              </p>
              <div style="display:flex;flex-direction:column;gap:8px">
                <input id="ag-cfg-domain" type="text" placeholder="AUTH0_DOMAIN (ex: dev-xxx.us.auth0.com)" style="width:100%;padding:8px 10px;background:#111827;border:1px solid #334155;border-radius:6px;color:#f8fafc;font-size:0.8rem" />
                <input id="ag-cfg-client-id" type="text" placeholder="AUTH0_CLIENT_ID" style="width:100%;padding:8px 10px;background:#111827;border:1px solid #334155;border-radius:6px;color:#f8fafc;font-size:0.8rem" />
                <button id="ag-btn-save-cfg" type="button" style="padding:8px 12px;border-radius:6px;border:none;background:#10b981;color:#fff;font-weight:600;font-size:0.8rem;cursor:pointer">
                  Salvar Chaves Auth0
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertBefore(overlay, document.body.firstChild);

    // Eventos das abas e botões
    document.getElementById('ag-tab-login').addEventListener('click', function () {
      currentTab = 'login';
      hideFeedback();
      this.style.background = '#3b82f6';
      this.style.color = '#fff';
      const tabSignup = document.getElementById('ag-tab-signup');
      tabSignup.style.background = 'transparent';
      tabSignup.style.color = '#94a3b8';
      document.getElementById('ag-signup-fields').style.display = 'none';
      document.getElementById('ag-btn-submit').textContent = 'Entrar no Portal Antecipe';
    });

    document.getElementById('ag-tab-signup').addEventListener('click', function () {
      currentTab = 'signup';
      hideFeedback();
      this.style.background = '#3b82f6';
      this.style.color = '#fff';
      const tabLogin = document.getElementById('ag-tab-login');
      tabLogin.style.background = 'transparent';
      tabLogin.style.color = '#94a3b8';
      document.getElementById('ag-signup-fields').style.display = 'flex';
      document.getElementById('ag-btn-submit').textContent = 'Criar Conta e Acessar Plataforma';
    });

    document.getElementById('ag-feedback-close').addEventListener('click', hideFeedback);

    document.getElementById('ag-btn-google').addEventListener('click', function () {
      hideFeedback();
      startAuth0Redirect('login', 'google-oauth2');
    });

    document.getElementById('ag-btn-demo').addEventListener('click', function () {
      hideFeedback();
      saveSession({
        id: 'demo-cedente-01',
        name: 'Empresário Cedente (Demo)',
        email: 'financeiro@industriabrasil.com.br',
        companyName: 'Indústria Brasil S.A.',
        cnpj: '11.222.333/0001-81',
        provider: 'demo',
        authenticatedAt: new Date().toISOString(),
      });
    });

    document.getElementById('ag-toggle-cfg').addEventListener('click', function () {
      const box = document.getElementById('ag-manual-auth0-box');
      showManualConfig = !showManualConfig;
      box.style.display = showManualConfig ? 'block' : 'none';
    });

    document.getElementById('ag-btn-save-cfg').addEventListener('click', function () {
      const domain = document.getElementById('ag-cfg-domain').value.trim().replace(/^https?:\/\//, '').replace(/\/$/, '');
      const clientId = document.getElementById('ag-cfg-client-id').value.trim();
      if (!domain || !clientId) {
        showFeedback('Informe o AUTH0_DOMAIN e o AUTH0_CLIENT_ID.');
        return;
      }
      window.localStorage.setItem(AUTH0_CONFIG_STORAGE_KEY, JSON.stringify({ domain, clientId }));
      syncView();
      showFeedback('Chaves Auth0 salvas! Agora clique em "Continuar com Google (Gmail)".', true);
    });

    document.getElementById('ag-email-form').addEventListener('submit', async function (e) {
      e.preventDefault();
      hideFeedback();
      const email = document.getElementById('ag-email').value.trim().toLowerCase();
      const password = document.getElementById('ag-password').value;
      const name = document.getElementById('ag-name').value.trim();
      const companyName = document.getElementById('ag-company').value.trim() || 'Indústria Brasil S.A.';
      const cnpj = document.getElementById('ag-cnpj').value.trim() || '11.222.333/0001-81';

      const passwordDigest = await sha256Hex(email + '::' + password);
      let accounts = [];
      try {
        accounts = JSON.parse(window.localStorage.getItem(ACCOUNTS_STORAGE_KEY) || '[]');
      } catch (err) {
        accounts = [];
      }

      const existing = accounts.find((a) => a.email === email);

      if (currentTab === 'signup') {
        if (existing) {
          showFeedback('Já existe uma conta cadastrada com este e-mail. Mude para a aba "Entrar na Conta".');
          return;
        }
        if (!name) {
          showFeedback('Informe seu nome completo para criar a conta.');
          return;
        }
        const newAcc = {
          id: 'usr-' + Date.now(),
          name,
          email,
          companyName,
          cnpj,
          passwordDigest,
        };
        accounts.push(newAcc);
        window.localStorage.setItem(ACCOUNTS_STORAGE_KEY, JSON.stringify(accounts));

        saveSession({
          id: newAcc.id,
          name: newAcc.name,
          email: newAcc.email,
          companyName: newAcc.companyName,
          cnpj: newAcc.cnpj,
          provider: 'email',
          authenticatedAt: new Date().toISOString(),
        });
      } else {
        if (!existing) {
          showFeedback('Conta não encontrada para este e-mail. Clique na aba "Criar Conta" para se cadastrar primeiro.');
          return;
        }
        if (existing.passwordDigest !== passwordDigest) {
          showFeedback('Senha incorreta para esta conta.');
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
      }
    });
  }

  function injectHeaderBadge(user) {
    const headerMeta = document.querySelector('.header-meta');
    if (!headerMeta) return;

    let badge = document.getElementById('antecipe-session-badge');
    if (!user) {
      if (badge) badge.remove();
      return;
    }

    if (!badge) {
      badge = document.createElement('div');
      badge.id = 'antecipe-session-badge';
      badge.style.cssText =
        'display:flex;align-items:center;gap:10px;padding:6px 12px;background:#111827;border:1px solid #1e293b;border-radius:8px;';
      headerMeta.appendChild(badge);
    }

    const initials = (user.name || 'EC').slice(0, 2).toUpperCase();
    badge.innerHTML = `
      ${
        user.pictureUrl
          ? `<img src="${user.pictureUrl}" alt="" style="width:26px;height:26px;border-radius:50%;object-fit:cover" />`
          : `<div style="width:26px;height:26px;border-radius:50%;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);color:#60a5fa;display:flex;align-items:center;justify-content:center;font-size:0.72rem;font-weight:700">${initials}</div>`
      }
      <div style="display:flex;flex-direction:column;line-height:1.15">
        <span style="font-size:0.8rem;font-weight:600;color:#f8fafc">${user.name}</span>
        <span style="font-size:0.68rem;color:#94a3b8">${user.companyName} • ${user.provider.toUpperCase()}</span>
      </div>
      <button id="antecipe-btn-logout" type="button" style="padding:4px 10px;font-size:0.75rem;border-radius:6px;border:1px solid #334155;background:#1a2234;color:#f8fafc;cursor:pointer;margin-left:4px">
        Sair
      </button>
    `;

    const logoutBtn = document.getElementById('antecipe-btn-logout');
    if (logoutBtn) {
      logoutBtn.onclick = logout;
    }
  }

  function syncView() {
    ensureAuthGateDom();
    const rootEl = document.getElementById('root');
    const overlay = document.getElementById('antecipe-auth-gate-overlay');
    const user = getLoggedUser();
    const cfg = getAuth0Config();

    const pill = document.getElementById('ag-auth0-status-pill');
    if (pill) {
      if (cfg) {
        pill.textContent = '● Auth0 Conectado (' + cfg.domain + ')';
        pill.style.color = '#34d399';
        pill.style.borderColor = 'rgba(16, 185, 129, 0.35)';
      } else {
        pill.textContent = '● Portal de Autenticação Ativo';
        pill.style.color = '#60a5fa';
        pill.style.borderColor = 'rgba(59, 130, 246, 0.35)';
      }
    }

    if (user) {
      if (overlay) overlay.style.display = 'none';
      if (rootEl) rootEl.style.display = 'block';
      injectHeaderBadge(user);
    } else {
      if (overlay) overlay.style.display = 'block';
      if (rootEl) rootEl.style.display = 'none';
      injectHeaderBadge(null);
    }
  }

  async function initAuthGate() {
    ensureAuthGateDom();
    syncView();

    // Observa renderização do React para manter o crachá do empresário no cabeçalho
    const observer = new MutationObserver(function () {
      const user = getLoggedUser();
      if (user && !document.getElementById('antecipe-session-badge')) {
        injectHeaderBadge(user);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Busca configuração automática da integração Auth0 na Vercel (/api/auth/config)
    try {
      const cfgRes = await fetch('/api/auth/config');
      if (cfgRes.ok) {
        const data = await cfgRes.json();
        if (data && data.enabled && data.domain && data.clientId) {
          serverAuth0Config = {
            domain: data.domain,
            clientId: data.clientId,
            useServerExchange: Boolean(data.useServerExchange),
          };
        }
      }
    } catch (e) {}

    // Verifica retorno OAuth2 (?code=...)
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const errorParam = params.get('error_description') || params.get('error');
    const cfg = getAuth0Config();

    if (errorParam) {
      showFeedback('Erro retornado pelo Auth0: ' + errorParam);
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (code && cfg) {
      const verifier = window.sessionStorage.getItem(PKCE_VERIFIER_KEY);
      window.sessionStorage.removeItem(PKCE_VERIFIER_KEY);
      const returnUrl =
        window.sessionStorage.getItem('antecipe_auth0_last_redirect_uri') ||
        window.location.origin + '/auth/callback';
      window.history.replaceState({}, document.title, window.location.pathname);

      if (verifier) {
        try {
          const exRes = await fetch('/api/auth/exchange', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              code,
              codeVerifier: verifier,
              redirectUri: returnUrl,
            }),
          });
          if (exRes.ok) {
            const data = await exRes.json();
            if (data && data.ok && data.user) {
              saveSession({
                id: data.user.id || 'auth0-' + Date.now(),
                name: data.user.name || data.user.email || 'Empresário Cedente',
                email: data.user.email || 'cedente@empresa.com.br',
                companyName: 'Indústria Brasil S.A.',
                cnpj: '11.222.333/0001-81',
                provider: data.user.provider || 'google',
                pictureUrl: data.user.pictureUrl,
                authenticatedAt: new Date().toISOString(),
              });
              return;
            }
          }
        } catch (e) {}

        try {
          const tokenRes = await fetch('https://' + cfg.domain + '/oauth/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              grant_type: 'authorization_code',
              client_id: cfg.clientId,
              code_verifier: verifier,
              code,
              redirect_uri: returnUrl,
            }),
          });
          if (tokenRes.ok) {
            const tokenData = await tokenRes.json();
            const userRes = await fetch('https://' + cfg.domain + '/userinfo', {
              headers: { Authorization: 'Bearer ' + tokenData.access_token },
            });
            if (userRes.ok) {
              const profile = await userRes.json();
              saveSession({
                id: profile.sub || 'auth0-' + Date.now(),
                name: profile.name || profile.email || 'Empresário Cedente',
                email: profile.email || 'cedente@empresa.com.br',
                companyName: 'Indústria Brasil S.A.',
                cnpj: '11.222.333/0001-81',
                provider: (profile.sub || '').includes('google') ? 'google' : 'auth0',
                pictureUrl: profile.picture,
                authenticatedAt: new Date().toISOString(),
              });
              return;
            }
          }
        } catch (e) {}
      }
    }

    syncView();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuthGate);
  } else {
    initAuthGate();
  }
})();

