# Registro de decisões técnicas (ADR) — Antecipe FIDC

---

## ADR-001 — Estrutura de Monólito Modular Local em Python e React

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Coordenação & Arquitetura)
- **Contexto/restrição oficial:** O desafio exige entrega funcional, segura, testável e apresentável com prazo determinado (24/10/2026, 18h). A estação de trabalho local inspecionada dispõe de Python 3.11 e Node 24, porém não dispõe de daemon Docker ativo. O ambiente dos avaliadores externos é desconhecido.
- **Alternativas consideradas:**
  1. Microserviços distribuídos com mensageria (Kafka/RabbitMQ).
  2. Monólito modular com backend FastAPI (Python 3.11) e frontend React/Vite (Node 24).
- **Escolha e trade-offs:** Adotado o **monólito modular**. Elimina custos de rede, serialização excessiva e complexidade de orquestração. Permite execução local autossuficiente com SQLite e suporte declarativo a PostgreSQL via variável `DATABASE_URL` quando o ambiente dispuser de banco externo.
- **Impacto sobre pontuação:** Maximiza estabilidade, simplicidade de inicialização auditável e conformidade com critérios de arquitetura Unix-first.
- **Teste ou evidência:** Aplicação executável do zero sem Docker; suíte integrada rodando em ~11,7s com 113 testes aprovados.
- **Status:** **Aceita**.

---

## ADR-002 — Motor de Regras Orientado a Configuração (Strategy + Registry)

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Motor / Domínio)
- **Contexto/restrição oficial:** As regras de elegibilidade vêm de um arquivo JSON externo (`validadores_antecipe.json`). O sistema deve permitir alterar parâmetros ou ativar/desativar validadores sem necessidade de redeploy ou alteração de código. Proibida execução arbitrária de código (`eval`).
- **Alternativas consideradas:**
  1. Condicionais `if/elif` hardcoded no código.
  2. Motor baseado em expressões dinâmicas (`eval`/DSL não confiável).
  3. Padrão Registry com instâncias de Strategies puras e tipadas.
- **Escolha e trade-offs:** **Strategy Pattern + Registry**. Cada validador possui código estável, validação de schema de parâmetros e execução pura e determinística. Validadores inativos são ignorados pelo executor.
- **Impacto sobre pontuação:** Explicabilidade total de recusas, extensibilidade e proteção contra injeção de código.
- **Teste ou evidência:** `backend/tests/test_domain_engine.py` e `qa/test_matriz_casos.py` cobrindo validadores ativos e inativos.
- **Status:** **Aceita**.

---

## ADR-003 — Precisão Decimal Estrita para Cálculos Financeiros

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Financeiro / Domínio)
- **Contexto/restrição oficial:** O cálculo financeiro de antecipação (desconto comercial simples a 2,0% a.m., base 30 dias) e as somas nominais e líquidas exigem exatidão contábil e conformidade regulatória.
- **Alternativas consideradas:**
  1. Tipos primitivos de ponto flutuante (`float`).
  2. Tipo nativo `decimal.Decimal` com arredondamento comercial `ROUND_HALF_UP` (não bancário `ROUND_HALF_EVEN`) a 2 casas decimais por título.
- **Escolha e trade-offs:** **`Decimal` estrito** em todas as operações monetárias, percentuais e de desconto. Proibido o uso de `float`. Arredondamento comercial `ROUND_HALF_UP` aplicado por título individual.
- **Impacto sobre pontuação:** Elimina erros de representação binária e inconsistências de centavos nas simulações e somatórios do lote.
- **Teste ou evidência:** Casos de teste financeiro cobrindo 90 dias a 2% (R$ 5.000,00 $\to$ R$ 4.700,00) e arredondamento comercial em centavos.
- **Status:** **Aceita**.

---

