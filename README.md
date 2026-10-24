# Hackathon Agent Kit — guia de início

Pacote preparado a partir dos critérios 4.1.2 e 5.2 das imagens do edital. Idioma de operação: português do Brasil. Atualizado em 23/10/2026.

## O que está pronto

- 9 perfis de agentes, cada um em formato nativo Codex (`.codex/agents/*.toml`) e Claude Code (`.claude/agents/*.md`).
- 5 skills locais por competência, disponíveis para Codex em `.agents/skills/` e Claude em `.claude/skills/`.
- Dois hooks de captura de prompts: `UserPromptSubmit` e `Stop`. Nenhum hook instala dependências nem envia informações para serviços externos.
- Ferramentas Python sem dependências externas: registro de prompts, gerador de CSV sintético, benchmark e auditoria final.
- Matrizes para recusa, evidências, decisões e rastreabilidade.

**Isto é uma infraestrutura de trabalho, não uma solução pronta para o desafio.** O enunciado técnico completo, o schema do CSV, os motivos obrigatórios de recusa e o hardware oficial ainda precisam ser inseridos. Não declarar pontos ganhos nem performance antes da execução real.

## Instalação rápida

Requisitos: Git, Python 3.11+ (para executar também os testes incluídos) e Codex CLI **ou** Claude Code. Node/npm é opcional, apenas para instalar skills públicas adicionais. Os scripts principais usam somente a biblioteca padrão Python e os hooks usam `fcntl` (macOS/Linux/WSL; Windows puro requer adaptação).

1. Extraia a pasta e copie **todo o conteúdo interno**, incluindo os diretórios ocultos `.codex`, `.claude` e `.agents`, para a raiz do **novo repositório** do hackathon. Não sobrescreva arquivos preexistentes sem revisar o diff.
2. Se houver `.gitignore`, `AGENTS.md`, `CLAUDE.md` ou configurações de hooks anteriores, faça merge manual. Não substitua hooks de terceiros inadvertidamente.
3. Abra Codex CLI ou Claude Code na raiz do projeto. Em Codex, execute `/hooks` e **revise/autorize** os hooks do projeto; eles não rodam em projetos não confiáveis. Em Claude Code, confira as configurações do projeto e a confiança no workspace.
4. Peça ao coordenador: `Analise os critérios de docs/CRITERIOS.md, leia o enunciado e distribua tarefas entre os agentes. Comece pelo processamento de 100 mil e 500 mil linhas.`
5. Registre as regras oficiais em `docs/ESPECIFICACAO.md` e os critérios de cada recusa em `docs/MATRIZ_RECUSAS.md` **antes** de implementar.

## Uso dos agentes

| Agente | Quando chamar | Principal saída |
| --- | --- | --- |
| `coordenador` | Início, mudança de escopo, antes da entrega | Plano e mapa de evidências |
| `performance` | Pipeline CSV, throughput, memória, latência | Benchmarks de 100k/500k e gargalos |
| `ux_ui` | Interface, feedback de processamento, recusas | Fluxo, estados e testes de clareza |
| `unix_arch` | Interfaces de módulos, CLI, código limpo | Estrutura e contratos de componentes |
| `observabilidade` | Logs, métricas, rastreabilidade | JSON logs sem conteúdo do CSV |
| `credenciais` | Segredos, .env, histórico Git, sanitização | Auditoria de vazamentos e correções |
| `prompt_registry` | Cada interação e auditoria do histórico | `docs/REGISTRO_PROMPTS.md` reconciliado |
| `qa_criterios` | A cada marco e antes da submissão | Matriz de pontuação com evidências |
| `demo_entrega` | Reta final | Roteiro de demonstração verificável |

Você pode invocar os agentes nominalmente na conversa; são perfis disponíveis para **delegação pelo agente principal**, e não processos que iniciam sozinhos. Múltiplos agentes escrevendo o mesmo arquivo simultaneamente causam conflito. O coordenador atribui propriedade de arquivos e integra os resultados.

## Registro de prompts — obrigatório

Em Codex ou Claude Code, os hooks tentam registrar toda submissão interativa e a última resposta. Os eventos sanitizados ficam em `docs/prompts-events.jsonl` (fonte de verdade, versionável) e geram `docs/REGISTRO_PROMPTS.md` com horário, origem, texto do prompt sanitizado e hash SHA-256 do texto original. A ação efetivamente tomada fica `PENDENTE` até reconciliação. Isso é intencional: uma resposta do modelo **não prova** que um arquivo foi alterado.

