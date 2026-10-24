# Estado de coordenação — Antecipe

Objetivo: plataforma local demonstrável de simulação; regras reais, precisão decimal, carteira histórica, CSV/API/interface equivalentes. Publicação externa e aquisição não autorizadas nesta execução.

## Responsáveis e fronteiras

| Agente | Responsabilidade exclusiva | Estado de coordenação |
|---|---|---|
| d583bd12 (coordenador) | Contratos, plano, estado, verificação e integração; sem escrita de produto | Verificando integração |
| 5c877889 | backend/domain e test_domain | Fontes congeladas após correções e regressão |
| f333df74 | Backend, persistência, API, execução local e Compose; análise isolada do gabarito em qa/expected-results-review.md e compare_expected_results.py | Runtime congelado; análise de compatibilidade do novo arquivo esperado |
| bc5051a0 | frontend | Correções de filtros, explicações e formatação monetária entregues; verificação final no navegador |
| 13e644a2 (continuação de db0d8f21) | Documentação e ledger; scripts/prompt_ledger e tests/test_kit apenas roteamento autorizado | P0002 aberto; fork Gemini preservou contexto após falha de entrega cloud ao agente original |
| 7615806a | qa (exceto security e análise do gabarito) e benchmarks | Motor medido; repetição HTTP para corrigir identificação do processo de memória |
| dcf792b3 | qa/security-review.md e test_security_*; produto somente leitura | 21 verificações independentes passaram |

Nenhuma escrita concorrente no mesmo arquivo autorizada. Sem subagentes aninhados. Todas as novas fontes do projeto ficam em Codex/antecipe; registry individual em docs foi exceção explicitamente indicada pelo usuário. Diretórios de dados, bancos e caches gerados também devem permanecer no projeto e fora do Git.

## Evidências já executadas pelo coordenador

- Inspeção integral do estoque: 100.554 títulos, 18 fundos, 10.621 no ANTECIPE, nominal 53.074.028,00, exposição máxima por raiz 12,5%; sem duplicidade na chave composta proposta.
- Kit: oito testes passaram; check_submission sem --final passou.
- Domínio: 24 testes e, após primeira correção, 33 testes passaram. Isso não substitui revisão adversarial; três casos adicionais de ingestão/precificação foram reproduzidos e devolvidos ao autor.
- QA independente: 20 testes do motor e quatro testes do formatador real de logs passaram. A auditoria HTTP de logs permanece separada.
- Primeira integração `DATABASE_URL=sqlite:///:memory:` com `.venv/Scripts/python -m pytest backend/tests -q --tb=short`: 17 falhas e 36 aprovações. Principal problema identificado: fixture SQLite em memória por conexão/thread e contrato de parsing em transição. Resultado foi entregue aos autores, sem reivindicar API funcional.

## Fluxo de conclusão

1. Estabilizar domínio e backend; autores executam regressão e notificam QA/revisor.
2. Importar estoque real no banco local privado e conferir agregados; verificar repetição/rollback.
3. Medir motor e fluxo completo com 100k e 500k, sem extrapolar métricas entre camadas.
4. Navegador: upload, resumo, recusa, filtros, paginação, responsividade e API consistente.
5. Revisão independente final pelo Gemini 3.8 Flash via OMP, conforme nova instrução explícita do usuário. Reproduzir também os achados históricos da auditoria crítica anterior.
6. Corrigir achados pelos autores; verificar README do zero, fechar P0002 com resultados reais e executar auditorias finais.

## Políticas e limitações

- Escrita de produto pelo coordenador: zero. Todos os módulos de produto e correções atribuídos a autores independentes. Artefatos de coordenação escritos diretamente.
- R3: upload, administração e informações cadastrais; revisão independente e rechecagem crítica. R2: persistência/versionamento. A instrução mais recente do usuário substitui a seleção anterior: todos os subagentes devem usar somente Gemini 3.8 Flash via OMP. Não abrir novas sessões Sol ou Kimi. A frase sobre substituir Sol 5.6 por Sol 6.1 terminou em “quando”; condição ainda não informada, sem alteração do guia global.
- Skills do coordenador na inspeção: orchestrator-control-plane, memory-recall, prompt-evidence-ledger; subagent-memory-brief consultada para contexto mínimo. Fase de memória concluída, sem busca externa de memória necessária. Máximo quatro simultâneas.
- Catálogo: manifest 3.0.0, 35 definições presentes no espelho; 48 descobertas no runtime incluindo extras. Hash de definições: c8cfd7f9cecf5b1f9088e8ad81452f29ebd21776f426b62f62e5aa115b1d6d32.
- Docker não instalado e PostgreSQL não verificado. Comando Python neste Windows é python, sem alias python3.
- Foi realizado apenas fetch do Git remoto. Não houve autorização para descartar arquivos, reescrever histórico, commit, push ou publicação. Preservar alterações e staging feitos pelo usuário.
- Algumas chamadas de colaboração foram recusadas por ausência de cloud verdict; foi criada nova sessão independente de segurança e a atribuição finalmente foi confirmada. Não confundir tentativa recusada com tarefa executada.

