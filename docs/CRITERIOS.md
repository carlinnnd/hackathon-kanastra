# Matriz de avaliação — 100 pontos máximos

| Critério edital | Peso | O que demonstrar | Artefatos de prova | Estado |
| --- | ---: | --- | --- | --- |
| 5.2.1 Escalabilidade | 35 | Todas as etapas para 100k e 500k linhas e velocidade de processamento | `docs/EVIDENCIAS.md`, `Codex/antecipe/benchmarks/run_real_benchmark.py`, `Codex/antecipe/benchmarks/run_http_benchmark.py` e `Codex/antecipe/benchmarks/run_upload_comparison.py` (100k e 500k linhas medidos e confrontados com oráculo) | Verificado (`docs/EVIDENCIAS.md`) |
| 5.2.2 Design e UX | 25 | Clareza das mensagens de recusa, design, criatividade e interface | `docs/MATRIZ_RECUSAS.md`, aplicação publicada em `https://hackathon-kanastra.vercel.app/`, tela de login com vídeo institucional (`video_fundo_login.mp4`), What-If interativo e exportação CSV/PDF | Verificado (`docs/MATRIZ_RECUSAS.md`) |
| 5.2.3 Organização — filosofia Unix | 20 | Segregação de tarefas e código limpo | Segregação estrita em `Codex/antecipe/backend/{domain,application,infrastructure,api}`, CLI Unix (`Codex/antecipe/backend/cli.py`), suíte de domínio (`tests/test_antecipe_domain_suite.py`) e testes de integração (`Codex/antecipe/backend/tests/`) | Verificado (`docs/DECISOES_TECNICAS.md`) |
| 5.2.4 Logs e credenciais | 15 | Logs estruturados, nenhum dado do CSV nos logs, nenhum segredo no repositório | `Codex/antecipe/backend/logger.py` (allowlist estrita), `scripts/check_logs.py` com sentinela, `tests/test_kit.py` e `Codex/antecipe/backend/tests/test_security_r3.py` | Verificado (`scripts/check_logs.py`) |
| 5.2.5 Registro de prompts | 5 | Arquivo com todos os prompts usados em ordem cronológica e descrição do que foi feito com cada resposta | `docs/REGISTRO_PROMPTS.md`, `docs/REGISTRO_PROMPTS_CARLOS.md`, `docs/REGISTRO_PROMPTS_ELIAS.md`, `docs/REGISTRO_PROMPTS_PINA.md` e `python3 scripts/prompt_ledger.py audit` (0 pendências) | Verificado (`docs/REGISTRO_PROMPTS.md`) |

**Não atribuir nota presumida.** O júri define as notas. Nossa meta é evidenciar cada requisito com uma demonstração reproduzível.

## Gatilhos de bloqueio (todos verificados e atendidos)

- Benchmark que executa, mas não valida a saída, **não** demonstra correção $\rightarrow$ Todos os benchmarks em `docs/EVIDENCIAS.md` validam status, motivos e cálculo `Decimal` contra oráculo independente.
- Log que contém valor de linha, conteúdo do arquivo CSV, token ou segredo bloqueia submissão $\rightarrow$ Auditado via `scripts/check_logs.py` e `tests/test_kit.py` (`test_sensitive_log_detection`).
- Qualquer prompt sem ação final deixa registro incompleto $\rightarrow$ Auditado via `python3 scripts/prompt_ledger.py audit` (`Pendências: 0 | Eventos órfãos: 0`).
- Mensagem genérica de recusa sem causa e próximo passo precisa de revisão $\rightarrow$ Todas as recusas mapeadas em `docs/MATRIZ_RECUSAS.md` e `Codex/antecipe/frontend/src/services/rejections.ts` exibem causa objetiva, parâmetro violado e próximo passo acionável.