```bash
python3 scripts/prompt_ledger.py status
python3 scripts/prompt_ledger.py close --id P0001 --action "Criado parser streaming e testado" --files "src/processor.py,tests/test_processor.py" --verification "pytest: 12 testes passaram"
python3 scripts/prompt_ledger.py audit
```

Para ChatGPT, IDEs ou agentes sem hook, use captura manual com arquivo local, **não texto sensível na linha de comando**:

```bash
python3 scripts/prompt_ledger.py manual --source chatgpt --prompt-file pedido.txt
python3 scripts/prompt_ledger.py close --id P0002 --action "Ação executada" --verification "Comando/evidência"
```

Os prompts podem ser sanitizados (segredos, dados pessoais e linhas de CSV). O hash mantém vínculo com o texto de entrada sem salvar a versão sigilosa. **Não informe dados sensíveis em prompts.** Os hooks dependem de confiança e do cliente; confira `status` a cada sessão e faça a entrada manual se um deles não disparar. Não presumir captura retroativa. Revise e versiona **ambos** os arquivos de `docs/` após cada sessão; sincronize o repositório antes de trabalhar em outra máquina.

Subprompts trocados entre agentes podem não acionar `UserPromptSubmit`; o coordenador deve registrá-los manualmente se fizerem parte do histórico exigido pelo regulamento. O histórico publicado exige revisão humana antes do commit, pois nenhuma sanitização automática é infalível.

Se o relatório mostrar `Eventos órfãos` (uma resposta foi capturada sem o prompt correspondente), registre o prompt faltante com `manual`, feche-o com `close` e explique a reconciliação com `python3 scripts/prompt_ledger.py resolve-orphan --id O0001 --reason "Prompt recuperado em P0005"`. Não descarte o evento silenciosamente.

## Benchmark

```bash
python3 scripts/generate_fixture.py --rows 100000 --output .hackathon/datasets/teste-100k.csv
python3 scripts/generate_fixture.py --rows 500000 --output .hackathon/datasets/teste-500k.csv
python3 scripts/benchmark.py --help
```

Quando existir um processador com CLI, um exemplo de integração **a adaptar** é:

```bash
python3 scripts/benchmark.py --rows 100000 500000 --runs 3 --command "python3 -m app.cli --input {input} --output {output}"
```

Esse comando de exemplo não funcionará até existir `app.cli`. O benchmark mede tempo e taxa, mas não prova sozinho que cada regra de negócio foi aplicada. Testes de correção e inspeção dos relatórios são indispensáveis.

Para testar vazamento em logs, inclua uma sentinela **fictícia** de `generate_fixture.py` num arquivo de teste, rode o processamento e inspecione os logs JSONL gerados pelo projeto:

```bash
python3 scripts/check_logs.py caminho/dos/logs.jsonl --sentinel FAKE_ONLY_00000001
```

O verificador exige `timestamp`, `level` e `event`, checa uma allowlist de campos e falha se a sentinela aparecer. O schema pode ser estendido após revisão. Rode também `gitleaks dir .` e `gitleaks git .` **se o Gitleaks estiver instalado**, além de revisar os achados e rotacionar qualquer credencial efetivamente comprometida.

## Checklist de entrega

1. 100k e 500k concluídos em máquina e ambiente documentados; três execuções, p50 e p95 ou medições individuais, e contagem validada.
2. Para cada recusa, código e texto compreensível, ação possível e teste de acessibilidade.
3. Módulos pequenos, responsabilidades separadas, contratos estáveis, testes unitários e de integração.
4. Logs JSON em formato consistente sem valores/linhas do CSV; verificação de tokens e segredos, incluindo histórico Git.
5. Registro de todos os prompts realmente usados, em sequência, com ação, arquivos e verificação por resposta.
6. Evidência em `docs/EVIDENCIAS.md` e rubric em `docs/CRITERIOS.md` sem notas autoconcedidas.

Auditoria estrutural local: `python3 scripts/check_submission.py`. Auditoria final mais rigorosa: `python3 scripts/check_submission.py --final` (falhará até preencher a especificação e registrar as interações).

Veja `research/REFERENCIAS.md` para projetos públicos pesquisados, vantagens, ressalvas e instalação opcional. Consulte a licença de cada projeto e leia os scripts antes de habilitar terceiros.
