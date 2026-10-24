# Hackathon Antecipe — Plataforma de Antecipação de Recebíveis (FIDC)

> **Projeto Desenvolvido:** Plataforma modular de antecipação e simulação de recebíveis para o **ANTECIPE FIDC**.  
> **Acesso rápido à aplicação:** Consulte o guia de execução e arquitetura completo em **[Codex/antecipe/README.md](Codex/antecipe/README.md)**.  
> **Documentação de Requisitos e Evidências:** Especificação oficial em `docs/ESPECIFICACAO.md`, evidências reais em `docs/EVIDENCIAS.md`, decisões em `docs/DECISOES_TECNICAS.md`, matriz de recusas em `docs/MATRIZ_RECUSAS.md` e histórico de prompts em `docs/REGISTRO_PROMPTS_CARLOS.md`.

**Demonstração pública:** [hackathon-kanastra.vercel.app](https://hackathon-kanastra.vercel.app/)  
**GitHub:** [carlinnnd/hackathon-kanastra](https://github.com/carlinnnd/hackathon-kanastra)

A versão pública usa somente uma carteira de **5 títulos sintéticos**, com resultados temporários por instância serverless. **Não envie dados reais.** O estoque privado, o gabarito externo e os bancos locais não fazem parte do deploy. A execução local completa e as limitações de instalação estão documentadas no guia abaixo.

---

## 1. Resumo da Solução Implementada

O sistema foi construído a partir dos requisitos oficiais de negócio e dos dados do edital:
- **Motor de Regras Configurável:** Execução baseada em *Strategy + Registry* sem parâmetros financeiros fixos no código e com suporte a versionamento imutável de políticas carregadas de `validadores_antecipe.json` (configuração pública versionada no Git).
- **Precisão Financeira Estrita:** Cálculo de desconto comercial simples com `decimal.Decimal` (zero uso de `float`), integridade centesimal na face (ADR-008) e arredondamento comercial `ROUND_HALF_UP` nos centavos por nota aprovada (não bancário).
- **Antiduplicidade Global e Parcelas:** Identidade composta única (`DOC_CEDENTE + DOC_SACADO + TIPO_RECEBIVEL + NU_DOCUMENTO + DATA_VENCIMENTO_ORIGINAL`) que reconhece parcelas legítimas e previne duplicidade contra todo o estoque histórico da base (`DUPLICIDADE_HISTORICA`) e intra-lote (`DUPLICIDADE_LOTE`).
- **Controle de Concentração:** Monitoramento determinístico de exposição por raiz de CNPJ do sacado (limite de 10,0% onde $\le 10{,}0\%$ é aceito e $> 10{,}0\%$ é recusado), respeitando o excesso histórico documentado.
- **Processamento Streaming Unix:** Ingestão de alta vazão com baixo uso de memória (pico amostrado < 100 MB em 500k linhas no motor e throughput > 10.000 linhas/s; throughput HTTP de ~3.000 a 3.200 linhas/s com worker real).
- **Interface Web Acessível:** Frontend em React 19 + TypeScript + Vite 8 (porta 3000) com mensagens de recusa explicativas orientadas às diretrizes WCAG 2.2 AA.
- **Ambiente de Execução Local:** Aplicação 100% autossuficiente e testada localmente em SQLite 3; Docker e PostgreSQL não foram executados na máquina host por indisponibilidade de daemon Docker.
- **Separação de Dados:** Arquivo de estoque real privado (`estoque_antecipe.csv`) e arquivo de gabarito externo (`resultado_esperado_100k.json`) mantidos fora do controle de versão do Git, com regras regulamentares (`validadores_antecipe.json`) versionadas como especificação pública.

Para inicializar a aplicação, consulte: **[Guia Completo de Execução (Codex/antecipe/README.md)](Codex/antecipe/README.md)**.

---

# Hackathon Agent Kit — Guia de Infraestrutura e Governança

Pacote de governança, governança de prompts, auditoria estrutural e perfis de agentes preparado para o desafio.

## O que está pronto no Kit
- 9 perfis de agentes em formato nativo Codex (`.codex/agents/*.toml`) e Claude Code (`.claude/agents/*.md`).
- 5 skills locais por competência, disponíveis em `.agents/skills/`.
- Dois hooks de captura de prompts: `UserPromptSubmit` e `Stop`.
- Scripts de auditoria, benchmark e reconciliação contínua de prompts (`scripts/prompt_ledger.py`, `scripts/check_submission.py`).
- Matrizes oficiais de evidências, decisões técnicas e recusas em `docs/`.

## Uso dos Agentes
| Agente | Quando chamar | Principal saída |
| :--- | :--- | :--- |
| `coordenador` | Início, orquestração, integração de frentes | Plano de execução e mapa de evidências |
| `performance` | Pipeline CSV, throughput, memória, latência | Benchmarks de 100k e 500k com oráculo |
| `ux_ui` | Interface web, mensagens de recusa, acessibilidade | Telas React, componentes e WCAG |
| `unix_arch` | Contratos de domínio, CLI Unix, código limpo | Motor modular Strategy + Registry |
| `observabilidade` | Logs estruturados, métricas | Safe JSON logs sem vazamento de CSV/PII |
| `credenciais` | Varredura de segredos, sanitização de ambiente | Auditoria de segurança e .env |
| `prompt_registry`| Rastreamento contínuo de IA | `docs/REGISTRO_PROMPTS_CARLOS.md` reconciliado |
| `qa_criterios` | Validação contra critérios de pontuação | Matriz de testes de negócio e suíte R3 |
| `demo_entrega` | Roteiro de banca e apresentação | Roteiro de 5 minutos e checklist |

## Registro de Prompts e Auditoria Estrutural
- Visualização e status do ledger:
  ```bash
  python scripts/prompt_ledger.py status
  python scripts/prompt_ledger.py audit
  ```
- Auditoria do kit:
  ```bash
  python scripts/check_submission.py
  ```
- Suíte de testes do kit:
  ```bash
  python tests/test_kit.py
  ```
