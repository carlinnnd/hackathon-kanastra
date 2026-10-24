# Evidências de execução — Antecipe FIDC

> **Status:** Registro factual e auditável de testes, inspeções e medições executadas no projeto.  
> **Diretriz de integridade:** Apenas medições reais e comandos efetivamente executados são documentados. Requisitos em fase de desenvolvimento ou integração permanecem explicitamente marcados como `EM PROGRESSO` ou `PENDENTE`.

---

## 1. Tabela Principal de Evidências

### 1.1. Resumo Consolidado de Execução e Testes

- **Integridade e Não-Duplicidade do Estoque:**
  - *Ambiente / Comando:* Inspeção via script de auditoria no `estoque_antecipe.csv` (100.554 linhas).
  - *Resultado:* 100.554 registros analisados; 0 duplicidades pela chave composta; 18 fundos; ANTECIPE com 10.621 registros e R$ 53.074.028,00 nominais.
  - *Artefato:* SHA-256 `313c75f4147e1e851eaaefd15dc035aa895c961434da1a91024fd0764559c2f1`.
  - *Verificado por:* Coordenador / Inspecionado.

- **Instalação Limpa do Backend em Ambiente Isolado (Clean Venv):**
  - *Ambiente / Comando:* Criação de virtualenv limpo em `Codex/antecipe/.data/verification/clean-venv` e instalação via `clean-venv/Scripts/python.exe -m pip install -r Codex/antecipe/requirements.txt` sob Python 3.11.15.
  - *Resultado:* Instalação concluída com código de saída 0. Execução de `clean-venv/Scripts/python.exe -m pip check` retornou: `"No broken requirements found."`.
  - *Verificado por:* Coordenador / Verificação de reprodutibilidade limpa.

- **Auditoria de Dependências e Instalação do Frontend:**
  - *Ambiente / Comando:* Execução de `npm ci` a partir do zero no diretório `Codex/antecipe/frontend`.
  - *Resultado:* A execução inicial de `npm ci` falhou (código 1) devido a conflito de resolução entre `@types/node` (resolvido `26.1.2` vs especificação `^22.13.0` no manifest) e bloqueio de rede HTTP 403 na busca de metadados do registro.
  - *Ressalva Factual:* A tentativa seguinte com um lockfile de outro monorepo foi interrompida (código 15); esse arquivo foi rejeitado. Um closure reduzido também falhou com `EUSAGE` por dependências transitivas ausentes. O lockfile final foi gerado pelo próprio npm offline, mas a instalação completa não foi comprovada: houve HTTP 403 no registry e `ENOTCACHED` no cache. `npm ci --dry-run` não comprova instalação. A versão base local usa a árvore controlada já funcional, sem alegar execução do zero.
  - *Verificado por:* Coordenador / Auditoria de instalação.

- **Auditoria de Segurança e Varredura de Segredos:**
  - *Ambiente / Comando:* Tentativa de execução do binário `gitleaks` retornou `"command not found"` no ambiente host.
  - *Mitigação Executada:* Varredura de segurança alternativa via script com 4 padrões de regex cobrindo 137 arquivos do projeto: zero ocorrências de credenciais, tokens ou dados sensíveis encontrados.
  - *Ressalva de Governança:* A ausência de achados na varredura local por regex não constitui garantia absoluta ("segurança assegurada"), mas comprova a aplicação diligente dos controles de segurança possíveis no ambiente.
  - *Verificado por:* Coordenador / Revisor de Segurança.

- **Suíte Estrutural do Kit de Agentes:**
  - *Comando:* `python tests/test_kit.py`
  - *Resultado:* 8 testes executados com 100% de sucesso (0.55s).
  - *Verificado por:* Prompt Registry.

- **Auditoria Estrutural de Conformidade:**
  - *Comando:* `python scripts/check_submission.py`
  - *Resultado:* "Auditoria do kit: OK" (perfis, hooks e skills íntegros).
  - *Verificado por:* QA / Scripts.

- **Suíte Integrada Unificada (Backend, Motor, QA e R3 Segurança):**
  - *Comando:* `.\.venv\Scripts\python.exe -m pytest backend/tests qa -q` (a partir de `Codex/antecipe`)
  - *Resultado histórico, anterior à última correção monetária:* **113 testes aprovados** em 11,72s, com um aviso de depreciação. Não representa nova execução da suíte completa sobre a versão base atual.
  - *Cobertura:* Inclui 21 testes na suíte R3 de segurança (`test_security_r3.py`), matriz QA de casos de negócio (20 casos), testes de endpoints REST, motor de regras configurável e integridade centesimal ADR-008.
  - *Limite Monetário Atual:* Teto técnico de R$ 9.999.999.999.999,99 por título, por total de simulação e no saldo acumulado por fundo em importações consecutivas, sem migração de schema. Acima do teto individual: `VALOR_EXCEDE_CAPACIDADE`, nominal indisponível (`null`). Acima do total: HTTP 422 `TOTAL_EXCEDE_CAPACIDADE` e rollback completo. SQLite/SQLAlchemy pode converter internamente para float; a faixa suportada preserva centavos nos roundtrips testados.
  - *Verificado por:* Coordenador / QA Independente / Revisor de Segurança Gemini.

