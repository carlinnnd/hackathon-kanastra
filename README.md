LINK DA APLICAÇÃO: https://hackathon-kanastra.vercel.app/

# 🚀 Antecipe FIDC — Portal de Antecipação de Recebíveis

**Hackathon Kanastra 2026 (FACOM TechWeek)** | Python 3.12 · FastAPI · React 19 · TypeScript · Vite 8 · Auth0 · SQLite / SQLAlchemy · Vercel

> **⚡ Acesso Imediato para os Jurados (Recomendado):**
> A forma mais rápida e prática de avaliar a aplicação é diretamente pelo nosso deploy em produção na Vercel:
> 👉 **[https://hackathon-kanastra.vercel.app/](https://hackathon-kanastra.vercel.app/)**
> Não é necessário instalar nada na máquina para testar toda a jornada: autenticação, upload de CSV, geração automática de lotes de teste (100 a 1.000 notas), diagnóstico individual de aprovação/recusa em linguagem de negócio, cálculo de valor líquido, simulador **What-If** de regras sem deploy e exportação de relatórios em **CSV** e **PDF**.

---

## 🌠 Visão Geral (Overview)

O **Portal Antecipe** resolve a jornada de ponta a ponta de pequenas e médias empresas (cedentes) que venderam a prazo e desejam antecipar seus recebíveis hoje junto ao fundo **ANTECIPE FIDC**, garantindo que o fundo compre apenas títulos elegíveis segundo sua política de risco configurável.

A plataforma permite que empresas cedentes e gestores do fundo:

- 🔍 **Validem Lotes de Recebíveis (CSV ou API)** — Processamento em *streaming* de arquivos no padrão brasileiro (separador `;`, decimal com vírgula `,`, datas `dd/mm/aaaa`, UTF-8).
- 💬 **Compreendam Cada Recusa com Clareza (UX Acionável)** — Tradução imediata de regras financeiras e cadastrais em explicações claras para a empresa cedente, indicando o valor encontrado, o limite exigido e como corrigir.
- 💰 **Simulem o Valor Líquido Exato (`Decimal` Estrito)** — Cálculo determinístico de desconto comercial simples (`2,0% a.m.`, base `30 dias`, arredondamento comercial `ROUND_HALF_UP` ao centavo) por nota aprovada e total líquido a receber.
- ⚙️ **Alterem Regras sem Deploy (Motor Strategy + Registry & Simulador What-If)** — Regras lidas dinamicamente de [`validadores_antecipe.json`](validadores_antecipe.json), sem nenhum valor fixo (*hardcoded*) no código, com versionamento imutável auditado por SHA-256.
- 🛡️ **Impeçam Dupla Venda e Excesso de Concentração** — Antiduplicidade composta global contra os 100.554 títulos históricos (`DUPLICIDADE_HISTORICA`) e dentro da mesma remessa (`DUPLICIDADE_LOTE`), além de teto de concentração de `10,0%` por grupo econômico (raiz de CNPJ do sacado).

---

## 🛰️ Funcionalidades Principais (Features)

- ✨ **Autenticação Institucional Segura (Auth0 + Google OAuth 2.0 PKCE)** — Tela de login com vídeo institucional de fundo inspirado na Kanastra, suporte a login social Google e credenciais com sessão `HttpOnly` validada no backend.
- 🧩 **Motor de Regras 100% Dinâmico (`validadores_antecipe.json`)** — Ativação/desativação (`"ativo": true/false`) e ajuste de parâmetros (`valor_minimo`, `prazo_maximo_dias`, `percentual_maximo`, `tipos_aceitos`, `taxa_mensal_percentual`) em tempo de execução sem necessidade de deploy.
- 📊 **Dashboard Executivo e Gráficos Analíticos** — Visão consolidada do lote com KPIs de aprovação, deságio, prazo médio ponderado, distribuição de recusas por regra e filtros rápidos (`Todos`, `Aprovados`, `Recusados`).
- 📄 **Exportação Completa de Relatórios** — Download imediato do resultado da simulação em **CSV completo**, **Relatório Executivo em PDF** e **CSV exclusivo de violações/recusas**.
- ⚡ **Engenharia Unix de Alta Vazão (100k a 500k linhas)** — Pipeline em geradores Python com memória controlada e transporte via WebSocket/HTTP.

---

## 🧭 Como Funciona (How It Works)

1. **Ingestão e Normalização (`backend.domain.ingestion`)**
   → Lê o CSV em *streaming* linha a linha, valida as 11 colunas obrigatórias, normaliza CNPJs/datas `dd/mm/aaaa` e garante precisão estrita de 2 casas decimais (`Decimal`, sem `float`).
2. **Checagem de Antiduplicidade e Cadastro (`backend.domain.engine` + `cnpj_provider`)**
   → Verifica a chave composta (`DOC_CEDENTE + DOC_SACADO + TIPO_RECEBIVEL + NU_DOCUMENTO + DATA_VENCIMENTO_ORIGINAL`) contra a carteira histórica e intra-lote, permitindo parcelas legítimas com vencimentos distintos, e consulta a situação cadastral do sacado (`cnpj_situacao_mock.csv`).
3. **Avaliação pelo Motor de Regras e Concentração (`backend.domain.rules`)**
   → Executa os validadores ativos em [`validadores_antecipe.json`](validadores_antecipe.json) e projeta incrementalmente a exposição por raiz de CNPJ do sacado ($\le 10{,}0\%$ aprovado; $> 10{,}0\%$ recusado).
4. **Precificação Comercial Simples (`backend.domain.pricing`)**
   → Calcula o desconto comercial simples e o valor líquido para cada título aprovado:
   $$\text{Valor Líquido} = \text{round}\left(V_{\text{nominal}} \times \left(1 - \frac{\text{taxa\_mensal}}{100} \times \frac{\text{dias}}{30}\right),\ 2\right)$$
5. **Visualização Interativa e API (`frontend` + `FastAPI`)**
   → A mesma validação é exposta na interface web React e nos endpoints REST/WebSocket.

---

## 🔬 Componentes Principais (Core Components)

| Componente | Caminho Principal | Descrição |
| :--- | :--- | :--- |
| `Domínio Puro (Unix)` | `Codex/antecipe/backend/domain/` | Regras de elegibilidade (`rules.py`), motor (`engine.py`), precificação `Decimal` (`pricing.py`), ingestão CSV (`ingestion.py`) e validação de CNPJ (`cnpj.py`) — **zero dependência de banco ou HTTP**. |
| `Aplicação e Serviços` | `Codex/antecipe/backend/application/` | Orquestração de simulações, versionamento de regras sem deploy, relatórios CSV/PDF e gerador de lotes sintéticos (`sample_batches.py`). |
| `API Backend (FastAPI)` | `Codex/antecipe/backend/api/` | Endpoints REST (`/api/simulations`, `/api/receivables/evaluate`, `/api/rules`), WebSocket (`/api/simulations/stream`), sessão Auth0 (`auth_routes.py`) e Safe JSON Logger (`logger.py`). |
| `Frontend (React + Vite)` | `Codex/antecipe/frontend/` & `public/` | Interface web responsiva (WCAG 2.2 AA), tela de login com vídeo institucional, upload de lotes, tabela de decisões e simulador What-If. |
| `Configuração e Dados` | `validadores_antecipe.json` | Política de crédito oficial do fundo ANTECIPE FIDC lida dinamicamente e base cadastral `cnpj_situacao_mock.csv`. |
| `Governança e Testes` | `tests/` & `docs/` | Suítes automatizadas (`unittest` e `pytest`), scripts de auditoria de segurança/logs (`scripts/`) e registros cronológicos de prompts (`docs/REGISTRO_PROMPTS.md`). |

---

## 🌐 Opção 1 (Prioridade Recomendada): Testar Direto na Vercel

Acesse **[https://hackathon-kanastra.vercel.app/](https://hackathon-kanastra.vercel.app/)** no navegador:

1. **Autenticação (Login):**
   - Entre com **Google (OAuth 2.0 PKCE)** ou com e-mail e senha na tela de login institucional.
2. **Simulação de Lote CSV (Upload ou 1 Clique):**
   - Clique em **"Baixar CSV Exemplo (`demo.csv`)"** e envie o arquivo na área de upload, **OU** utilize os botões rápidos de **Amostra Homologada (100 notas / 1.000 notas)** para testar imediatamente sem precisar baixar arquivo.
   - Você também pode enviar qualquer arquivo `.csv` seguindo o formato do edital (`;`, decimal `,`, datas `dd/mm/aaaa`).
3. **Análise de Resultados e Explicação de Recusas:**
   - Veja no topo os cards com **Total Nominal**, **Desconto Total**, **Valor Líquido Total a Receber** e **Taxa de Aprovação**.
   - Na tabela de notas, filtre por **Todas**, **Aprovadas** ou **Recusadas** e veja em cada nota recusada a **explicação clara em português** pensada para a empresa cedente.
   - Baixe o resultado completo em **CSV**, **PDF Executivo** ou **Relatório de Violações**.
4. **Simulador What-If (Alteração de Regras sem Deploy):**
   - Altere na interface parâmetros como Valor Mínimo, Prazo Máximo, Limite de Concentração ou Taxa de Desconto e compare em tempo real o impacto sobre a aprovação do lote.
5. **Teste Direto da Mesma Validação via API REST na Vercel:**
   ```bash
   # 1. Healthcheck e metadados operacionais:
   curl -s https://hackathon-kanastra.vercel.app/api/health

   # 2. Avaliação direta de recebíveis via API JSON:
   curl -s -X POST https://hackathon-kanastra.vercel.app/api/receivables/evaluate \
     -H "Content-Type: application/json" \
     -d '{
       "recebiveis": [
         {
           "NOME_FUNDO": "ANTECIPE FIDC",
           "DOC_FUNDO": "92.234.400/0001-80",
           "NOME_CEDENTE": "INDUSTRIA BRASIL SA",
           "DOC_CEDENTE": "11.222.333/0001-81",
           "NOME_SACADO": "CLIENTE ATIVO LTDA",
           "DOC_SACADO": "04.252.011/0001-10",
           "NU_DOCUMENTO": "NF-9001",
           "TIPO_RECEBIVEL": "Duplicata",
           "VALOR_NOMINAL": "5000,00",
           "DATA_VENCIMENTO_ORIGINAL": "21/11/2026",
           "DATA_AQUISICAO": "24/10/2026"
         }
       ]
     }'
   ```

---

## 💻 Opção 2: Passo a Passo Completo para Rodar Localmente do Zero

Caso deseje executar a aplicação localmente na sua máquina (Linux, macOS ou Windows), siga o passo a passo abaixo.

### 1) Estrutura do Repositório (Quick Map)

- `app.py` & `vercel.json` → Ponto de entrada ASGI unificado e configuração de deploy Vercel
- `validadores_antecipe.json` → Configuração oficial das regras e taxa do ANTECIPE FIDC
- `Codex/antecipe/backend/` → Aplicação FastAPI, motor de domínio, CLI e testes de integração
- `Codex/antecipe/frontend/` → Código-fonte React 19 + TypeScript + Vite 8
- `public/` → Bundle estático compilado do frontend servido pelo backend
- `tests/` & `scripts/` → Suíte de testes de domínio/kit e scripts de auditoria de logs e prompts
- `docs/` → Documentação arquitetural, matriz de recusas, evidências de benchmark e registro de prompts

### 2) Pré-Requisitos do Sistema

- **Python 3.11+** (testado em Python 3.11 e 3.12)
- **Node.js 20+** e **npm** *(opcional — necessário apenas se quiser recompilar o frontend em modo dev, pois o backend já serve o bundle pronto em `public/`)*
- **Git**
- *(Não requer Docker nem servidor de banco externo: utiliza **SQLite 3** local autossuficiente por padrão, com suporte pronto a PostgreSQL via `DATABASE_URL`).*

### 3) Instalação das Dependências Python

Abra o terminal na raiz do repositório clonado (`hackathon-kanastra`):

**No Linux / macOS:**
```bash
cd Codex/antecipe
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

**No Windows (PowerShell ou CMD):**
```powershell
cd Codex\antecipe
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4) Variáveis de Ambiente (`.env`)

Dentro de `Codex/antecipe`, copie o arquivo de exemplo `.env.example` para `.env` (ou utilize diretamente o arquivo `.env` enviado junto ao formulário oficial de entrega):

```bash
# Linux / macOS (dentro de Codex/antecipe):
cp .env.example .env

# Windows (dentro de Codex\antecipe):
copy .env.example .env
```

Principais variáveis de ambiente (`Codex/antecipe/.env`):
```env
ENV=development
DATABASE_URL=sqlite:///./antecipe.db
ESTOQUE_CSV_PATH=../../estoque_antecipe_100k/estoque_antecipe.csv
VALIDADORES_JSON_PATH=../../validadores_antecipe.json
ENABLE_DEMO_CADASTRO=true
ADMIN_TOKEN=

# Credenciais Auth0 (enviadas no arquivo .env do formulário de submissão):
AUTH0_DOMAIN=icfg-qbtjet3r34vhsn7hvbn1ch1w.us.auth0.com
AUTH0_CLIENT_ID=ptDlCgO5ZLDVMYVOCHyDHaGporfYw1Mi
AUTH0_CLIENT_SECRET=<SEGREDO_ENVIADO_NO_ARQUIVO_ENV_DO_FORMULARIO>
AUTH0_DB_CONNECTION=Username-Password-Authentication
```
> 💡 **Nota prática:** A aplicação possui *defaults* seguros em `Codex/antecipe/backend/config.py` e funciona perfeitamente mesmo sem segredos externos usando o modo `--stub-auth` descrito abaixo.

### 5) Inicializar o Banco de Dados e Carregar a Carteira

Ainda dentro de `Codex/antecipe`:

1. **Inicialize o banco SQLite e carregue a versão 1 das regras (`validadores_antecipe.json`):**
   ```bash
   # Linux / macOS:
   ./.venv/bin/python -m backend.cli init

   # Windows:
   .\.venv\Scripts\python.exe -m backend.cli init
   ```

2. **(Opcional) Importe o estoque histórico de 100.554 linhas (`estoque_antecipe.csv`):**
   Caso tenha descompactado `estoque_antecipe_100k.zip` em `estoque_antecipe_100k/estoque_antecipe.csv`:
   ```bash
   # Linux / macOS:
   ./.venv/bin/python -m backend.cli import-stock --file ../../estoque_antecipe_100k/estoque_antecipe.csv

   # Windows:
   .\.venv\Scripts\python.exe -m backend.cli import-stock --file ..\..\estoque_antecipe_100k\estoque_antecipe.csv
   ```

3. **Verifique o status da carteira:**
   ```bash
   # Linux / macOS:
   ./.venv/bin/python -m backend.cli status

   # Windows:
   .\.venv\Scripts\python.exe -m backend.cli status
   ```

### 6) Subir a Aplicação Localmente (Quickstart)

Você pode subir a aplicação local de **duas formas**:

#### Forma A (Mais Prática — 1 Único Comando com Frontend + Backend integrados na porta `8015`):
A partir da **raiz do repositório (`hackathon-kanastra`)**:
```bash
# Linux / macOS:
./Codex/antecipe/.venv/bin/python Codex/antecipe/qa/serve_portal_review.py --stub-auth --port 8015

# Windows:
.\Codex\antecipe\.venv\Scripts\python.exe Codex\antecipe\qa\serve_portal_review.py --stub-auth --port 8015
```
👉 Acesse no navegador: **`http://127.0.0.1:8015`**

#### Forma B (Execução separada Backend na porta `8000` + Frontend Vite na porta `3000`):
1. **Terminal 1 — Backend FastAPI (`porta 8000`):**
   ```bash
   cd Codex/antecipe
   # Linux / macOS:
   ./.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log

   # Windows:
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
   ```
2. **Terminal 2 — Frontend React + Vite (`porta 3000`):**
   ```bash
   cd Codex/antecipe/frontend
   npm ci
   npm run dev
   ```

### 7) Portas e URLs Padrão

- **Produção (Vercel):** `https://hackathon-kanastra.vercel.app/`
- **Portal Local Integrado (`serve_portal_review.py`):** `http://127.0.0.1:8015`
- **API Backend Local (FastAPI):** `http://127.0.0.1:8000` (Healthcheck: `/api/health` | Swagger UI: `/docs`)
- **Frontend Dev Server (Vite):** `http://localhost:3000`

---

## 📋 Relatório Curto do Projeto (Requisitos do Enunciado)

### 1. O que o Time Construiu
Construímos a solução completa do **Portal Antecipe FIDC**:
- **Jornada de UX e Explicação de Recusas:** Do login com vídeo institucional e upload/geração de lote CSV até a tabela interativa com status por nota (`APROVADA` ou `RECUSADA`), valor líquido individual, total líquido a receber e tradução clara de cada motivo de recusa para que o empresário saiba exatamente por que uma nota foi recusada e como proceder.
- **Motor de Regras Configurável sem Deploy:** Leitura integral de [`validadores_antecipe.json`](validadores_antecipe.json) sem valores fixos no código, suportando ativação/desativação de regras e alteração de parâmetros em tempo real pelo **Simulador What-If** e pela API (`POST /api/rules`).
- **Idempotência, Antiduplicidade e Concentração:** Chave única composta que distingue parcelas legítimas de uma mesma nota fiscal (vencimentos diferentes) e barra duplicidades contra o estoque histórico (`DUPLICIDADE_HISTORICA`) e dentro do lote (`DUPLICIDADE_LOTE`), além de controlar o limite de `10,0%` de concentração por raiz de CNPJ do sacado.
- **Validação Idêntica via Tela e API + Relatórios:** Mesma lógica de domínio disponível pela interface web e pelos endpoints REST/WebSocket, com exportação em CSV e PDF.

### 2. Principais Decisões Técnicas (ADRs)
Documentadas em [`docs/DECISOES_TECNICAS.md`](docs/DECISOES_TECNICAS.md):
- **ADR-001 & ADR-002 (Filosofia Unix + Strategy/Registry):** Domínio 100% puro e isolado de I/O; cada código de validador do JSON mapeia para uma classe determinística sem uso de `eval()`.
- **ADR-003 & ADR-008 (`Decimal` Estrito e Centavos Exatos):** Zero uso de `float`. Rejeição de frações além de 2 casas decimais no valor de face e arredondamento comercial `ROUND_HALF_UP` ao centavo no cálculo do desconto simples.
- **ADR-004 & ADR-005 (Chave Composta e Excesso Histórico Documentado):** Preserva o estoque histórico original e bloqueia qualquer nova aquisição que ultrapasse `10,0%` da carteira projetada do fundo.
- **ADR-006 (Situação Cadastral com `cnpj_situacao_mock.csv`):** Carregamento em memória (`O(1)`) dos CNPJs do mock oficial com política *fail-closed* (`NAO_VERIFICADA` $\rightarrow$ `RECUSADA`) para CNPJs ausentes.

### 3. O que Ficou de Fora (Escopo Consciente)
- **Liquidação Bancária Externa (PIX/TED/CIP):** A aplicação realiza a simulação de elegibilidade, risco e precificação; não executa movimentação bancária real.
- **Consulta Síncrona Externa à Receita Federal na Internet:** Para garantir processamento de 100k a 500k linhas sem bloqueio de rede/rate-limit, utiliza a base cadastral `cnpj_situacao_mock.csv` fornecida no desafio.
- **Scanner OCR por Câmera:** A arquitetura foi desenhada e documentada em [`docs/ARQUITETURA_SCANNER_WEB.md`](docs/ARQUITETURA_SCANNER_WEB.md) como evolução futura, priorizando a robustez do pipeline CSV de alto volume e da plataforma web principal.

---

## 🏆 Mapa de Evidências para os Critérios de Avaliação (100 Pontos — Seção 5.2)

| Critério do Edital | Pontos | Onde Conferir no Repositório |
| :--- | :---: | :--- |
| **5.2.1 Escalabilidade** (100k a 500k linhas e velocidade) | **35 pts** | Medições reais de **100.000** e **500.000 linhas** registradas com comando, ambiente, memória RSS e throughput em **[`docs/EVIDENCIAS.md`](docs/EVIDENCIAS.md)** e scripts em `Codex/antecipe/benchmarks/`. |
| **5.2.2 Design e UX** (clareza das recusas, design, interface) | **25 pts** | Aplicação ao vivo em **[hackathon-kanastra.vercel.app](https://hackathon-kanastra.vercel.app/)**, catálogo humano de recusas em **[`docs/MATRIZ_RECUSAS.md`](docs/MATRIZ_RECUSAS.md)**, login com vídeo institucional, What-If e exportação CSV/PDF. |
| **5.2.3 Organização — Filosofia Unix** (segregação e código limpo) | **20 pts** | Separação estrita em `Codex/antecipe/backend/{domain,application,infrastructure,api}` e CLI Unix em `Codex/antecipe/backend/cli.py`. |
| **5.2.4 Logs e Credenciais** (logs estruturados, zero CSV nos logs, zero segredos) | **15 pts** | Safe JSON Logger com *allowlist* em `Codex/antecipe/backend/logger.py`, verificador `scripts/check_logs.py` e auditoria `scripts/check_submission.py`. |
| **5.2.5 Registro de Prompts** (ordem cronológica + o que foi feito) | **5 pts** | Índice geral em **[`docs/REGISTRO_PROMPTS.md`](docs/REGISTRO_PROMPTS.md)** e registros cronológicos de **[Carlos](docs/REGISTRO_PROMPTS_CARLOS.md)**, **[Elias](docs/REGISTRO_PROMPTS_ELIAS.md)** e **[Pina](docs/REGISTRO_PROMPTS_PINA.md)**. |

---

## 🧪 Como Rodar os Testes Automatizados

Na raiz do repositório (`hackathon-kanastra`), execute a suíte rápida de domínio, regras, financeiro, ingestão CSV e auditoria do kit (29 testes, zero dependências externas):

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 scripts/check_submission.py
python3 scripts/prompt_ledger.py audit
```

Para rodar também a suíte completa de integração FastAPI/WebSocket dentro de `Codex/antecipe`:
```bash
# Linux / macOS:
./Codex/antecipe/.venv/bin/python -m pytest Codex/antecipe/backend/tests -q

# Windows:
.\Codex\antecipe\.venv\Scripts\python.exe -m pytest Codex\antecipe\backend\tests -q
```
