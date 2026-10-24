# Registro de Decisões de Arquitetura (ADRs) — Antecipe FIDC

Este documento registra as principais decisões de arquitetura e engenharia adotadas na construção da plataforma do **Antecipe FIDC**, acompanhadas das motivações de negócio, alternativas consideradas e trade-offs assumidos.

---

## Índice das Decisões
- [ADR-001 — Monólito Modular com Execução Local Autossuficiente](#adr-001--monólito-modular-com-execução-local-autossuficiente)
- [ADR-002 — Motor de Regras Configurável Orientado a Strategy e Registry](#adr-002--motor-de-regras-configurável-orientado-a-strategy-e-registry)
- [ADR-003 — Precisão Decimal Estrita para Cálculos Financeiros](#adr-003--precisão-decimal-estrita-para-cálculos-financeiros)
- [ADR-004 — Identidade Global Composta para Antiduplicidade e Parcelas](#adr-004--identidade-global-composta-para-antiduplicidade-e-parcelas)
- [ADR-005 — Concentração por Raiz de CNPJ e Tolerância ao Excesso Histórico](#adr-005--concentração-por-raiz-de-cnpj-e-tolerância-ao-excesso-histórico)
- [ADR-006 — Tratamento Conservador de Situação Cadastral (NAO_VERIFICADA)](#adr-006--tratamento-conservador-de-situação-cadastral-nao_verificada)
- [ADR-007 — Suporte Dual de Banco de Dados: SQLite Local e PostgreSQL](#adr-007--suporte-dual-de-banco-de-dados-sqlite-local-e-postgresql)
- [ADR-008 — Representação Estrita de Valor Nominal em Centavos](#adr-008--representação-estrita-de-valor-nominal-em-centavos)

---

## ADR-001 — Monólito Modular com Execução Local Autossuficiente
- **Status:** Aceita
- **Contexto:** A estação de trabalho local inspecionada dispõe de Python 3.11 e Node 24, porém não dispõe de Docker ativo. Não há conhecimento prévio do ambiente dos avaliadores.
- **Decisão:** Estruturar a solução como um monólito modular (FastAPI no backend e React + Vite no frontend), separando domínio, aplicação, infraestrutura e apresentação em pacotes explícitos.
- **Trade-offs:** Elimina sobrecarga operacional de microserviços e dependência de orquestração externa, assegurando inicialização imediata e auditável no ambiente local.

---

## ADR-002 — Motor de Regras Configurável Orientado a Strategy e Registry
- **Status:** Aceita
- **Contexto:** As regras do fundo estão descritas em `validadores_antecipe.json` e novas regras podem ser ativadas/desativadas sem alteração de código.
- **Decisão:** Implementar validadores como estratégias puras e desacopladas registradas em um Registry. O motor valida os parâmetros através de schemas estritos e ignora validadores inativos.
- **Trade-offs:** Elimina riscos de injeção de código via `eval`, garantindo extensibilidade e explicabilidade clara para cada recusa.

---

## ADR-003 — Precisão Decimal Estrita para Cálculos Financeiros
- **Status:** Aceita
- **Contexto:** A precisão dos centavos na simulação e soma total líquida é crítica para a credibilidade financeira da aplicação.
- **Decisão:** Utilizar `decimal.Decimal` em todas as representações monetárias, taxas e cálculos de desconto comercial simples, aplicando arredondamento comercial `ROUND_HALF_UP` (não bancário `ROUND_HALF_EVEN`) por título individual. Proibido o uso de `float`.
- **Trade-offs:** Elimina qualquer discrepância oriunda da representação em ponto flutuante binário.

---

## ADR-004 — Identidade Global Composta para Antiduplicidade e Parcelas
- **Status:** Aceita
- **Contexto:** O estoque possui documentos de mesmo número com vencimentos distintos (parcelas legítimas). Além disso, não é permitido revender a mesma parcela alterando apenas o fundo comprador.
- **Decisão:** Definir a identidade única como a combinação normalizada:
  `DOC_CEDENTE + DOC_SACADO + TIPO_RECEBIVEL + NU_DOCUMENTO + DATA_VENCIMENTO_ORIGINAL`.
  Validar a duplicidade contra **todo o estoque histórico global** da base (`DUPLICIDADE_HISTORICA`) e dentro da própria remessa (`DUPLICIDADE_LOTE`).
- **Trade-offs:** Reconhece parcelas distintas e previne duplicidade com precisão, impedindo revenda interfundos e garantindo integridade de carteira.

---

## ADR-005 — Concentração por Raiz de CNPJ e Tolerância ao Excesso Histórico
- **Status:** Aceita
- **Contexto:** O limite é de 10,0% por sacado (raiz do CNPJ). A análise do estoque histórico revelou um grupo com 12,5% de exposição prévia.
- **Decisão:** Adotar a premissa de negócio de preservar os títulos já adquiridos no estoque como fato consumado; um lote cuja concentração projetada atinja **exatamente 10,0% é aceito**; recusas ocorrem estritamente quando a concentração projetada ultrapassa 10,0% ($> 10{,}0\%$).
- **Trade-offs:** Decisão defensável e documentada, que protege o fundo sem invalidar a base histórica existente.

---

## ADR-006 — Tratamento Conservador de Situação Cadastral (NAO_VERIFICADA)
- **Status:** Aceita
- **Contexto:** A validação matemática de dígitos verificadores não comprova situação ativa na Receita Federal.
- **Decisão:** O motor classifica a situação cadastral em `ATIVA`, `INATIVA` e `NAO_VERIFICADA`. Na ausência de consulta oficial externa, a política classifica como `NAO_VERIFICADA` e recusa o título. Para fins de demonstração, utiliza-se uma fonte sintética explicitamente identificada como SIMULADA (`ENABLE_DEMO_CADASTRO=true`).
- **Trade-offs:** Transparência com a banca e conformidade com as boas práticas de crédito e regulação.

---

## ADR-007 — Suporte Dual de Banco de Dados: SQLite Local e PostgreSQL
- **Status:** Aceita
- **Contexto:** O ambiente local inspecionado não possui Docker instalado e a configuração da máquina dos avaliadores é desconhecida.
- **Decisão:** Utilizar SQLAlchemy para permitir chaveamento transparente via variável de ambiente `DATABASE_URL`. O padrão local testado e executado é SQLite 3 para funcionamento com zero dependências externas, mantendo suporte mapeado para PostgreSQL.
- **Trade-offs:** Garante reprodutibilidade no ambiente local disponível sem supor instalações externas.

---

## ADR-008 — Representação Estrita de Valor Nominal em Centavos
- **Status:** Aceita (implementada e testada)
- **Contexto:** Valores nominais com frações além de 2 casas decimais (ex: `100.005`) não podem ser aceitos ou truncados silenciosamente, pois geram inconsistência contábil no cálculo do desconto comercial simples.
- **Decisão:** Contrato de integridade de armazenamento e parsing: qualquer fração não nula além de centavos é estritamente recusada na ingestão como `FORMATO_INVALIDO_VALOR`. Frações nulas (ex: `100.000`) são normalizadas para centavos exatos.
- **Trade-offs:** Garante consistência estrita entre o valor de face armazenado e os cálculos de desconto.