- **Auditoria de Interface Web no Navegador (Browser Demo Real):**
  - *Resultado:* Simulação completa com lote real de 9 itens resultou em **1 aprovado e 8 recusados**, total líquido de **R$ 4.700,00** (desconto de 90 dias a 2% a.m. sobre R$ 5.000,00 nominais).
  - *Comportamento de Erro:* Submissão de CSV com cabeçalho inválido foi imediatamente recusada e o estado anterior da tela foi devidamente limpo.
  - *Acessibilidade e Console:* Console do navegador 100% limpo (zero erros de runtime JavaScript), mensagens com formatação de moeda em BRL estrita e preservação de valores ricos da API.
  - *Verificado por:* Coordenador / Auditoria via Playwright / Browser REPL.

- **Rastreabilidade e Governança de Prompts:**
  - *Comando:* `python scripts/prompt_ledger.py status`
  - *Resultado final da versão base local:* 11 prompts reconciliados, incluindo `P0011` (redução de testes) e fechamento de `P0002` com as limitações da entrega local explicitadas. `python scripts/prompt_ledger.py audit`: 0 pendências e 0 eventos órfãos. Isso comprova reconciliação do registro, não aprovação das funcionalidades adiadas.
  - *Artefatos:* `docs/REGISTRO_PROMPTS_CARLOS.md`, `docs/REGISTRO_PROMPTS.md`, `docs/prompts-events.jsonl`.
  - *Verificado por:* Prompt Registry.

---

## 2. Benchmarks de Escalabilidade e Throughput

### 2.1. Benchmark do Motor de Domínio e Streaming (Comprovação Semântica com Oráculo)

Executado via `Codex/antecipe/.venv/Scripts/python Codex/antecipe/benchmarks/run_real_benchmark.py` no ambiente oficial (`Windows-10-10.0.26300-SP0 | Python 3.11.15 | Intel64`).  
Todas as decisões foram confrontadas linha a linha contra um **oráculo independente**, validando status de aprovação, primeiro motivo de recusa, cálculo Decimal HALF_UP e projeção acumulada da carteira.

#### Histórico da Rodada 1:
- **100.000 linhas:** 11,13s | Throughput: 8.986,10 linhas/s | RSS Amostrado Pico: 36,58 MB | Aprovados: 1.890 / Recusados: 98.110 | Nominal: R$ 1.874.852,00 / Líquido: R$ 1.838.604,87
- **500.000 linhas:** 50,29s | Throughput: 9.941,40 linhas/s | RSS Amostrado Pico: 92,32 MB | Aprovados: 1.890 / Recusados: 498.110 | Nominal: R$ 1.874.852,00 / Líquido: R$ 1.838.604,87

#### Última Rodada Oficial Auditada (`Codex/antecipe/benchmarks/relatorio_benchmark_real.json`):
- **Cenário 100.000 linhas:**
  - **Status Semântico:** `APROVADA_COM_SUCESSO` (Oráculo independente confrontando 100% das linhas: aprovação, primeiro motivo de recusa e cálculo Decimal).
  - **Duração da Ingestão e Avaliação:** `9,208s`
  - **Throughput:** `10.860,13 linhas/s`
  - **Memória RSS Amostrada (Pico a cada 5k linhas):** `36,80 MB`
  - **Memória RSS do Sistema Operacional (Pico Win32):** `36,80 MB`
  - **Decisões Auditadas:** 1.890 Aprovados | 98.110 Recusados (avaliação determinística do 1º motivo)
  - **Total Nominal Aprovado:** R$ 1.874.852,00 | **Total Líquido Aprovado:** R$ 1.838.604,87
  - **SHA-256 CSV Entrada:** `2bd449c5ade5017d1e575f3c709997589f63ba87072bb935c9f99c40c4aed165`
  - **Hash Determinístico das Decisões de Saída:** `abc3534c6c662b01f8ef05d94346db00d47a18c79383b55adda22c43163c3330`

- **Cenário 500.000 linhas:**
  - **Status Semântico:** `APROVADA_COM_SUCESSO` (Oráculo independente confrontando 100% das linhas: aprovação, primeiro motivo de recusa e cálculo Decimal).
  - **Duração da Ingestão e Avaliação:** `45,3718s`
  - **Throughput:** `11.020,05 linhas/s`
  - **Memória RSS Amostrada (Pico a cada 5k linhas):** `92,52 MB`
  - **Memória RSS do Sistema Operacional (Pico Win32):** `92,52 MB`
  - **Decisões Auditadas:** 1.890 Aprovados | 498.110 Recusados (avaliação determinística do 1º motivo)
  - **Total Nominal Aprovado:** R$ 1.874.852,00 | **Total Líquido Aprovado:** R$ 1.838.604,87
  - **SHA-256 CSV Entrada:** `4988b1c7f6fcf4cc43d80957f92cb4829b5b2f3f5278d11418bc7ce125b39a58`
  - **Hash Determinístico das Decisões de Saída:** `0e301a8551805cff6c710e2dbf8ca4e4231b68db8e6eedea1ed38a860e6be6fa`