## ADR-004 — Identidade Global do Recebível e Antiduplicidade Global

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Engenharia de Dados / Domínio)
- **Contexto/restrição oficial:** O estoque histórico contém documentos de mesmo número com diferentes vencimentos (parcelas legítimas). Além disso, não se deve permitir a revenda de um título alterando-se apenas o fundo comprador.
- **Alternativas consideradas:**
  1. Chave simples `NUM_DOCUMENTO` ou `DOC_CEDENTE + NUM_DOCUMENTO`.
  2. Chave composta restrita ao fundo atual.
  3. Chave composta global: `DOC_CEDENTE + DOC_SACADO + TIPO_RECEBIVEL + NU_DOCUMENTO + DATA_VENCIMENTO_ORIGINAL` validada contra todo o estoque histórico da base.
- **Escolha e trade-offs:** **Chave composta normalizada com escopo global**. Normaliza pontuação e espaços antes da geração do identificador. Reconhece parcelas distintas e rejeita duplicidades exatas contra todo o estoque histórico global (`DUPLICIDADE_HISTORICA`) e repetições dentro do próprio lote (`DUPLICIDADE_LOTE`).
- **Impacto sobre pontuação:** Prevenção robusta contra fraudes, revenda interfundos e falsos positivos de duplicidade.
- **Teste ou evidência:** Teste com parcelas legítimas (mesmo documento, vencimentos distintos) e teste com duplicatas idênticas contra o estoque global.
- **Status:** **Aceita**.

---

## ADR-005 — Concentração por Raiz de CNPJ e Tratamento de Excesso Histórico

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Risco / Domínio)
- **Contexto/restrição oficial:** O limite de concentração por sacado é de 10,0%, agrupado pela raiz do CNPJ (8 primeiros dígitos). A carteira histórica do ANTECIPE já apresentava um grupo sacado com aproximadamente 12,5% de concentração prévia.
- **Alternativas consideradas:**
  1. Rejeição retroativa dos títulos históricos já adquiridos.
  2. Ignorar o excesso histórico e permitir novas compras até estourar um teto arbitrário.
  3. Preservar o estoque adquirido e recusar novas aquisições para grupos que resultem em concentração estritamente superior a 10,0% ($> 10{,}0\%$).
- **Escolha e trade-offs:** **Premissa técnica documentada**: Os títulos históricos do estoque são preservados como fato consumado; um lote que resulte em concentração de **exatamente 10,0% é aceito** (piso aceito); recusa ocorre estritamente quando a concentração projetada ultrapassa 10,0% ($> 10{,}0\%$).
- **Impacto sobre pontuação:** Decisão de negócio defensável e transparente, sem invalidar o estoque importado.
- **Teste ou evidência:** Testes de domínio e de integração com sacado exatamente em 10,0% (aprovado) e sacados com excesso (recusados).
- **Status:** **Aceita**.

---

## ADR-006 — Tratamento Conservador de Situação Cadastral (NAO_VERIFICADA)

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Conformidade / Risco)
- **Contexto/restrição oficial:** A validação matemática de dígitos verificadores não comprova situação cadastral ativa na Receita Federal.
- **Alternativas consideradas:**
  1. Presumir ativas todas as empresas com CNPJ matematicamente válido.
  2. Consulta a APIs externas públicas não confiáveis em tempo de execução.
  3. Classificação em `ATIVA`, `INATIVA` e `NAO_VERIFICADA`, com inelegibilidade padrão e fonte sintética para demonstração.
- **Escolha e trade-offs:** **Tratamento conservador**. Sacados não verificados em base oficial são classificados como `NAO_VERIFICADA` e recusados pelo fundo. Modo de demonstração controlado pela flag `ENABLE_DEMO_CADASTRO=true`.
- **Status:** **Aceita**.

---

## ADR-007 — Suporte Dual de Banco de Dados: SQLite Local e PostgreSQL

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Infraestrutura)
- **Contexto/restrição oficial:** O ambiente de avaliação inspecionado não possui Docker em execução. O sistema deve ser imediatamente reprodutível localmente.
- **Alternativas consideradas:**
  1. Exigir Docker obrigatório e falhar caso ausente.
  2. SQLite 3 como padrão autossuficiente local com suporte mapeado para PostgreSQL via SQLAlchemy.
