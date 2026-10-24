# Matriz de avaliação — 100 pontos máximos

| Critério edital | Peso | O que demonstrar | Artefatos de prova | Estado |
| --- | ---: | --- | --- | --- |
| 5.2.1 Escalabilidade | 35 | Todas as etapas para 100k e 500k linhas e velocidade de processamento | scripts de benchmark, relatório de execução, contagem e validação | A testar |
| 5.2.2 Design e UX | 25 | Clareza das mensagens de recusa, design, criatividade e interface | matriz de mensagens, protótipo/telas e teste de uso | A testar |
| 5.2.3 Organização — filosofia Unix | 20 | Segregação de tarefas e código limpo | diagrama de módulos, CLI, testes, auditoria de qualidade | A testar |
| 5.2.4 Logs e credenciais | 15 | Logs estruturados, nenhum dado do CSV nos logs, nenhum segredo no repositório | `scripts/check_logs.py` com sentinela, amostra sintética e Gitleaks | A testar |
| 5.2.5 Registro de prompts | 5 | Arquivo com todos os prompts usados em ordem cronológica e descrição do que foi feito com cada resposta | `REGISTRO_PROMPTS.md`, auditoria de entradas sem pendência | A testar |

**Não atribuir nota presumida.** O júri define as notas. Nossa meta é evidenciar cada requisito com uma demonstração reproduzível.

## Gatilhos de bloqueio

- Benchmark que executa, mas não valida a saída, **não** demonstra correção.
- Log que contém valor de linha, conteúdo do arquivo CSV, token ou segredo bloqueia submissão.
- Qualquer prompt sem ação final deixa registro incompleto.
- Mensagem genérica de recusa sem causa e próximo passo precisa de revisão.