### 2.2. Benchmark HTTP End-to-End Oficial Auditado (Upload Multipart + API + Persistência)

Executado pelo QA Independente via `Codex/antecipe/benchmarks/run_http_benchmark.py` com rastreamento nativo e auditado do **PID real do worker Uvicorn** (`relatorio_benchmark_http.json`), corrigindo o viés da medição preliminar que capturava o launcher Windows:

- **Cenário 100.000 Linhas (End-to-End HTTP + Banco de Dados):**
  - **Status Semântico:** `APROVADA_COM_SUCESSO` (Oráculo independente e auditoria SQL direta).
  - **Duração HTTP Total:** `30,8496s`
  - **Throughput HTTP:** `3.241,54 linhas/s`
  - **Pico de Memória RSS do Worker Uvicorn (PID real 4548):** `120,90 MB` (saída de 77,18 MB para 102,97 MB).
  - **Auditoria SQL e Paginação:** 0,78s (SQL) e 0,66s (paginação).
  - **Totais Auditados:** 11.557 aprovados | 88.443 recusados.
  - **Total Nominal:** R$ 114.950.000,00 | **Total Líquido Aprovado:** R$ 13.011.875,59.
  - **Hash Determinístico do Banco de Dados:** `66ebe6bb311704c973cd4760285096c54f2519e4a210c43be13be48d58ebbd7a`.
  - **CSV SHA-256:** `d904d5302ca15bd1957f4e8bb4728cb63b237a0b2386804683b5ffdc372adea8`.

- **Cenário 500.000 Linhas (End-to-End HTTP + Banco de Dados):**
  - **Status Semântico:** `APROVADA_COM_SUCESSO` (Oráculo independente e auditoria SQL direta).
  - **Duração HTTP Total:** `166,7215s`
  - **Throughput HTTP:** `2.999,01 linhas/s`
  - **Pico de Memória RSS do Worker Uvicorn (PID real 4548):** `172,49 MB` (saída de 102,66 MB para 119,66 MB).
  - **Auditoria SQL e Paginação:** 3,84s (SQL) e 3,16s (paginação).
  - **Totais Auditados:** 11.557 aprovados | 488.443 recusados.
  - **Total Nominal:** R$ 574.750.000,00 | **Total Líquido Aprovado:** R$ 13.011.875,59.
  - **Hash Determinístico do Banco de Dados:** `7899846e9d4e68346ce8802fb11a9f1403099409ac85e0289e468b788273c7f2`.
  - **CSV SHA-256:** `a17431d42169eee4a9da0e0507b33d3697dcc6f5c021dde083b02512fa8435ba`.

- **Transparência Técnica:**
  - A medição de ~4,41 MB reportada na rodada preliminar referia-se estritamente ao launcher Windows wrapper (`python.exe`), sem refletir o consumo de memória do worker da aplicação. Os números oficiais e auditáveis de consumo de memória do servidor HTTP são **120,90 MB em 100k** e **172,49 MB em 500k**, atestando a integridade da persistência e do streaming em lotes.

---

## 3. Auditoria Investigativa do Arquivo de Comparação Fornecido Externamente (`resultado_esperado_100k.json`)

- **Origem e Caracterização:** Arquivo fornecido externamente pelo usuário sob o caminho `"C:\hackathon_kanastra\resultado_esperado_100k.json"` (sem proveniência formal de edital ou fonte primária associada).
- **Integridade Criptográfica:** SHA-256 `a5e0de969c0cf9d1f37aeea0100d7a4a2ba663da24c1641977f7a68934bc1ae8`.
- **Composição dos Dados:** 100.554 itens; 85.215 marcados como `APROVADO` e 15.339 marcados como `BARRADO`. Todos os pares de linha e identificadores coincidem com o `estoque_antecipe.csv`.
- **Execução Factual em Ambiente Limpo (Clean Venv):**
  - O Coordenador executou a validação direta do script de comparação `qa/compare_expected_results.py` em ambiente virtual limpo (`clean-venv`) via `runpy`, com saída agregada determinística.
  - **Concordância das 4 Regras Deriváveis:** O confronto contra regras objetivas e independentes (`VALOR_MINIMO`, `TIPO_RECEBIVEL`, `PRAZO_MAXIMO` por data de aquisição e agregação por fundo na `CONCENTRACAO_MAXIMA_SACADO`) resultou em **98.362 / 100.554 registros coincidentes (97,8201%)**.
  - **Natureza do Vetor Residual:** A divergência de 2.192 itens decorre exclusivamente de um **vetor de 87 sacados barrados**, que representa uma análise exploratória rotulada sem fonte de cadastro ou comprovação oficial de birô nos artefatos recebidos.
  - **Decisão Institucional:** O sistema não foi alterado para emular o conjunto de rótulos do arquivo fornecido externamente, mantendo o motor em conformidade com as boas práticas de crédito e com a política institucional do fundo.