- **Escolha e trade-offs:** Padrão local **SQLite 3** com suporte para PostgreSQL via `DATABASE_URL`. Evidências executadas em SQLite; PostgreSQL permanece suportado em código/schemas mas não executado localmente.
- **Status:** **Aceita**.

---

## ADR-008 — Representação Estrita de Valor Nominal em Centavos

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Integridade / Domínio)
- **Contexto/restrição oficial:** Valores nominais com frações além de 2 casas decimais (ex: `100.005`) não podem ser aceitos ou truncados silenciosamente, pois causariam discrepância contábil no cálculo de desconto simples.
- **Decisão:** Contrato de integridade de armazenamento e parsing: qualquer fração não nula além de centavos é estritamente recusada na ingestão como `FORMATO_INVALIDO_VALOR`. Frações nulas (ex: `100.000`) são normalizadas para centavos exatos.
- **Teste ou evidência:** Implementado e validado nos testes unitários e de integração (`test_matriz_casos.py`, `test_domain_engine.py`).
- **Status:** **Aceita (implementada e testada)**.

---

## ADR-009 — Autenticação Institucional (Auth0 + PKCE + Sessão HttpOnly) e Vídeo de Fundo em Camadas

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Segurança, Frontend & Integração)
- **Contexto/restrição oficial:** O portal requer identificação segura do usuário com suporte a SSO Google e credenciais (e-mail/senha) sem expor tokens sensíveis no armazenamento local do navegador nem sobrepor scripts legados, mantendo visual institucional com vídeo de fundo (`video_fundo_login.mp4`) e campos de entrada limpos (sem CNPJ/dados fictícios pré-preenchidos).
- **Decisão:**
  1. **Sessão `HttpOnly` no Servidor (`backend/api/auth_routes.py`):** Troca de código OAuth 2.0 PKCE e validação de sessão centralizadas no backend, emitindo cookie `HttpOnly` / `SameSite=Lax` (`Secure` em HTTPS).
  2. **Políticas Pessoais com Escopo da Própria Conta (`backend/api/policy_routes.py`):** Isolamento por usuário autenticado sem exigir privilégios administrativos globais da Management API.
  3. **Camadas Visuais Isoladas (`z-index`) no Login (`LoginPage.tsx`):** Vídeo de fundo (`video_fundo_login.mp4`) renderizado em camada inferior com *overlay* de contraste (WCAG 2.2 AA) e formulário institucional limpo em camada superior.
- **Teste ou evidência:** Validado em `Codex/antecipe/backend/tests/test_auth_rejection_regression.py`, `test_personal_policies.py` e `test_portal_integration.py`.
- **Status:** **Aceita (implementada e publicada na Vercel)**.

---

## ADR-010 — Transporte de Upload em Streaming WebSocket com Leitor por Cursor e Janelas de 12 MiB

- **Data e autor:** 2026-10-24 — Equipe Antecipe (Escalabilidade & Backend)
- **Contexto/restrição oficial:** Ambientes serverless (como a Vercel) impõem limite de payload por requisição HTTP POST (~4,5 MB), enquanto lotes de 100.000 a 500.000 linhas possuem entre ~18 MB e ~93 MB.
- **Decisão:** Implementado protocolo de upload em streaming sobre WebSocket (`WS /api/simulations/stream` em `backend/api/bulk_routes.py` e `backend/application/stream_upload.py`) com frames de **768 KiB**, janela de controle de fluxo (`ACK`) de **12 MiB** e leitor baseado em **cursor de índice** (eliminando cópias de memória do restante do buffer a cada linha lida).
- **Impacto sobre pontuação:** Reduziu o tempo de upload de 100k linhas de `19,45s` para `8,17s` (**2,38x mais rápido**) e de 500k linhas de `223,72s` para `106,08s` (**2,11x mais rápido**), mantendo 100% de exatidão linha a linha.
- **Teste ou evidência:** `Codex/antecipe/backend/tests/test_upload_capacity.py` e `Codex/antecipe/benchmarks/relatorio_upload_20261024.json`.
- **Status:** **Aceita (implementada e auditada)**.
