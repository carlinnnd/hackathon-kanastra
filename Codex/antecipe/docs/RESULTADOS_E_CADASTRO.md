# Cadastro, decisões e relatórios

Requisitos atualizados em 24/10/2026: novas operações têm **somente APROVADA ou RECUSADA**, conforme correção explícita posterior do usuário. Usar cadastro mock, motivos claros, líquido por aprovada e total, com a mesma validação na tela e API. A proposta anterior de pendência/erro como terceiro estado foi substituída.

## Como usar

1. Escolha **Estoque histórico dos fundos** para analisar o arquivo de 100.554 títulos já adquiridos. O resultado é descritivo: valores, vencimentos e concentração por fundo/raiz. Não aplica uma decisão de nova aquisição e não importa permanentemente o estoque de referência.
2. Escolha **Novas notas para antecipação** para aplicar as regras ativas, duplicidade e precificação. O estoque de referência é o informado na auditoria; na publicação pública, continua sendo o seed sintético de cinco títulos, não a carteira real.
3. Use **CSV completo**, **PDF executivo** ou **CSV de violações** após concluir. Exportações são integrais, independentemente da página/filtro visível. Na demonstração pública dependem da sessão WebSocket ativa; depois de encerrada, reenvie o arquivo. Baixe os resultados antes de trocar o arquivo ou fechar a aba.

## Decisões e fonte

| Status técnico | Significado |
| --- | --- |
| APROVADA | Passou em todas as regras ativas e em duplicidade; recebe cálculo financeiro. |
| RECUSADA | Não passou em alguma validação. Cadastro não confirmado, situação não aceita e dados inválidos recusam com motivos claros e próximos passos. |
| CARTEIRA_HISTORICA | Linha válida no modo descritivo de estoque; não é aprovação nem recusa de antecipação. |

Todos os motivos identificados são preservados. Recusadas não entram no volume elegível nem na projeção. Valores líquidos/descontos de notas recusadas são nulos no resultado técnico e vazios no CSV. No modo histórico, os totais financeiros de antecipação não se aplicam. Uma linha histórica analisada descritivamente não é uma solicitação de nova antecipação.

O arquivo `data/cnpj_situacao_mock.csv` mantém o SHA-256 do arquivo recebido: `522ba08c9685a48d2c2a5b20bfde0773f58bb15b095e03cf605b44c224ca6916`. São 3.041 documentos válidos, 2.999 ATIVA e 42 INAPTA/SUSPENSA/BAIXADA. É **fonte simulada**, sem equivalência a consulta à Receita Federal.

Configuração: `ENABLE_DEMO_CADASTRO=true` e `CADASTRO_MOCK_PATH` apontando para esse arquivo. O caminho padrão está dentro do projeto. Documento ausente, arquivo inacessível, schema inválido ou conflito cadastral não resultam em ATIVA. O fixture antigo de quatro CNPJs só é selecionado explicitamente com caminho vazio em testes. O mapa e sua identificação são congelados durante cada simulação.

## Concentração e configuração

Novas operações usam a raiz do sacado, somam somente aprovações anteriores do lote e incluem o título candidato no numerador e denominador. Igualdade ao limite ativo é aceita. Excesso histórico é preservado, com aviso; novas exposições acima do limite são recusadas. Análise histórica calcula exposição por fundo e raiz e não reescreve aquisições existentes.

Sete regras ativas e duas inativas permanecem no JSON. O gestor pode publicar e ativar uma versão imutável de configuração pelas rotas administrativas existentes, sem deploy. Isso exige o token administrativo configurado; editar um arquivo no disco não é hot reload automático da versão já persistida.

## Contratos e compatibilidade