---

## 4. Detalhes do Ambiente de Execução
- **Sistema Operacional:** Windows 10 (win32 10.0.26300 x64 / Windows-10-10.0.26300-SP0)
- **Processador:** Intel64 Family 6 Model 142 Stepping 12, GenuineIntel
- **Runtime Python:** Python 3.11.15
- **Runtime Node.js:** Node.js v24.14.1
- **Gerenciador de Dependências:** Ambiente virtual dedicado (`.venv`) em `Codex/antecipe/`
- **Banco de Dados Local:** SQLite 3 (configuração pronta para PostgreSQL via `DATABASE_URL`, com Docker e PostgreSQL **NÃO** executados no ambiente local por indisponibilidade de daemon Docker na máquina host)

## 5. Corte de escopo — versão base local

O usuário priorizou liberar a base e continuar melhorias e testes manuais depois. `diferenciais.md` foi lido como backlog: scanner DANFE, what-if, visualizações adicionais e aquisição concorrente não foram adicionados. Nenhum teste existente foi apagado; novas baterias de escala e expansão de QA foram suspensas.

- **Regressão financeira mínima:** `clean-venv/Scripts/python.exe -m pytest backend/tests/test_capacidade_monetaria_boundaries.py -q --tb=short`: 6 aprovados em 2,24 s.
- **Revisão independente dirigida:** rollback depois do chunk de 2.000 itens aprovado. O teste de importação cumulativa falhou inicialmente apenas por esperar outro prefixo de mensagem; corrigida somente essa asserção, passou em 1,63 s, incluindo preservação da carga anterior. Não foi repetida a suíte inteira.
- **Smoke do backend reiniciado:** saúde, upload e consulta HTTP 200; estoque ANTECIPE de 10.621 títulos, fonte `SIMULADO_DEMO`; 9 notas, 1 aprovada, 8 recusadas, total líquido `4700.00`.
- **Frontend local:** fontes atuais sincronizadas na árvore controlada `.data/frontend-clean-verify`; `npm test && npm run lint && npm run build` aprovado, build em 1,49 s com Vite 8.1.5, React 19.2.8, TypeScript 6.0.3 e Lucide 1.27.0. Bundle copiado para `frontend/dist`. Não é prova de instalação limpa do manifesto final.
- **Escala:** medições anteriores permanecem históricas e vinculadas aos hashes das fontes daquela execução. Não houve nova medição de 100k/500k após o ajuste monetário.
- **Git:** fontes permitidas integradas sem commit em cópia separada que já recebeu pull até `e0c5349`. Registros remotos de Elias/Pina e índice original preservados; dados privados e dependências não exportados. Nenhum push ou deploy externo realizado.
- **Auditorias mínimas finais:** `python tests/test_kit.py` aprovou 8 testes em 1,048 s; `python scripts/check_submission.py` retornou `Auditoria do kit: OK`; `python scripts/prompt_ledger.py audit` retornou 11 prompts, 0 pendências e 0 eventos órfãos.

## 6. Publicação autorizada no GitHub e na Vercel

