# Módulo Isolado de Autenticação (`login/`) — Antecipe FIDC

Este diretório concentra **100% da implementação de Login do Empresário (Cedente)** de forma isolada na branch `login`, garantindo **zero conflito** com os arquivos que o **Carlos** (Backend/Vercel) e o **Pina** (Frontend principal) estão editando.

---

## 1. Estrutura do Diretório `login/`

```text
login/
├── index.html                  # Laboratório visual standalone (testa Login Normal + Google/Auth0 + Storage)
├── styles.css                  # Estilos do Portal do Empresário (alinhados ao tema Antecipe)
├── AuthContext.tsx             # Provedor React (Auth0 Vercel Marketplace OAuth2 PKCE + Criar Conta SHA-256)
├── EntrepreneurAuthView.tsx    # Componentes React (<EntrepreneurAuthGate /> e <EntrepreneurSessionBadge />)
├── index.ts                    # Exportação unificada para o Pina importar com 1 linha no React
├── .env.example                # Variáveis públicas da integração https://vercel.com/marketplace/auth0
└── README.md                   # Este guia passo a passo
```

---

## 2. Passo a Passo para Testar Agora (Login Normal + Login Real com Gmail via Auth0)

### Passo 2.1 — Subir o servidor de teste do diretório `login/`
No terminal, na raiz do projeto, execute:

```bash
python3 -m http.server 8090 --directory login
```

Abra no navegador:
👉 **`http://localhost:8090`**

### Passo 2.2 — Testar o Login Normal (Criar Conta + Entrar com E-mail/Senha)
1. Clique na aba **"Criar Conta"**, preencha Nome, Razão Social, CNPJ, E-mail e Senha (mínimo 6 caracteres) e clique em **Criar Conta**.
2. Veja no painel **"Raio-X do Storage"** que o usuário foi salvo em `sessionStorage["antecipe_entrepreneur_session_v1"]` e a conta foi salva em `localStorage["antecipe_entrepreneur_accounts_v1"]` apenas com o `passwordDigest` em `SHA-256` (sem senha em texto puro).
3. Clique em **Sair** e tente entrar com um e-mail não cadastrado ou senha errada para ver o bloqueio funcionando.

### Passo 2.3 — Ativar e Testar o Login Oficial com Google (Gmail) via Auth0
Para o botão **"Continuar com Google (Gmail)"** abrir a janela oficial da Google (`accounts.google.com`):

1. Acesse **[manage.auth0.com](https://manage.auth0.com)** (ou instale a integração em **[vercel.com/marketplace/auth0](https://vercel.com/marketplace/auth0)**).
2. No menu lateral do Auth0, vá em **Applications $\rightarrow$ Applications** e clique em **"+ Create Application"**:
   - Nome: `Antecipe FIDC`
   - Tipo: Selecione **Single Page Web Applications** (muito importante para liberar OAuth2 PKCE no navegador!) e clique em **Create**.
3. Clique na aba **Settings** da aplicação criada no Auth0:
   - Copie o **Domain** (ex.: `dev-xxxx.us.auth0.com`) e o **Client ID**.
   - Role até os 3 campos (**Allowed Callback URLs**, **Allowed Logout URLs** e **Allowed Web Origins**) e cole nos 3 campos:
     ```text
     http://localhost:8090, http://localhost:8090/index.html, http://localhost:5173
     ```
     *(Quando tiverem a URL da Vercel do Carlos, basta adicionar `, https://seu-projeto.vercel.app` nesses mesmos 3 campos).*
   - Role até o final da página do Auth0 e clique em **Save Changes**.
4. Volte para `http://localhost:8090`, cole o **Domain** e o **Client ID** no **Card 1 ("Conectar Auth0")** e clique em **"Salvar Chaves Auth0 e Ativar Login Google"**.
5. Agora clique no botão branco **"Continuar com Google (Gmail)"**:
   - O navegador vai redirecionar para a tela oficial de login da Google (`accounts.google.com`), pedir para você escolher sua conta real do Gmail e voltar para `http://localhost:8090` já logado com seu nome, e-mail e foto do Google salvos no `sessionStorage`!

---

## 3. Como Integrar com o Frontend que o Pina está fazendo (Em 2 minutos)

Quando a branch `login` for juntada com o trabalho do Pina:

1. Copiar os arquivos `login/AuthContext.tsx`, `login/EntrepreneurAuthView.tsx` e `login/index.ts` para dentro de `Codex/antecipe/frontend/src/login/` (ou importar direto de `../../../login`).
2. Em `Codex/antecipe/frontend/src/main.tsx`, envolver o `<App />`:
   ```tsx
   import { AuthProvider, EntrepreneurAuthGate } from './login';

   // Dentro do root.render:
   <AuthProvider>
     <EntrepreneurAuthGate>
       <App />
     </EntrepreneurAuthGate>
   </AuthProvider>
   ```
3. No cabeçalho do `App.tsx`, adicionar `<EntrepreneurSessionBadge />` para mostrar o avatar/nome do empresário logado e o botão **Sair**.
4. Na Vercel (**Settings $\rightarrow$ Environment Variables** — ou automático via `vercel.com/marketplace/auth0`), garantir as variáveis:
   - `VITE_AUTH0_DOMAIN` (ou `NEXT_PUBLIC_AUTH0_DOMAIN`)
   - `VITE_AUTH0_CLIENT_ID` (ou `NEXT_PUBLIC_AUTH0_CLIENT_ID`)