- `POST /api/simulations?tipo_analise=novas_operacoes|carteira` conserva a resposta síncrona paginada existente.
- `GET /api/simulations/{id}` e `/items`: envelope paginado com APROVADA/RECUSADA e agregações. Aliases legados continuam disponíveis; CARTEIRA_HISTORICA é exclusivo da análise descritiva separada.
- `GET /api/simulations/{id}/analytics`: agregações persistidas na mesma transação dos resultados.
- `GET /api/simulations/{id}/export?format=csv|pdf|violacoes`: CSV integral em cursor limitado; PDF a partir das agregações. Headers de download e `Cache-Control: no-store`.
- WebSocket: `start` recebe `tipo_analise`; `complete`/`page` incluem analytics. Comando `export` envia formato e request_id; respostas `export_chunk` (base64, até 32 KiB binários por frame) e `export_complete`. O servidor ignora IDs de simulação externos e usa apenas a simulação da conexão.
- Em novas operações, `aprovados + recusados = total_itens`; `analytics.status_counts` usa somente APROVADA/RECUSADA. A UI, API, CSV e PDF usam o mesmo contrato. Resultados anteriores com os status removidos são normalizados na leitura, incluindo motivos cadastrais e agregações, sem apagar ou migrar o histórico armazenado.
- Duas tabelas aditivas (`simulation_item_details`, `simulation_reports`) preservam resultados anteriores, sem ALTER/descarte/backfill. Simulações antigas continuam consultáveis; a exportação detalhada responde 409 e pede reprocessamento, pois não possuíam campos originais persistidos.
- O CSV usa UTF-8 BOM, `;`, vírgula decimal, datas brasileiras, ordem original, todos os motivos e campos de auditoria. Células/cabeçalhos que poderiam executar fórmulas recebem prefixo de proteção ao abrir no Excel.
- O servidor não monta lista de todos os títulos para exportar. O navegador recebe blocos e cria um Blob para o download; sua memória pode crescer com o arquivo exportado. O PDF contém resumo e gráficos dinâmicos, não uma tabela de 100 mil linhas.

## Gabarito: comparação integral e divergências

O script `qa/compare_cadastral_reference.py` conferiu todas as 100.554 linhas e documentos contra `resultado_esperado_100k.json`.

| Fonte / cenário | Aprovações | Recusas |
| --- | ---: | ---: |
| Gabarito recebido | 85.215 | 15.339 |
| Motor atual, novas operações, seed público, base 22/10/2026 | 67.971 | 32.583 |

Concordância de status: 80.800/100.554. Concordância de todos os motivos: 75.736/100.554. O relatório foi reexecutado com a decisão binária. Isso **não** é aprovação integral pelo gabarito. Os valores financeiros não estão presentes no gabarito e não podem ser comparados com ele.

Conflitos diretos: 1.392 linhas barradas por cadastro têm ATIVA no mock; 777 linhas com cadastro não ativo não têm esse motivo no gabarito; 16.593 aprovadas no gabarito estão sem cadastro no mock. Há também diferenças de cenário: o gabarito tem 3.305 marcações de concentração e 4.671 de prazo máximo; o motor contra o seed público tem zero e 4.502, respectivamente, além de 1.793 notas vencidas na data-base. Isso exige alinhamento de carteira e referência temporal antes de atribuir toda divergência a um defeito. Não se infere cadastro a partir do gabarito nem se altera o motor para reproduzir rótulos contraditórios.

O JSON agregado está em `qa/relatorio_gabarito_mock.json`. Divergências por linha ficam em `.data/gabarito-conference/divergencias.csv`, local e fora da publicação. Concordância integral depende de resolver a fonte cadastral e alinhar a carteira/data-base do cenário esperado; essa decisão continua aberta.

## Verificações

- Correção binária: 71 testes de backend aprovados em 3,67 s, cobrindo domínio, API, WebSocket e regressões.
- Frontend: typecheck, helpers e quatro cenários de resiliência passaram na árvore controlada; build Vite 8.1.5/React 19.2.8 em 1,43 s gerou o bundle `index-DsYjQTxp.js`. Não comprova `npm ci` limpo do manifesto final.
- PDF sintético de 63 notas: quatro páginas renderizadas e inspecionadas, incluindo líquido conferido de R$ 18.800,00. Exemplo em `output/pdf/relatorio-executivo-demo.pdf`.
- Verificação anterior: CSV completo, PDF e CSV de violações baixados, modo histórico e tela de 390 px sem overflow externo. O filtro de pendências daquela versão foi removido na correção binária.
- Benchmark local histórico: 100k em 29,79 s e 500k em 138,27 s, incluindo persistência, CSV, conferência integral e PDF. Avaliação/persistência: 19,33 s / 82,10 s; CSV: 8,58 s / 47,85 s. Pico cumulativo Win32 do processo: 76,32 / 84,89 MiB. Python 3.11.15, Windows 10.0.26300, SQLAlchemy 2.0.36. O caso 500k repete o estoque para volume, sem novos recebíveis. Hashes das fontes antes/depois iguais. Não mede HTTP/WebSocket, concorrência ou volume publicado.
- A primeira coleta de memória falhou e produziu zero; essa coleta foi invalidada e preservada em `.data/reporting-benchmark/summary-run1-memory-invalid.json`. O runner foi corrigido com tipos Win32 explícitos e os dois volumes foram repetidos. Medições válidas em `.data/reporting-benchmark/summary.json`.

O limite configurado de 1 milhão não comprova capacidade publicada de 1 milhão. Nenhum dado de estoque real, banco, arquivo de divergências ou credencial integra o pacote Vercel.