- **Autorização:** pedido literal do usuário “pode subir no github e atualizar no vercel”, registrado como `P0012`.
- **GitHub:** `https://github.com/carlinnnd/hackathon-kanastra`, visibilidade pública já existente preservada. Pull antes do envio; commits `c30d8be` (base e adaptação de deploy) e `5502066` (manifesto Python plano) enviados à `main`, sem força ou reescrita de histórico.
- **Segurança do pacote:** dry-run Vercel identificou 36 arquivos e framework FastAPI. Verificada ausência de `.env`, banco SQLite, estoque real, gabarito externo, `.data` e dependências locais. Verificação HTTP após publicação: `/.env.local` e `/Codex/antecipe/antecipe.db` retornaram 404.
- **Teste dirigido:** `clean-venv/Scripts/python.exe -m pytest backend/tests/test_vercel_demo.py -q --tb=short`: 1 aprovado em 2,26 s. Verifica cinco títulos sintéticos, aviso público, upload de nove notas e totais nominais/líquidos exatos. O guard da entrada raiz também recusou banco fora do diretório temporário sem criar o arquivo.
- **Verificações mínimas do kit:** 8 testes aprovados em 1,207 s e `check_submission.py` aprovado na cópia de integração.
- **Falha de build investigada:** a primeira publicação não resolveu `-r Codex/antecipe/requirements.txt`. Substituído por manifesto plano contendo apenas sete dependências de runtime já existentes, com as mesmas versões. Sem introduzir dependências novas.
- **Deploy confirmado:** `dpl_9vPG9b9ZocUdJigTZ8q1WJMfuGV2`, estado `READY`, Python 3.12, promovido a `https://hackathon-kanastra.vercel.app`.
- **Smoke público inicial:** `/`, saúde e carteira responderam. Navegador exibiu 5 títulos sintéticos e aviso de resultados temporários; upload de nove notas confirmou 1 aprovada, 8 recusadas, nominal `30050.00` e líquido `4700.00`.
- **Limitação reproduzida e navegação corrigida:** a consulta do filtro inicialmente caiu em outra instância e retornou “Simulação não encontrada”. O SQLite temporário continua sem persistência entre instâncias. Para respostas completas já recebidas, a interface pública agora filtra somente a visualização em memória e preserva os totais do backend. Para resposta parcial, bloqueia filtros/paginação adicional e avisa que é necessário armazenamento persistente. A execução local continua usando consultas ao servidor.
- **Preservação:** índice original e registros remotos de Elias/Pina conferidos por SHA-256 após os pushes. Nenhum dado privado publicado e nenhum serviço de banco pago criado.
- **Validação da correção:** `npm test && npm run lint && npm run build` aprovado na árvore controlada, build de 2,42 s. O primeiro `npm test` revelou que o runner não carregava o helper novo; corrigido somente esse carregamento antes da execução aprovada.
- **Versão final em produção:** `dpl_Cj1UA5ksJt3pAgFLGT3uM8CasH27`, estado `READY`, Python 3.12, URL imutável `https://hackathon-kanastra-6anmspuvt-carlos-s-projects-198e4b14.vercel.app`, domínio principal `https://hackathon-kanastra.vercel.app`.
- **Smoke final no domínio principal:** bundle `index-CnKj22BH.js` confirmado. Nove notas exibidas com uma aprovada, oito recusadas, nominal R$ 30.050,00 e líquido R$ 4.700,00. Filtro de recusados exibiu oito linhas e retorno a todos restaurou nove; totais globais preservados, nenhuma consulta GET por ID durante o filtro, nenhum alerta de erro e nenhum erro de console observado.
- **Colaboração preservada no último pull:** atualização remota `ef43f14` de Elias incorporada por merge, resultando em `a2cdde6` com a correção de navegação. Sem sobrescrever os registros da equipe nem alterar o índice original.
- **Governança final da publicação:** `P0012` reconciliado com as falhas e correções reais. `python scripts/check_submission.py`: auditoria do kit OK. `python scripts/prompt_ledger.py audit`: 12 prompts, 0 pendências e 0 eventos órfãos.


## Deploy acelerado ? 2026-10-24T17:38:06.836482+00:00

A pedido do usu?rio em P0014, novas baterias espec?ficas e benchmarks de 100k/500k/1M foram adiados para priorizar publica??o. O requisito de capacidade de P0013 continua sem comprova??o nesses volumes no ambiente publicado.

- Produ??o: https://hackathon-kanastra.vercel.app/
- Deployment: `dpl_DmXmcEmfUAYSZmgp6RAD5qGZni8g`, `READY`, Python 3.12; build remoto conclu?do em 6 segundos.
- Publica??o direta por `vercel deploy --prod --yes --scope carlos-s-projects-198e4b14`, a partir do pacote isolado `Codex/antecipe/.data/deploy-20261024-fast`. A origem foi o workspace atual, sem novo commit ou push nesta intera??o.
- O conector MCP recusou acesso ao escopo da equipe (403); a CLI instalada confirmou o projeto e publicou com a autentica??o j? dispon?vel.
- `npm run build` falhou por aus?ncia do wrapper `vite` no PATH. O build real `node node_modules/vite/bin/vite.js build` passou com Vite 8.1.5. Aviso de bundle JavaScript maior que 500 kB; instala??o limpa npm permanece sem comprova??o.
- Pacote restrito a 38 arquivos preparados; a Vercel informou download de 36 arquivos de aplica??o. Somente c?digo, configura??o de demo, CSV sint?tico e assets referenciados pelo HTML; dados reais, bancos e credenciais exclu?dos.
- Verifica??o p?blica: `/`, `/api/health`, `/api/portfolio/summary` retornaram 200. HTML referencia `index-BwjX6Dvr.js`. Health anuncia o transporte WebSocket, teto configurado de 1.000.000 registros e 512 MiB; isso n?o constitui benchmark.
- Smoke operacional WebSocket: envio do `samples/demo.csv` sint?tico recebeu `ready`, confirmou bytes por `ack` e retornou `complete` com envelope de simula??o. N?o foram executadas novas su?tes espec?ficas de regress?o ou carga.
- `python scripts/check_submission.py`: Auditoria do kit OK. O fechamento do ledger e auditoria s?o registrados ap?s esta entrada.
# Cadastro, relatórios e conferência do gabarito — 24/10/2026

Atualização posterior aos registros históricos abaixo. Código e decisões vigentes estão detalhados em `Codex/antecipe/docs/RESULTADOS_E_CADASTRO.md`.

