# Hackathon Antecipe — plano e contratos de integração

Estado: implementação inicial. Fonte dos requisitos: prompt do usuário de 24/10/2026 e arquivos reais da raiz. O edital completo não foi disponibilizado como documento independente. Não realizar publicação externa.

## Diagnóstico confirmado

- Apenas kit de agentes existente; nenhuma aplicação anterior a preservar.
- CSV UTF-8 com os 11 cabeçalhos descritos pelo usuário: 100.554 registros, 18 fundos; ANTECIPE tem 10.621 registros e nominal de 53.074.028,00. Maior exposição por raiz: 12,5%.
- SHA-256 CSV: `313c75f4147e1e851eaaefd15dc035aa895c961434da1a91024fd0764559c2f1`.
- JSON real: nove validadores; sete ativos. `valor_minimo`, `prazo_maximo_dias`, `percentual_maximo`, `situacoes_aceitas`, `tipos_aceitos`; taxa `taxa_mensal_percentual` representa porcentagem e deve ser dividida por 100.
- Python 3.11.15 e Node 24.14.1 presentes. Docker e comando python3 indisponíveis; utilizar `python` no Windows. PostgreSQL via Compose será preparado, e SQLite será alternativa local explicitamente documentada.

## Escopo e premissas do MVP

- Simulação, sem aquisição. Data-base explícita 2026-10-22, pois ausente do JSON original.
- Identidade global: cedente + sacado + tipo normalizado + documento normalizado + vencimento. Não incluir fundo.
- Ordem do CSV; apenas aprovados alteram carteira projetada do lote. Duplicidade de uma parcela repetida deve ser detectada mesmo se a primeira ocorrência for recusada.
- Concentração por raiz do sacado; histórico acima do limite é alerta, novas notas não podem agravar o grupo acima do limite. Premissa proposta no prompt, sujeita a confirmação de negócio.
- Fonte cadastral padrão desconhecida: NAO_VERIFICADA recusa quando regra ativa aceita apenas ATIVA. Demonstração usa mapa estático explicitamente SIMULADO apenas de empresas sintéticas conhecidas. Nunca inferir ATIVA de CNPJ válido nem de presença no estoque.
- Valores Decimal, arredondamento HALF_UP por nota, total soma das notas aprovadas. Nenhum float financeiro.
- Configuração por JSON validado e versões imutáveis, versão fixa por simulação e metadados do estoque/cadastro. Sem execução de expressões.
- API local sem aquisição; administração exige segredo de ambiente, sem valor padrão público. Uploads limitados; respostas de erro e logs não incluem conteúdo bruto.

## Frentes com escrita exclusiva

| Frente | Propriedade exclusiva | Dependências |
|---|---|---|
| Motor | backend/domain/** e backend/tests/test_domain*.py | JSON real |
| API e persistência | backend/** exceto domain e test_domain*; requirements, Docker/Compose, configuração local e samples/** | contrato motor e API abaixo |
| Frontend funcional | frontend/** | contrato HTTP abaixo |
| Documentação/ledger | docs existentes raiz; docs do projeto exceto este plano; README existente raiz e README projeto | evidências concretas dos demais |
| QA/performance | qa/**, benchmarks/** | implementação integrada; sem editar módulos dos autores |

Todos os arquivos novos do projeto ficam em Codex/antecipe. Arquivos existentes do kit podem ser atualizados. Nenhum agente pode editar arquivos de outra frente sem transferência explícita. Não criar subagentes aninhados. Não alterar Git/histórico nem publicar.

## Contrato HTTP fixado

- `GET /api/health`: estado e prontidão do estoque.
- `POST /api/simulations`: multipart campo `file`, CSV UTF-8 delimitador ponto e vírgula. Retorna resumo e primeira página do objeto abaixo. Processamento síncrono inicial; UI usa estado indeterminado honesto.
- `GET /api/simulations/{id}?page=1&page_size=50&status=aprovado|recusado&reason=CODIGO`: mesmo envelope com paginação e filtros; `status`/`reason` opcionais.
- `POST /api/receivables/evaluate`: JSON `{ "recebiveis": [objetos com cabeçalhos CSV], "data_base": "2026-10-22" }`; mesmo serviço, mesmo envelope.
- `GET /api/rules`, `GET /api/rules/versions`: configuração ativa e versões.
- `POST /api/rules/versions`: `{ "configuration": objeto JSON original, "change_reason": texto }`, cabeçalho `X-Admin-Token`; resposta versão publicada.
- `POST /api/rules/versions/{id}/activate`: cabeçalho `X-Admin-Token`, proteção contra ativação concorrente.
- `GET /api/demo.csv`: lote sintético público e identificado; `GET /api/portfolio/summary`: resumo agregado, sem dados individuais históricos.

Envelope: `{simulation_id, rule_version, rule_version_id, data_base, status: "concluida", total_itens, aprovados, recusados, total_nominal: "0.00", total_liquido: "0.00", resultados: [{linha, documento, sacado, aprovado, valor_nominal: "0.00"|null, valor_liquido: "0.00"|null, motivos: [{codigo,mensagem,dados?:{}}]}], pagination: {page,page_size,total,total_pages}, auditoria: {cadastro_fonte,carteira_referencia,configuration_hash}, avisos: []}`.

Erros: HTTP 400/413/422/503 com `{detail:{codigo,mensagem}}`; não retornar linhas, exceções ou payloads em erros. Frontend deve aceitar também `detail` string e erro de rede com mensagem segura.

## Contrato do motor (autor deve publicar assinaturas definitivas cedo)

Módulo `backend.domain.engine`; independente de SQL/HTTP. Parsing CSV e normalização dentro de domain/ingestion.py. Motor recebe snapshot agregado (total nominal, exposições por raiz/sacado e cedente, identidades globais existentes), configuração congelada e cadastro por CNPJ. Itera resultados em ordem e acumula projeção apenas de aprovados. API persiste resultados em lotes, sem resposta de 500 mil itens em memória; queries paginadas. Coordenar nomes exatos diretamente com autor backend antes de finalizá-los.

## Verificação e dependências

1. Domínio, backend e frontend em paralelo com contratos acima.
2. Integração e testes de limites, importação real e demonstração.
3. QA independente, benchmarks reais 100k/500k e revisão de segurança.
4. Correções pelos autores, repetição das evidências afetadas, README e roteiro.
5. Testes do kit, check_submission, audit do ledger, build frontend e fluxo real no navegador.

Risco R3 para upload/admin/cadastro, R2 para persistência/versionamento. Escrita de produto delegada; coordenador mantém contratos e valida. Revisão independente Gemini e auditoria final Sol xhigh exigidas pela política local. Docker/PostgreSQL indisponíveis localmente devem ser declarados sem afirmar teste inexistente. Rollback: nenhuma aquisição; simulações e versões novas preservam dados importados; bancos de teste isolados.

Catálogo de skills localizado em `C:/Users/moren/.traycer/skill-suites/traycer-engineering-skill-suite/manifest.json`, versão 3.0.0 com 35 entradas declaradas. Espelho do runtime em `.traycer/.codex/skills` tem 48 definições descobertas (inclui extras); SHA-256 do JSON determinístico ordenado de identificador + definição UTF-8: `c8cfd7f9cecf5b1f9088e8ad81452f29ebd21776f426b62f62e5aa115b1d6d32`. Skills por fase, máximo quatro simultâneas. Histórico da sessão anterior recuperado; ledger previamente iniciado P0001. Hooks desta sessão não capturaram o novo prompt até a inspeção; registrar manualmente texto real, sem inventar histórico.
