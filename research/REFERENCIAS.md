# Pesquisa de agentes, skills e ferramentas — 23/10/2026

## Método da seleção

Foi priorizada a **fonte primária**: repositórios dos autores, documentação oficial de frameworks e normas técnicas. Critérios: aderência ao edital, mantenibilidade, facilidade de integração, escopo, riscos de instalação e documentação. Popularidade é um sinal de adoção, **não uma avaliação independente de desempenho**. Não afirmar que um agente teve melhores resultados de benchmark ou mais avaliações positivas sem teste comparativo documentado.

**Recomendação prática:** usar os 9 agentes deste kit como funções especializadas e adicionar 2–4 skills públicas de alta utilidade; não instalar 200 agentes genéricos de uma vez.

| Origem | Papel no hackathon | Avaliação e escolha | Status no kit |
| --- | --- | --- | --- |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | UX, estilos, design system, acessibilidade | Muito alinhada aos 25 pontos; base pesquisável por domínio/stack; confirmar consistência visual com testes reais | Integração opcional, não copiada |
| [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | Criatividade e acabamento da interface | Complementa UI UX Pro Max; não substitui fluxos de recusa claros | Integração opcional |
| [Vercel Agent Skills](https://github.com/vercel-labs/agent-skills) | Auditoria web e performance React | `web-design-guidelines` é útil mesmo sem stack definido; `vercel-react-best-practices` só se usar React/Next | Integração opcional |
| [Superpowers](https://github.com/obra/superpowers) | TDD, planejamento, depuração, revisão antes da entrega | Metodologia forte e abrangente; pode aumentar overhead em hackathon se usar todas as skills | Recomendada seleção enxuta |
| [wshobson/agents](https://github.com/wshobson/agents) | Catálogo de especialistas para testes, backend, observabilidade | Grande variedade e suporte multicliente; excesso de perfis cria conflito/consumo de contexto. Selecionar por habilidade específica | Catálogo de consulta, sem instalação em massa |
| [github/awesome-copilot](https://github.com/github/awesome-copilot) | Exemplos de agentes e padrões | Comunidade vinculada ao GitHub; relevante se a equipe usar Copilot, não necessário aos dois clientes já configurados | Consulta |
| [Polars](https://docs.pola.rs/user-guide/lazy/execution/) | CSV alto volume | `scan_csv` com engine streaming pode reduzir memória; nem toda transformação comporta streaming; comparar contra alternativa simples | Referência técnica |
| [DuckDB](https://duckdb.org/docs/current/data/csv/overview) | CSV/SQL local e análises | Excelente candidato se regras forem relacionais/SQL; overhead pode ser desnecessário | Referência técnica |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | Credenciais no repositório e histórico | Scanner útil para arquivos atuais e commits; não substitui rotação de credencial comprometida | Ferramenta opcional |
| [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) | Logs seguros | Orienta remoção/sanitização de tokens, senhas e dados sensíveis | Incorporado nas instruções originais |
| [OpenTelemetry Sensitive Data](https://opentelemetry.io/docs/security/handling-sensitive-data/) | Telemetria e filtragem de atributos | Recomenda redução de coleta e redaction de campos sensíveis | Incorporado nas instruções originais |
| [WCAG 2.2 3.3.1](https://www.w3.org/WAI/WCAG22/Understanding/error-identification) | Mensagens de erro | Exige identificação e descrição textual dos erros; base para UX de recusas | Incorporado nas instruções originais |

## Skills públicas para instalar só se fizer sentido

Instale manualmente após revisar conteúdo, licença, scripts e permissões. Os comandos abaixo são **opcionais**; não foram executados neste kit. Necessitam Node/npm, rede e suporte à ferramenta de skills.

```bash
# Design e auditoria web
npx skills add nextlevelbuilder/ui-ux-pro-max-skill --skill ui-ux-pro-max
npx skills add anthropics/skills --skill frontend-design
npx skills add vercel-labs/agent-skills --skill web-design-guidelines

# Processo rigoroso (apenas as duas mais úteis no sprint)
npx skills add obra/superpowers --skill test-driven-development
npx skills add obra/superpowers --skill verification-before-completion

# Somente se o frontend for React/Next
npx skills add vercel-labs/agent-skills --skill vercel-react-best-practices
```

Alternativa nativa para Claude Code, caso prefira plugins: consulte `anthropics/skills` e `obra/superpowers` diretamente nos repositórios. **Não execute instaladores de skills desconhecidas no repositório real sem inspecionar o código.** Não combine dois métodos de instalação da mesma skill sem entender conflitos.

## O que foi adaptado e o que não foi

- Os **9 perfis** e **5 skills** neste pacote foram escritos especificamente para os critérios das imagens; são configurações originais e não cópias de agentes públicos.
- As fontes externas informam métodos, padrões e ferramentas. Seus arquivos não são redistribuídos aqui; dependências opcionais não estão pré-instaladas.
- Não foram medidos benchmarks comparando agentes ou frameworks nem confirmadas avaliações de usuários. Estrelas, instalações e rankings públicos mudam; não use números sem conferir data e metodologia.
- A integração nativa é com Codex CLI e Claude Code. Para OpenCode, Gemini CLI, Cursor e outros clientes, aproveite `agents/*.md` e `AGENTS.md`, mas adapte o formato de configuração e os hooks; não afirme compatibilidade automática.

## Por que não um agente para tudo?

- Performance, UX, logs e segurança têm critérios de prova diferentes; separar os papéis impede revisões superficiais.
- Logging de prompts e dados do CSV têm políticas distintas: registrar comandos ao modelo **não** autoriza vazar dados em logs de aplicação.
- O gargalo de 500k linhas é o software real e o hardware do júri, não a quantidade de agentes. A pontuação depende da execução demonstrável.
- A documentação automática precisa ser conciliada por humano/agente com alterações reais; sem isso o requisito de "o que foi feito com cada resposta" fica apenas parcialmente cumprido.

## Referências de compatibilidade de cliente

- [Codex — subagentes customizados `.codex/agents/*.toml`](https://developers.openai.com/codex/subagents)
- [Codex — hooks de ciclo de vida `.codex/hooks.json`](https://developers.openai.com/codex/hooks)
- [Claude Code — subagents `.claude/agents/*.md`](https://code.claude.com/docs/en/sub-agents)
- [Claude Code — hooks `UserPromptSubmit` e `Stop`](https://code.claude.com/docs/en/hooks)
- [Codex — skills e descoberta](https://developers.openai.com/codex/build-skills)
