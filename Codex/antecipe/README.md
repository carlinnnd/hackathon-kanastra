# Antecipe FIDC — Plataforma de Antecipação de Recebíveis

Plataforma modular para simulação de antecipação de recebíveis para Fundos de Investimento em Direitos Creditórios (FIDCs), com processamento streaming Unix de alta vazão, motor de regras configurável, antiduplicidade global e cálculo financeiro com precisão `Decimal` estrita.

> **Escopo Operacional:** O sistema destina-se estritamente à **simulação de elegibilidade, análise de risco e precificação** de títulos recebíveis. Não realiza aquisição ou liquidação financeira externa.

### Demonstração pública na Vercel

O projeto `hackathon-kanastra` usa a entrada ASGI `app.py`, Python 3.12 e as dependências existentes do backend. `vercel.json` ativa explicitamente `PUBLIC_DEMO_MODE` e o cadastro sintético. A carteira pública contém **5 títulos sintéticos (R$ 501.000,00)** provenientes dos fixtures de teste, não o estoque real de 10.621 títulos. Nenhum CSV real ou banco local é publicado.

O SQLite da demonstração fica em diretório temporário por instância serverless. **Resultados podem desaparecer ou não estar disponíveis em outra instância. Não envie dados reais.** Não há aquisição, cadastro oficial, persistência financeira de produção ou garantia de suporte aos volumes dos benchmarks locais. O limite configurado de requisição da demo é 4.000.000 bytes.

O diretório raiz `public/` contém somente o bundle estático previamente validado, com Vite 8.1.5, React 19.2.8 e TypeScript 6.0.3. Esse artefato versionado permite publicar a base sem alegar instalação npm limpa do manifesto final. Após uma alteração de frontend, validar `lint` e `build` e regenerar `public/` a partir de `Codex/antecipe/frontend/dist`; não editar o JavaScript compilado manualmente.

Na raiz do repositório, com o projeto Vercel correto vinculado:

```bash
vercel deploy --prod
```

O teste dirigido do wrapper é `python -m pytest backend/tests/test_vercel_demo.py -q`, a partir de `Codex/antecipe`. A verificação pós-deploy deve cobrir `/`, `/api/health`, `/api/portfolio/summary`, download do CSV e simulação das nove notas.

---

## 1. Visão Geral do Projeto

O **Antecipe** automatiza o processo de simulação de elegibilidade e precificação de títulos (Duplicatas e Duplicatas de Serviço) apresentados ao **ANTECIPE FIDC**.

### Principais Características
- **Arquitetura Limpa (Unix-First):** Monólito modular em camadas com estrita segregação entre Domínio puro, Aplicação, Infraestrutura e Apresentação.
- **Motor de Regras Configurável (Strategy + Registry):** Políticas carregadas a partir de `validadores_antecipe.json` (arquivo versionado no repositório), permitindo parametrização e versionamento imutável de regras sem alteração de código.
- **Precisão Financeira Estrita:** Desconto comercial simples calculado estritamente com `decimal.Decimal` (zero uso de `float`), representação estrita de valor de face em centavos (ADR-008) e arredondamento comercial `ROUND_HALF_UP` a 2 casas decimais.
- **Antiduplicidade Composta Global:** Chave única normalizada (`DOC_CEDENTE + DOC_SACADO + TIPO_RECEBIVEL + NU_DOCUMENTO + DATA_VENCIMENTO_ORIGINAL`) que reconhece parcelas legítimas e impede duplicidade contra todo o estoque histórico da base (`DUPLICIDADE_HISTORICA`) e dentro da remessa (`DUPLICIDADE_LOTE`).
- **Controle de Concentração:** Monitoramento determinístico de exposição por raiz de CNPJ do sacado (limite de 10,0% onde $\le 10{,}0\%$ é aceito e $> 10{,}0\%$ é recusado).
- **Observabilidade Estruturada:** Logs estruturados em formato JSON com allowlist estrita de campos, orientados a prevenir vazamento de dados de clientes ou payloads brutos.

---

## 2. Tecnologias e Pré-Requisitos

### Tecnologias
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic v2, Uvicorn.
- **Frontend:** React 19 (19.2.8), TypeScript (6.0.3), Vite (8.1.5), CSS modular com acessibilidade WCAG 2.2 AA.
- **Banco de Dados:** SQLite 3 local (configuração pronta para PostgreSQL via `DATABASE_URL`).
- **Testes:** Pytest, Unittest, HTTPX.