## Atualização verificável de 24/10/2026 — fase final

- O coordenador executou `pytest backend/tests qa -q --tb=short`: 113 aprovações em 11,72 s, com um aviso de depreciação Starlette/AnyIO. Nenhuma falha.
- Navegador real: demo de nove itens, um aprovado, oito recusados e líquido 4.700,00; cabeçalho inválido apresenta erro e remove resultado anterior; filtro VALOR_MINIMO retorna uma nota após correção de códigos. Paginação e última versão das explicações ainda em verificação.
- Motor: relatórios com oráculo por linha e hashes de fontes iguais antes/depois. HTTP: primeira rodada validou decisões persistidas, mas a memória de 4,41 MB mediu o launcher do venv Windows. Essa medição foi rejeitada; QA deve medir o worker Python efetivo e repetir os dois volumes. Não usar essa memória como evidência de eficiência.
- Git: em cópia de integração separada, branch `antecipe/integracao-validada`, `git pull --ff-only origin main` executado com sucesso: 0e31b3e → e0c5349. Remoto trouxe atualizações dos registros da equipe. Diretório original permanece master sem commit e com staging do usuário preservado. Integração das fontes locais na cópia atualizada ainda em andamento; nenhum commit/push/deploy.
- Novo arquivo do usuário: `resultado_esperado_100k.json`, SHA-256 `a5e0de969c0cf9d1f37aeea0100d7a4a2ba663da24c1641977f7a68934bc1ae8`. Possui 100.554 resultados, 85.215 aprovados e 15.339 barrados; todos os pares linha/documento coincidem com o CSV histórico. Compatibilidade com cadastro, estoque e concentração está em análise. Não transformar títulos históricos em aquisições novas nem desabilitar proteções para forçar o gabarito.

## Corte final de escopo — base local

Esta atualização substitui os estados de trabalho anteriores: o usuário priorizou liberar a base e continuar melhorias e testes manuais depois. Não executar novas baterias de escala nem ampliar testes automaticamente. `diferenciais.md` é backlog, não autorização para adicionar scanner, what-if ou aquisição.

- Capacidade monetária individual e cumulativa corrigida e validada por seis testes do autor e dois cenários independentes críticos. Preservação de centavos, rollback após chunk e estoque existente conferidos.
- Demo atualizada em `http://127.0.0.1:3000/`, backend em `http://127.0.0.1:8000`; cadastro `SIMULADO_DEMO`. Smoke HTTP de nove itens: um aprovado, oito recusados, líquido `4700.00`. Frontend local passou em test, lint e build.
- Instalação limpa do frontend não aprovada. Registry npm retornou 403 e cache incompleto; lockfile final gerado offline difere das dependências usadas no build local. Não afirmar execução do zero.
- Relatórios de escala anteriores são históricos, sem nova medição após a última correção.
- Pull até `e0c5349` realizado em cópia separada e fontes permitidas integradas sem commit. Índice original e registros remotos de Elias/Pina preservados. Sem push ou deploy externo.
- `P0011` registra a redução de testes. `P0002` fechado como entrega de base local com limitações explícitas. Auditoria: 11 prompts, nenhuma pendência de reconciliação e nenhum evento órfão.
- Próximo ciclo: instalação limpa e testes manuais incrementais antes de selecionar diferenciais. PostgreSQL/Compose e Gitleaks continuam sem verificação neste ambiente.

## Publicação posterior autorizada

- O usuário autorizou commit/push e atualização Vercel; `P0012` registra o pedido. `main` recebeu a base e a adaptação de deploy, com pull antes do envio e merge da atualização de Elias. Índice original preservado.
- Site: `https://hackathon-kanastra.vercel.app`; GitHub: `https://github.com/carlinnnd/hackathon-kanastra`.
- Demo pública em Python 3.12 com cinco títulos sintéticos e SQLite temporário, sem dados reais ou banco persistente. Bundle pré-compilado validado em árvore controlada; instalação npm limpa continua sem comprovação.
- A primeira build não resolveu o manifesto `-r`; corrigido para pins planos de runtime. O primeiro filtro público encontrou outra instância sem a simulação; corrigida a visualização em memória somente para respostas completas. Respostas parciais avisam e bloqueiam consultas adicionais. API GET entre instâncias continua sem garantia de persistência.
- Deploy final `dpl_Cj1UA5ksJt3pAgFLGT3uM8CasH27` confirmado READY. Smoke final: nove notas, uma aprovação, oito recusas e líquido `4700.00`; filtro oito e restauração nove sem GET por ID ou alerta de erro. Aviso sintético/temporário visível.
- Sem novas rodadas de escala. Próximo ciclo continua sendo testes manuais incrementais e decisão explícita sobre persistência antes de uso com dados reais.
