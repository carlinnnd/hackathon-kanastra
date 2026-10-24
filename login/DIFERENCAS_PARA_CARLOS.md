# Diferenças Exatas para Integrar na `main` do Carlos (`d6050e3`)

Este documento lista **exatamente** tudo o que foi adicionado/modificado no módulo de Login do **Elias** em relação ao commit `d6050e3` da `main` do **Carlos**, para que o Carlos possa aplicar direto (extraindo o `pacote-login-elias-para-carlos.zip` na raiz do projeto ou copiando os trechos abaixo).

---

## Como aplicar tudo em 1 comando (usando o `.zip`)
Na raiz do repositório `hackathon-kanastra`, basta rodar:
```bash
unzip -o pacote-login-elias-para-carlos.zip
```

---

## Parte 1: Os únicos 3 arquivos existentes que receberam linhas novas

Nenhum arquivo dentro de `Codex/antecipe/` foi modificado. Apenas estes **3 arquivos na raiz/public** receberam linhas adicionais:

### 1. `public/index.html` (Adicionada 1 linha antes de `</body>`)
Mantém o script `/assets/index-DbNlozI0.js` da `main` do Carlos e adiciona `<script src="/assets/antecipe-auth-gate.js"></script>`:

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Antecipe — Motor de Elegibilidade e Simulação de Antecipação</title>
    <meta name="description" content="Plataforma de simulação de elegibilidade de recebíveis e análise de carteira." />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script type="module" crossorigin src="/assets/index-DbNlozI0.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-BYy8dtib.css">
  </head>
  <body>
    <div id="root"></div>
    <script src="/assets/antecipe-auth-gate.js"></script>
  </body>
</html>
```

---

### 2. `app.py` (Adicionadas as rotas `/api/auth/config` e `/api/auth/exchange`)
Mantém o `app` do Carlos e registra o roteador do Auth0 da Vercel (`login/vercel_auth_helper.py`):

```python
"""Entrypoint ASGI da demonstração pública na Vercel."""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ROOT_DIR / "Codex" / "antecipe"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(PROJECT_DIR))

from backend.vercel_app import app  # noqa: E402,F401
from login.vercel_auth_helper import router as vercel_auth_router  # noqa: E402

if not any(getattr(r, "path", None) == "/api/auth/config" for r in app.routes):
    app.include_router(vercel_auth_router)
```

---

### 3. `.vercelignore` (Adicionadas 2 linhas para não ignorar a pasta `login/`)
Logo abaixo de `!public/**`, foram adicionadas as linhas `!login` e `!login/**`:

```gitignore
*
!app.py
!requirements.txt
!.python-version
!vercel.json
!validadores_antecipe.json
!public
!public/**
!login
!login/**
!Codex
!Codex/antecipe
!Codex/antecipe/requirements.txt
!Codex/antecipe/backend
!Codex/antecipe/backend/**
!Codex/antecipe/samples
!Codex/antecipe/samples/demo.csv
!Codex/antecipe/data
!Codex/antecipe/data/cnpj_situacao_mock.csv
**/__pycache__/**
**/tests/**
**/.data/**
**/.venv/**
**/node_modules/**
**/.env*
**/*.db
**/*.db-*
**/__pycache__
**/tests
**/.data
**/.venv
**/node_modules
```

---

## Parte 2: Arquivos 100% novos (basta copiar as pastas para a raiz)

Todos os demais arquivos do pacote são novos e não existem na `main` do Carlos (zero risco de conflito):

| Caminho do Arquivo | Função |
| :--- | :--- |
| `public/assets/antecipe-auth-gate.js` | Renderiza o **Portal do Empresário (Login Gate)** antes do `#root` e injeta o **Crachá do Empresário Logado + botão "Sair"** no cabeçalho `.header-meta` após o login. |
| `public/auth/callback/index.html` | Recebe o redirecionamento OAuth2 (`?code=...`) do Auth0/Google na Vercel (`/auth/callback`) e repassa para a página principal. |
| `public/login/index.html` e `public/login/styles.css` | Página standalone do laboratório de login e inspeção de `sessionStorage`/`localStorage` acessível em `/login/`. |
| `login/vercel_auth_helper.py` | Roteador FastAPI (`/api/auth/config` e `/api/auth/exchange`) que lê `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID` e `AUTH0_CLIENT_SECRET` da Vercel ou de `login/.env`. |
| `login/AuthContext.tsx` | Contexto React completo (OAuth2 PKCE + SHA-256 + SessionStorage). |
| `login/EntrepreneurAuthView.tsx` e `login/index.ts` | Componentes React `<EntrepreneurAuthGate />` e `<EntrepreneurSessionBadge />`. |
| `login/index.html`, `login/styles.css`, `login/auth/callback/index.html` | Ambiente local de teste do módulo `login/`. |
| `login/.env.example`, `login/README.md`, `login/GUIA_INTEGRACAO_CARLOS.md` | Documentação e passo a passo de configuração do Auth0 na Vercel. |
| `docs/ARQUITETURA_SCANNER_WEB.md` | Documento de arquitetura do Scanner Web de Notas Fiscais. |
| `docs/REGISTRO_PROMPTS_ELIAS.md` | Registro cronológico auditável de prompts do Elias. |

---

## Parte 3: O que o Carlos precisa fazer no painel da Vercel (se quiser usar a própria conta Vercel)

1. Como os identificadores públicos (`AUTH0_DOMAIN` e `AUTH0_CLIENT_ID`) já estão pré-configurados no `public/assets/antecipe-auth-gate.js`, basta que na URL da Vercel do Carlos (ou no painel Auth0 do Elias em **Allowed Callback URLs** / **Allowed Web Origins**) esteja liberado o domínio `.vercel.app` do Carlos, **OU**
2. O Carlos pode instalar a integração direto na Vercel dele em **[https://vercel.com/marketplace/auth0](https://vercel.com/marketplace/auth0)** clicando em **Install** $\rightarrow$ selecionando o projeto `hackathon-kanastra` (o `app.py` lerá automaticamente as variáveis `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID` e `AUTH0_CLIENT_SECRET` da Vercel dele via `/api/auth/config`).