### Pré-Requisitos e Versões de Ambiente
- **Python:** Python 3.11+
- **Node.js:** Versões LTS recomendadas compatíveis com Vite 8 (Node.js 20.19+, 22.12+ ou ambiente medido 24.14.1) e npm.
- **Git**  
*(Nota de infraestrutura: Docker Compose e PostgreSQL não foram executados localmente devido à indisponibilidade de daemon Docker na máquina host; a aplicação funciona 100% autossuficiente com SQLite 3 local).*

### Separação de Dados e Configurações
1. **Configuração Regulamentar Versionada:**
   - `validadores_antecipe.json`: Especificação declarativa pública da política de crédito e validadores do fundo, mantida no repositório.
2. **Dados Reais Privados (Não Versionados no Git):**
   - `estoque_antecipe_100k/estoque_antecipe.csv`: Carteira histórica do edital (100.554 registros, SHA-256 `313c75f4147e1e851eaaefd15dc035aa895c961434da1a91024fd0764559c2f1`), mantida em diretório local externo.
   - `resultado_esperado_100k.json`: Arquivo externo de apontamento com dados privados, protegido via `.gitignore`.

---

## 3. Guia de Instalação e Execução Passo a Passo

Os comandos abaixo foram preparados para execução direta no Windows (PowerShell/CMD) e em ambientes Unix (Linux/macOS), utilizando o binário Python do ambiente virtual diretamente para evitar restrições de script (`ExecutionPolicy`).

### 3.1. Navegação até o Projeto
```bash
cd Codex/antecipe
```

### 3.2. Configuração do Ambiente Virtual Python
**No Windows (PowerShell ou CMD):**
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**No Linux ou macOS (bash/zsh):**
```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

### 3.3. Configuração de Variáveis de Ambiente
Copie o modelo de ambiente:
```bash
# Windows:
copy .env.example .env

# Linux/macOS:
cp .env.example .env
```

*Variáveis principais no `.env`:*
- `DATABASE_URL`: `sqlite:///./antecipe.db` (banco de dados SQLite local autossuficiente).
- `ADMIN_TOKEN`: token secreto exigido pelo header `X-Admin-Token` para criar/ativar versões de regras (no `.env.example` o token de exemplo vem vazio para conformidade segura).
- `ENABLE_DEMO_CADASTRO`: `false` por padrão no `.env.example` (modo cadastral conservador: títulos sem fonte oficial retornam `NAO_VERIFICADA` e são recusados). Configure para `true` apenas para executar o roteiro de demonstração sintético.

### 3.4. Inicialização do Banco e Carga do Estoque Histórico
1. **Inicialize as tabelas e a versão 1 das regras:**
   ```powershell
   # Windows:
   .\.venv\Scripts\python.exe -m backend.cli init

   # Linux/macOS:
   ./.venv/bin/python -m backend.cli init
   ```

2. **Importe o estoque histórico original (100.554 registros):**
   O arquivo oficial fornecido encontra-se na pasta `estoque_antecipe_100k/estoque_antecipe.csv`:
   ```powershell
   # Windows:
   .\.venv\Scripts\python.exe -m backend.cli import-stock --file ../../estoque_antecipe_100k/estoque_antecipe.csv

   # Linux/macOS:
   ./.venv/bin/python -m backend.cli import-stock --file ../../estoque_antecipe_100k/estoque_antecipe.csv
   ```
   *Carga transacional e idempotente que carrega os 10.621 títulos do ANTECIPE FIDC (R$ 53,07M).*

3. **Verifique o status da carteira:**
   ```powershell
   # Windows:
   .\.venv\Scripts\python.exe -m backend.cli status

   # Linux/macOS:
   ./.venv/bin/python -m backend.cli status
   ```

### 3.5. Execução do Servidor Backend
```powershell
# Windows:
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log

# Linux/macOS:
./.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```
*A flag `--no-access-log` desabilita o log de acesso padrão do Uvicorn para garantir conformidade estrita com o formato estruturado Safe JSON.*  
*API disponível em `http://127.0.0.1:8000` (Documentação interativa Swagger em `http://127.0.0.1:8000/docs`).*

---

### 3.6. Instalação e Execução do Frontend
O frontend foi construído em React 19 + Vite 8 configurado para a porta **3000**:

Em um novo terminal:
```bash
cd Codex/antecipe/frontend
npm ci
npm run lint
npm run build
npm run dev
```
*Acesse a interface no navegador em `http://localhost:3000`.*