- **Causa reproduzida:** o serviço cadastral consultava somente quatro CNPJs de demonstração. O mock recebido, de 3.041 CNPJs válidos, não era carregado. Foi integrado com normalização, cache por arquivo e falha fechada, mantendo a identificação de cadastro simulado.
- **Cobertura cadastral nos 100.554 registros:** ATIVA 77.555; ausente/NAO_VERIFICADA 22.222; SUSPENSA 154; INAPTA 493; BAIXADA 130. Esses números não representam aprovações financeiras.
- **Gabarito completo:** `Codex/antecipe/.venv/Scripts/python.exe Codex/antecipe/qa/compare_cadastral_reference.py` conferiu linha e documento dos 100.554 registros. Gabarito: 85.215 aprovados / 15.339 barrados. Motor de novas operações contra o seed público e base 22/10/2026: 67.971 aprovadas / 12.306 recusadas / 20.277 pendentes. Concordância de status 76.581 e de todos os motivos 74.814. Não há concordância integral. Contradições cadastrais: 1.392 barrados por cadastro estão ATIVA no mock, 777 não ativos no mock não têm essa marcação, 16.593 aprovados no gabarito estão ausentes do mock. Fontes, hashes, matriz e divergências em `qa/relatorio_gabarito_mock.json` e `.data/gabarito-conference/divergencias.csv`. Rótulos não foram usados como fonte cadastral.
- **Testes:** `Codex/antecipe/.venv/Scripts/python.exe -m pytest Codex/antecipe/backend/tests/test_result_reporting.py Codex/antecipe/backend/tests/test_domain_engine.py Codex/antecipe/backend/tests/test_bulk_stream.py Codex/antecipe/backend/tests/test_api_endpoints.py -q --tb=short`: **71 aprovados em 4,56 s**, um aviso de depreciação do TestClient. Duas expectativas antigas de cadastro indisponível foram atualizadas para a semântica explícita de pendência. Novas regressões cobrem status, todos os motivos, duplicidade, histórico sem aquisição, rollback, paginação e exportação integral/protegida.
- **Frontend:** typecheck, testes de helpers e quatro casos de resiliência WebSocket passaram na árvore `.data/frontend-clean-verify`. Build Vite 8.1.5: 1,49 s, bundle `index-DGXYupoC.js`, 244,34 kB. A árvore principal tinha wrappers/tipos incompletos e não foi declarada instalação limpa do manifesto final. O bundle validado foi copiado para `frontend/dist` e usado no pacote publicado.
- **PDF:** ReportLab 4.4.3 adicionado ao runtime. Exemplo sintético de 63 notas renderizado em quatro páginas via PyMuPDF 1.26.5, com líquido conferido de R$ 18.800,00 e sem cortes/overlap observados. PyMuPDF foi usado somente na verificação local, não no runtime publicado.
- **Benchmark local histórico:** comando `Codex/antecipe/.venv/Scripts/python.exe Codex/antecipe/benchmarks/run_reporting_benchmark.py --source estoque_antecipe_100k/estoque_antecipe.csv --rows 100000 500000`. Python 3.11.15, Windows 10.0.26300, SQLAlchemy 2.0.36; 100k em **29,79 s**, 500k em **138,27 s**, incluindo persistência, CSV completo, confronto integral de quantidade/status/nominal e ausência de precificação histórica, e PDF. CSVs com 57.149.798 / 286.640.311 bytes e 100.000 / 500.000 linhas verificadas. Picos cumulativos Win32 do processo 76,32 / 84,89 MiB. Cenário 500k repete o estoque para formar volume; não são novos recebíveis. Hashes das fontes antes/depois iguais. O primeiro runner falhou na aferição Win32 e produziu memória zero inválida; foi preservado, corrigido e os dois cenários foram repetidos. Medições válidas em `.data/reporting-benchmark/summary.json`. **Não comprova volume HTTP/WebSocket/Vercel nem um milhão de registros.**
- **Navegador local:** conferidos os três downloads, filtro de duas pendências da demonstração anterior à adaptação de exemplos, nove itens em modo histórico sem rótulo de recusa, valores e layout móvel de 390 px sem overflow externo. Sem erros de console observados.
- **Publicação:** primeiro deploy `dpl_9anRyDmPNeR9vJQKMphfGFugAjY4` partiu da raiz e levou o bundle anterior; a tentativa de cancelamento retornou 400 pois já havia concluído. Foi substituído pelo pacote isolado de 40 arquivos preparado por `scripts/prepare_deploy.py`. Deploy final **`dpl_CJGbkyVKAJvFSxNJPXBc9nzi5vvV`**, READY, Python 3.12, build remoto 6 s, domínio `https://hackathon-kanastra.vercel.app/`. Publicação direta, sem novo commit/push nesta interação. A configuração de vínculo criada automaticamente na raiz foi preservada em `.data/vercel-root-link-20261024`, dentro do projeto.
- **Verificação pública:** site e saúde HTTP 200; bundle final confirmado; source SHA do mock confirmado. Demonstração processada pelo navegador: **1 aprovada, 7 recusadas, 1 pendente, líquido R$ 4.700,00**. Downloads reais pelo UI: CSV 6.215 bytes, PDF 9.055 bytes, violações CSV 1.622 bytes; nenhum erro de console observado. Exemplos agora usam CNPJ ativo da fonte mock selecionada.
- **Limites:** carteiras da demo continuam sintéticas e resultados efêmeros; o cadastro mock não é confirmação oficial. Correspondência integral com o gabarito depende de reconciliar as fontes e o cenário de carteira/data-base. Não houve nova medição pública de 100k/500k/1M, nem PostgreSQL/concor­rência de produção. Dados de estoque real, bancos, divergências individuais e credenciais ficaram fora do pacote Vercel.


