# Roteiro de Demonstração e Apresentação aos Jurados — Antecipe FIDC

> **Tempo previsto:** 5 minutos.  
> **Objetivo:** Demonstrar aos jurados a plataforma funcional de antecipação de recebíveis, com ênfase na precisão das regras financeiras, clareza das mensagens de recusa, prevenção de duplicidades, explicabilidade e robustez da arquitetura.

---

## 1. Preparação Prévia (Checklist de Prontidão)

1. **Servidor Backend em execução (Safe JSON / sem access log padrão):**
   ```bash
   # A partir de Codex/antecipe:
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
   ```
2. **Servidor Frontend em execução:**
   ```bash
   # A partir de Codex/antecipe/frontend:
   npm run dev
   ```
3. **Acesso à aplicação:** Abrir o navegador no endereço `http://localhost:3000`.
4. **Documentação interativa da API:** Swagger acessível em `http://127.0.0.1:8000/docs`.
5. **Arquivo de demonstração pronto:** Download via link direto na interface ou pelo endpoint `GET /api/demo.csv`.

---

## 2. Roteiro Passo a Passo (5 Minutos)

### Minuto 1: Contexto de Negócio e Arquitetura do Produto
- **Fala:** "Apresentamos a plataforma de simulação de antecipação de recebíveis do ANTECIPE FIDC. A solução foi desenhada como um monólito modular limpo em Python e React, com processamento em streaming Unix, motor de regras configurável (*Strategy + Registry*) e precisão financeira estrita em `Decimal` (zero uso de float)."
- **Tela:** Tela inicial do portal exibindo o resumo do fundo: 10.621 títulos na carteira histórica, R$ 53,07 milhões nominais e versão ativa das regras carregada a partir de `validadores_antecipe.json`.

### Minuto 2: Ingestão e Processamento do Lote de Demonstração
- **Ação:** Clicar em "Baixar CSV de Exemplo" e submeter o arquivo via formulário/drag & drop na interface.
- **Fala:** "O lote de demonstração contém 9 títulos representativos que cobrem a esteira completa: títulos elegíveis, limites de prazo, valores mínimos, modalidades não aceitas e duplicidades."
- **Tela:** O sistema processa o arquivo em streaming imediato e exibe os totalizadores:
  - Total de recebíveis submetidos: 9.
  - Resultado objetivo da política: **1 aprovado e 8 recusados**.
  - Total líquido aprovado para antecipação: **R$ 4.700,00** (calculado sobre o título elegível de R$ 5.000,00).

### Minuto 3: Explicabilidade e UX de Recusas (WCAG 2.2 AA)
- **Ação:** Utilizar os filtros da tabela para inspecionar os títulos recusados e expandir os detalhes de linha.
- **Destaque:** Demonstrar que as mensagens orientam o usuário com clareza e próximos passos acionáveis, sem jargões:
  - *Prazo Máximo:* Explicita a quantidade de dias excedentes frente ao teto de 180 dias.
  - *Valor Mínimo:* Detalha quando o valor de face é inferior a R$ 100,00.
  - *Tipo de Recebível:* Informa que o fundo aceita apenas Duplicatas e Duplicatas de Serviço.
  - *Situação Cadastral:* Trata com transparência a regra conservadora de inelegibilidade para sacados com situação `NAO_VERIFICADA`.

### Minuto 4: Prevenção de Duplicidades e Precisão Financeira Comercial
- **Ação:** Comparar o título aprovado com as recusas por duplicidade histórica e intra-lote.
- **Fala:** "Nossa proteção antiduplicidade é global: utiliza chave composta normalizada (`DOC_CEDENTE + DOC_SACADO + TIPO_RECEBIVEL + NU_DOCUMENTO + DATA_VENCIMENTO_ORIGINAL`). Ela reconhece parcelas legítimas com vencimentos distintos e impede fraudes contra todo o estoque histórico da base (`DUPLICIDADE_HISTORICA`) e repetições na mesma remessa (`DUPLICIDADE_LOTE`)."
- **Demonstração do Cálculo:** Demonstrar a nota aprovada (R$ 5.000,00 nominais com vencimento em 90 dias a taxa de 2,0% a.m.), gerando exatamente **R$ 4.700,00 líquidos** através do desconto comercial simples com arredondamento comercial `ROUND_HALF_UP` nos centavos.

### Minuto 5: Governança de Regras via API, Ledger e Encerramento
- **Ação:** Abrir o Swagger em `http://127.0.0.1:8000/docs` e demonstrar os endpoints de versionamento imutável de regras (`GET /api/rules` e `POST /api/rules/versions`).
- **Fala:** "A parametrização do fundo é 100% desacoplada de código: cada versão de regras possui hash criptográfico SHA-256 e justificativa imutável. Toda a esteira de desenvolvimento foi governada e auditada no ledger de prompts (`docs/REGISTRO_PROMPTS_CARLOS.md`), com 113 testes automatizados passando e comprovação de performance de mais de 10.000 linhas por segundo no motor de streaming."
- **Fechamento:** "A aplicação está autossuficiente, auditada e pronta para avaliação da banca."
