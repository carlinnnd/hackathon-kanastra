# Rastreabilidade de Prompts de IA — Antecipe FIDC

> **Status:** Índice e ponte documental oficial com os registros cronológicos e auditáveis de prompts de IA.  
> **Fonte oficial de verdade:** `docs/REGISTRO_PROMPTS.md` e `docs/prompts-events.jsonl`.  
> **Registro específico do orquestrador (Carlos):** `docs/REGISTRO_PROMPTS_CARLOS.md`.  
> **Transcrições integrais preservadas:** `.hackathon/prompts/` e `Codex/antecipe/docs/USER_REQUIREMENTS.md`.

---

## 1. Governança e Metodologia de Rastreamento

Em conformidade com a seção 4.1.2 e o critério 5.2.5 do regulamento do hackathon, o projeto adota governança contínua e imutável para todas as interações de inteligência artificial.

Cada evento registrado possui:
- **Identificador Único Sequencial:** Ex: `P0001`, `P0002`, `P0003`.
- **Timestamp UTC Oficial:** Marcado no momento exato do registro.
- **Origem / Autor:** Sessão interativa via hooks nativos (`UserPromptSubmit` e `Stop`) ou inclusão manual auditada.
- **Digest Criptográfico (SHA-256):** Garante a integridade e não-repúdio do texto de entrada original.
- **Sanitização de Segurança:** Remoção de credenciais, dados pessoais e ocultação de linhas tabulares de CSV (`[LINHA_TABULAR_OMITIDA]`).
- **Reconciliação e Verificação:** Cada prompt possui status explícito do que foi feito com a resposta, arquivos afetados e comandos/testes que comprovam a execução.

---

## 2. Trilha Cronológica de Prompts Consolidados

| ID | Data / Hora (UTC) | Origem / Sessão | Objetivo Principal | Arquivos Afetados | Verificação / Prova | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`P0001`** | 2026-10-24T12:45:02Z | user / session-01 | Inicialização do prompt ledger e colocação dos agentes especialistas a postos. | `scripts/prompt_ledger.py` | `python scripts/prompt_ledger.py status; python tests/test_kit.py` | **Reconciliado / Concluído** |
| **`P0002`** | 2026-10-24T13:27:34Z | user / manual | Briefing oficial completo do Antecipe FIDC (regras, estoque, motor, API, UX e prazos). | `docs/ESPECIFICACAO.md`, `Codex/antecipe/docs/EXECUTION_PLAN.md`, `Codex/antecipe/docs/USER_REQUIREMENTS.md` | Em progresso pelas frentes de desenvolvimento (motor, backend, frontend) | **Em Progresso (Honesto)** |
| **`P0003`** | 2026-10-24T13:48:15Z | user / manual | Steering do usuário: direcionamento dos prompts para `docs/REGISTRO_PROMPTS_CARLOS.md`. | `scripts/prompt_ledger.py`, `docs/REGISTRO_PROMPTS_CARLOS.md`, `docs/REGISTRO_PROMPTS.md` | `python scripts/prompt_ledger.py status; python tests/test_kit.py` | **Reconciliado / Concluído** |

---

## 3. Acesso aos Registros Detalhados

Para auditoria completa, consulte os arquivos abaixo:
1. **[Registro Oficial de Carlos (Orquestrador & Frentes)](../../docs/REGISTRO_PROMPTS_CARLOS.md):** Contém a íntegra sanitizada de todas as entradas, prévias de resposta e reconciliações de ações.
2. **[Registro Geral e Índice de Prompts](../../docs/REGISTRO_PROMPTS.md):** Índice central com apontamento para os registros de Carlos, Elias e Pina.
3. **[Requisitos Integrais Sanitizados](USER_REQUIREMENTS.md):** Transcrição documental completa do prompt de requisitos de negócio sem supressão de parágrafos.