## Publicação no GitHub — 24/10/2026

Por pedido explícito “suba no git”, as fontes atuais e o bundle validado foram integrados em clone limpo de origin/main, dentro de Codex/antecipe/.data, preservando o índice original e os registros de Elias/Pina. Pull antes do commit confirmou main atualizada. Commit de implementação `d240217` enviado a `https://github.com/carlinnnd/hackathon-kanastra`, branch `main`, sem força nem reescrita de histórico.

Na cópia publicada: 71 testes de backend aprovados em 4,76 s, `scripts/check_submission.py` aprovado, ledger anterior com 16 prompts sem pendências. Varredura limitada dos 57 arquivos preparados não identificou caminhos sensíveis nem padrões de chaves privadas, tokens GitHub, chaves AWS ou tokens OpenAI. Não equivale a auditoria exaustiva de segredos. `git diff --cached --check` passou após remover espaços finais em linhas específicas, sem alterar lógica.

Incluídos cadastro mock autorizado, relatório agregado de comparação e resumo reproduzível das medições históricas. Excluídos estoque real, gabarito individual, bancos, credenciais, .data, dependências e saídas individuais. Os assets de public/ no GitHub agora correspondem ao bundle `index-DGXYupoC.js` já validado na publicação Vercel anterior. Esta etapa publica no Git; não afirma resultado de eventual deploy automático disparado pelo push.
# Correção de contrato — somente aprovada ou recusada — 24/10/2026

O usuário substituiu explicitamente a proposta anterior de pendência/erro como decisão separada. Novas notas agora retornam somente **APROVADA ou RECUSADA**. Cadastro ausente/inconclusivo recusa pelo código canônico `SITUACAO_CADASTRAL_SACADO`, com explicação e orientação para confirmar/atualizar o cadastro e reenviar. Dados inválidos também recusam, preservando o motivo específico. Nenhuma regra financeira, taxa, prazo ou limiar de elegibilidade foi introduzido ou fixado por esta alteração.

- **Consistência:** domínio, API HTTP/JSON e WebSocket, dashboard, CSV e PDF usam decisão binária. Aprovadas recebem cálculo líquido; recusadas mantêm líquido/desconto nulos ou vazios. Em novas operações, aprovados + recusados = total_itens. A análise descritiva de estoque continua separada, sem simular nova aquisição.
- **Legado:** payloads/analytics antigos são normalizados na leitura; dados armazenados não foram apagados nem migrados destrutivamente. Dois testes independentes confirmaram paridade CSV/API JSON e adaptação dos status antigos em GET, CSV e analytics.
- **Testes finais:** 73 aprovados em 7,02 s na cópia Git, comando `C:/hackathon_kanastra/Codex/antecipe/.venv/Scripts/python.exe -m pytest Codex/antecipe/backend/tests/test_result_reporting.py Codex/antecipe/backend/tests/test_binary_contract_review.py Codex/antecipe/backend/tests/test_domain_engine.py Codex/antecipe/backend/tests/test_api_endpoints.py Codex/antecipe/backend/tests/test_bulk_stream.py -q --tb=short`; um aviso de depreciação do TestClient. Typecheck, testes frontend e build passaram na árvore controlada; bundle `index-DsYjQTxp.js` gerado em 1,43 s, sem alegar instalação limpa npm.
- **Gabarito reexecutado:** 100.554 linhas/documentos conferidos; cenário de novas operações contra seed público resultou em 67.971 aprovadas e 32.583 recusadas. Concordância de status 80.800; de todos os motivos 75.736. Persistem conflitos de fonte cadastral e de cenário; não há concordância integral presumida.
- **Publicação:** deploy `dpl_9gr4KsNWNr2SCDXShHQJ6DF9Yy9Q`, READY, Python 3.12, build remoto 6 s. Domínio `https://hackathon-kanastra.vercel.app/`. Código enviado à main no commit `d9bcd29`, sem força ou reescrita de histórico.
- **Navegador em produção:** nove notas, **1 aprovada / 8 recusadas**, total a receber **R$ 4.700,00**; filtro com apenas aprovadas/recusadas. CSV baixado com 6.431 bytes e somente os dois status; PDF com 9.036 bytes; nenhum erro de console observado. A primeira tentativa de inspeção reabriu uma aba local suspensa, cuja espera expirou; navegação explícita ao domínio publicado corrigiu a inspeção.
- **Limites mantidos:** fonte cadastral simulada e carteira pública sintética, resultados efêmeros por sessão. Nenhuma nova medição de carga foi necessária para a mudança de classificação; os benchmarks anteriores continuam vinculados às fontes registradas. Relatos anteriores com pendências são históricos, substituídos por esta correção.

