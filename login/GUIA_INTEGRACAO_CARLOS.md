# Guia de Integração — Autenticação Auth0 & Portal do Empresário (para o Carlos)

Este guia orienta como o **Carlos** pode mesclar todo o trabalho de autenticação desenvolvido pelo **Elias** e ativar o **Auth0 (Google OAuth2 + E-mail/Senha SHA-256 + Demo)** na Vercel e no ambiente local.

---

## 1. Mesclar o código do Elias na branch principal

O Elias já enviou a branch `login` tanto para o repositório oficial (`origin/login`) quanto para o fork dele.

No terminal do Carlos (no repositório `hackathon-kanastra`):

```bash
# 1. Garante que está na sua branch main
git checkout main

# 2. Busca e junta as atualizações da branch login
git fetch origin login
git merge origin/login --no-edit

# 3. Envia para a sua main oficial
git push origin main
```

---

## 2. Configurar o Auth0 na Vercel do Carlos

Existem duas formas fáceis para o Carlos ter o Auth0 funcionando no deploy dele da Vercel:

### Opção A (Recomendada — Instalação Direta via Marketplace da Vercel — 1 minuto)
1. Acesse: **[https://vercel.com/marketplace/auth0](https://vercel.com/marketplace/auth0)**
2. Clique no botão **"Install"** (ou "Add Integration").
3. Selecione a sua conta da Vercel e o projeto **`hackathon-kanastra`**.
4. No campo **Localhost URL**, informe `http://localhost:8000` (ou `http://localhost:3000`).
5. No campo **Callback Endpoint**, mantenha `/auth/callback`.
6. Escolha o plano **Free** e clique em **Continue / Install**.
7. **Pronto!** A Vercel criará automaticamente a aplicação no Auth0 e injetará as seguintes variáveis de ambiente no projeto (`Settings -> Environment Variables`):
   - `AUTH0_DOMAIN` (ou `AUTH0_ISSUER_BASE_URL`)
   - `AUTH0_CLIENT_ID`
   - `AUTH0_CLIENT_SECRET`

### Opção B (Usar o mesmo tenant Auth0 já criado pelo Elias)
Caso vocês queiram usar o mesmo banco de usuários e chaves que o Elias configurou:
1. O Elias compartilha com o Carlos o `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID` e `AUTH0_CLIENT_SECRET` por canal privado e seguro.
2. Na Vercel do Carlos: vá no projeto **`hackathon-kanastra`** &rarr; aba **Settings** &rarr; **Environment Variables** e adicione as três variáveis.
3. No painel do Auth0 da aplicação: adicione a URL da Vercel do Carlos nos campos:
   - **Allowed Callback URLs**: `https://<dominio-do-carlos>.vercel.app/auth/callback`
   - **Allowed Logout URLs**: `https://<dominio-do-carlos>.vercel.app/`
   - **Allowed Web Origins**: `https://<dominio-do-carlos>.vercel.app`

---

## 3. Ambiente de Desenvolvimento Local (Opcional)

Se o Carlos for testar localmente na máquina dele:
1. Crie o arquivo `login/.env` (este arquivo já está no `.gitignore` e nunca sobe ao GitHub):
   ```env
   AUTH0_CLIENT_ID="seu_client_id"
   AUTH0_CLIENT_SECRET="seu_client_secret"
   AUTH0_DOMAIN="seu_dominio.us.auth0.com"
   ```
2. O `app.py` e o helper `login/vercel_auth_helper.py` lêem automaticamente tanto as variáveis de ambiente do sistema (`os.environ`) quanto o arquivo `login/.env`.

---

## 4. O que foi adicionado / Como o fluxo opera

1. **Backend (`app.py` & `login/vercel_auth_helper.py`)**:
   - Monta os endpoints `/api/auth/config` (expõe parâmetros públicos) e `/api/auth/exchange` (faz a troca segura do código OAuth2 com o Auth0 sem expor client secret).
   - Não grava PII em logs e obedece à allowlist do middleware de Safe Logging.

2. **Frontend Principal (`public/index.html` & `public/assets/antecipe-auth-gate.js`)**:
   - Bloqueia a visualização da esteira Antecipe até o empresário se identificar.
   - Oferece:
     - **Google (Gmail)**: fluxo oficial OAuth2 PKCE via Auth0;
     - **Criar Conta / Entrar**: validação com hash `SHA-256` no navegador (sem trafegar senha em texto puro);
     - **Acesso Rápido Demo**: empresário fictício (CNPJ `11.222.333/0001-81`).
   - Após autenticado: exibe o crachá do empresário no cabeçalho com o botão **"Sair"** e libera o dashboard completo.

3. **Callback Handler (`public/auth/callback/index.html`)**:
   - Captura o redirecionamento OAuth2 do Auth0 e envia o código para o app concluir a sessão.