**Versão base local:** o bundle demonstrado foi validado com Vite 8.1.5, React 19.2.8 e TypeScript 6.0.3 na árvore controlada `.data/frontend-clean-verify`. A instalação limpa ainda não foi comprovada: o registry npm retornou HTTP 403 e faltam tarballs no cache (`ENOTCACHED`). O manifesto/lockfile final foi gerado pelo npm offline e contém versões diferentes desse ambiente de build; não confundir `npm ci --dry-run` com instalação completa. Corrigir e validar essa reprodutibilidade é trabalho posterior à demonstração local.

---

## 4. Execução dos Testes Automatizados

### Validação mínima da versão base

Por solicitação do usuário, não repetir benchmarks nem a suíte completa a cada ajuste da base. Preservar todos os testes existentes e executar somente a regressão financeira crítica, seguida do smoke manual com `samples/demo.csv` (9 itens, 1 aprovado, 8 recusados e líquido de R$ 4.700,00 no modo cadastral simulado).

```powershell
# Windows, a partir de Codex/antecipe:
.\.venv\Scripts\python.exe -m pytest backend/tests/test_capacidade_monetaria_boundaries.py -q
```

No Linux/macOS, substituir o executável por `./.venv/bin/python`. A suíte completa permanece disponível para a fase posterior: `python -m pytest backend/tests qa -q`. As 113 aprovações registradas anteriormente são evidência histórica, anterior aos últimos testes e ajustes monetários.

---

## 5. Exemplos de Uso da API REST

### 5.1. Consulta de Saúde e Prontidão
```bash
curl -X GET http://127.0.0.1:8000/api/health
```

### 5.2. Download de CSV de Demonstração
```bash
curl -X GET http://127.0.0.1:8000/api/demo.csv -o demo.csv
```

### 5.3. Submissão de Simulação via Upload Multipart
```bash
curl -X POST http://127.0.0.1:8000/api/simulations \
  -F "file=@demo.csv"
```

### 5.4. Avaliação Direta via JSON
```bash
curl -X POST http://127.0.0.1:8000/api/receivables/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "data_base": "2026-10-22",
    "recebiveis": [
      {
        "NOME_FUNDO": "ANTECIPE FIDC",
        "DOC_FUNDO": "12345678000199",
        "NOME_CEDENTE": "FORNECEDOR LTDA",
        "DOC_CEDENTE": "11222333000181",
        "NOME_SACADO": "CLIENTE SA",
        "DOC_SACADO": "99888777000109",
        "NU_DOCUMENTO": "NF-5001",
        "TIPO_RECEBIVEL": "Duplicata",
        "VALOR_NOMINAL": "5000,00",
        "DATA_VENCIMENTO_ORIGINAL": "20/01/2027",
        "DATA_AQUISICAO": "22/10/2026"
      }
    ]
  }'
```

---

## 6. Principais Decisões e Limitações Conhecidas

### Decisões Arquiteturais (ADRs)
1. **Monólito Modular Local (ADR-001):** Executável do zero sem necessidade de Docker.
2. **Strategy + Registry (ADR-002):** Validadores tipados; zero `eval()`.
3. **Decimal Estrito (ADR-003):** Cálculos financeiros comerciais `ROUND_HALF_UP` sem aproximações de ponto flutuante binário.
4. **Antiduplicidade Composta Global (ADR-004):** Permite parcelas distintas com vencimentos diferentes e valida contra todo o estoque histórico da base (`DUPLICIDADE_HISTORICA`).
5. **Concentração com Excesso Histórico Documentado (ADR-005):** Preserva o estoque; aceita exatamente 10,0% e recusa novas aquisições que ultrapassem 10,0%.
6. **Situação Cadastral Conservadora (ADR-006):** Inelegibilidade padrão para sacados não verificados; demonstração controlada por flag explícita.
7. **Suporte Dual SQLite/PostgreSQL (ADR-007):** SQLite zero-conf local testado com suporte estruturado para PostgreSQL via SQLAlchemy.
8. **Representação Estrita de Valor Nominal em Centavos (ADR-008):** Rejeição de frações além de 2 casas decimais para evitar inconsistências no valor de face.

### Limitações Conhecidas
1. **Ambiente Local sem Docker:** O banco SQLite local atende integralmente à simulação com alta performance. PostgreSQL e Docker Compose não foram executados localmente por indisponibilidade de daemon Docker.
2. **Consulta Cadastral Externa:** Em ambiente offline, sacados não mapeados no conjunto sintético são classificados como `NAO_VERIFICADA`.
3. **Apenas Simulação:** Não efetua liquidação bancária, emissão de boletos ou transferência de recursos.