## Mock cadastral atualizado e publicado — 24/10/2026

Por solicitação explícita do usuário, o novo mock foi publicado no GitHub (main, commit `fd76ef4`) e na Vercel (produção, `dpl_CYYuJqP9XAhSiSCHB7AQwoURQMiq`, READY, build remoto de 8 s). O pacote isolado de 40 arquivos confere byte a byte com o clone de publicação; a mudança de runtime é somente o CSV cadastral. Não foram alteradas regras, data-base ou carteira demonstrativa.

- Mock: 4.360 CNPJs, sendo 4.271 ATIVA, 24 SUSPENSA, 27 INAPTA e 38 BAIXADA. SHA-256 `1d5f0897f7ba793a401a7313b574b3506c2a71b2f83312abd53ac0376f74d148`.
- Auditoria local completa das 100.554 notas: base 22/10 = 86.709 aprovadas / 13.845 recusadas / R$ 426.931.003,60 líquidos; base 24/10 = 85.818 / 14.736 / R$ 423.454.083,50. Todas as notas têm cadastro no novo mock; nenhum conflito cadastral com o gabarito foi detectado. Na base 22/10, 3.250 notas barradas exclusivamente por concentração no gabarito são aprovadas pelo motor contra a carteira pública demonstrativa. A projeção do gabarito para 24/10 continua sendo cenário distinto (82.601/17.953).
- Clone de publicação: 73 testes passaram em 7,88 s, um aviso de depreciação do TestClient. `check_submission.py` e `git diff --cached --check` passaram. Estoque real, gabarito individual, banco e credenciais não foram publicados.
- Navegador no domínio público: `/api/health` HTTP 200 e hash cadastral novo confirmado. Simulação de demonstração HTTP 200: nove notas, uma aprovada, oito recusadas, líquido R$ 4.700,00, auditoria com o hash novo e data-base 22/10/2026.
- Consulta CLI de logs de erro desde 10 minutos retornou nenhum log encontrado; não equivale a auditoria exaustiva nem comprova carga pública de 100k. A CLI emitiu aviso de consulta de atualização npm indisponível, mas os comandos de deploy e logs concluíram com código zero.

## Data atual automática publicada — 24/10/2026

Correção solicitada pelo usuário: novas simulações usam a data atual de Brasília (America/Sao_Paulo), capturada uma vez por lote; não usam mais o default 22/10/2026. Tela consulta health a cada minuto e exibe a data persistida ao consultar um resultado anterior. Cadastro, regras de elegibilidade e carteira foram preservados. API JSON sem data_base usa o dia atual; uma data diferente enviada explicitamente é rejeitada (DATA_BASE_INVALIDA). DATA_BASE foi removida das configurações e do exemplo de ambiente. Uma data antiga no JSON de regras não congela a data operacional.

- Testes: 77 aprovados em 4,25 s no clone de publicação, incluindo quatro casos novos de relógio/virada Brasilia versus UTC, CSV e JSON entre 24 e 25, configuração legada com data fixa, leitura/exportação de resultado antigo e WebSocket. Após capturar também a data JSON em uma única leitura de relógio, os quatro casos foram repetidos: 4 aprovados em 1,63 s. Um aviso de depreciação do TestClient.
- Frontend: typecheck, testes existentes e build passaram na árvore controlada frontend-clean-verify; Vite 8.1.5 em 1,31 s, bundle index-DbNlozI0.js. Não representa reinstalação limpa do manifesto. tzdata 2026.5 fixado para dados IANA no Windows, instalado via uv; teste local inicial provou que ZoneInfo não tinha essa base instalada.
- Git: commit de implementação c93943e enviado à main. Pacote restrito de 41 arquivos conferido byte a byte contra o clone. check_submission e diff --cached --check passaram. Nenhum estoque real, banco, payload ou credencial incluído.
- Vercel: dpl_6MApgrSBekAN3EX3AkAR1jSt3cQW, READY, build remoto 7 s, Python 3.12; domínio https://hackathon-kanastra.vercel.app/. health HTTP 200, Cache-Control no-store, data_base_atual 2026-10-24, fuso America/Sao_Paulo e hash do mock atualizado confirmados.
- Navegador real: banner DATA-BASE:24/10/2026; upload de demonstração via UI/WebSocket retornou nove notas, uma aprovada, oito recusadas, líquido R$4.706,67 e prazo ponderado 88 dias. Endpoint CSV HTTP confirmou os mesmos totais e data. Consulta CLI de logs de erro desde 10 minutos retornou nenhum log encontrado; não equivale a varredura exaustiva. Não houve novo benchmark de alto volume, pois a mudança lê a data uma vez por simulação e não altera o pipeline por linha.
