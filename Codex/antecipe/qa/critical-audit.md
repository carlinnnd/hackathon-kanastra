# Auditoria crítica independente R3 — Antecipe

**Snapshot auditado:** 24/10/2026, antes do ciclo de correções disparado pelo coordenador.  
**Escopo:** precisão financeira e armazenamento em centavos; configuração JSON e versões; cadastro; duplicidade; concentração; importação; autenticação administrativa; limites de entrada; erros e logs.  
**Veredito deste snapshot:** **CORRIGIR antes de submeter**. Há evidência positiva nos controles centrais de domínio, mas quatro defeitos confirmados impedem afirmar que a aplicação está pronta ou segura. As correções informadas pelos autores ainda não foram revalidadas neste documento.

## Fronteiras e premissas revisadas

- Entradas não confiáveis: multipart CSV, JSON de avaliação, parâmetros de URL e configuração publicada por administrador.
- Ativos: decisões de elegibilidade, valores financeiros, carteira histórica, versões de regras, dados de clientes, token administrativo e disponibilidade do serviço.
- Autoridades: público pode simular e consultar uma simulação por UUID; `X-Admin-Token` publica/ativa regras; banco e arquivos locais são infraestrutura confiável, mas corrupção/mutação deve ser detectável quando se afirma imutabilidade.
- Ambiente: Python 3.11.15, `.venv/Scripts/python.exe`, bancos SQLite temporários fora do workspace. O banco importado existente e o CSV de origem não foram alterados. Docker/PostgreSQL não estavam disponíveis.

## Bloqueadores confirmados

### B1 — Persistência de simulação viola a FK e não é atômica

**Classe:** defeito confirmado de correção e portabilidade.  
**Evidência no snapshot:** `SimulationService.executar_simulacao_lote` chamava `SimulationsRepository.salvar_itens_em_lote` antes de `criar_simulacao`; ambos faziam `commit()` internamente. O filho `simulation_items.simulation_id` referencia `simulations.id`.

Reprodução 1, com SQLite temporário e `PRAGMA foreign_keys=ON`:

```text
FK_ON_EXCEPTION=IntegrityError
FK_ON_MESSAGE=(sqlite3.IntegrityError) FOREIGN KEY constraint failed
FK_ON_COUNTS=simulations:0,items:0
```

Reprodução 2, SQLite padrão e gerador que lança uma falha controlada logo após o item 2.000:

```text
PARTIAL_EXCEPTION=RuntimeError:falha-controlada-pos-chunk
PARTIAL_COUNTS=simulations:0,items:2000
```

**Impacto:** PostgreSQL/Compose deve recusar o primeiro lote de filhos; SQLite pode confirmar resultados órfãos após falha tardia. Uma resposta malsucedida altera o banco de forma parcial.

**Recomendação:** **CORRIGIR**. Criar/`flush` do registro-pai antes dos filhos e controlar a unidade transacional no serviço, sem commits nos repositórios internos. Se a estratégia deliberada for commit por chunks, criar o pai em estado `processando`, marcar `falha` e eliminar/invalidar resultados parciais de forma comprovável.

**Recheck obrigatório:** (a) simulação de um item com FK ativa termina; (b) exceção depois de 2.000 itens deixa zero simulações/itens, ou um pai `falha` sem resultados consumíveis; (c) caminho normal preserva paginação e totais.

### B2 — Data-base usada no cálculo diverge da data-base auditada

**Classe:** defeito confirmado de correção financeira/auditoria.  
**Causa:** `carregar_configuracao` prioriza `configuration.data_base`, enquanto `SimulationService` persistia e devolvia `data_base_override`/`settings.DATA_BASE`.

Reprodução: V2 publicada com `data_base=2026-10-22`, execução com override `2026-10-01`, título de R$ 100,00 vencendo em 31/10/2026:

```text
DATE_SNAPSHOT=envelope:2026-10-01,persisted:2026-10-01,
approved:True,liquid:99.40,config_date:2026-10-22,
days_from_envelope:30,days_from_config:9
```

R$ 99,40 prova cálculo por 9 dias, embora envelope e banco declarem 30 dias.

**Recomendação:** **CORRIGIR**. Definir uma única data-base efetiva e usá-la no motor, persistência, resposta e auditoria. Alternativa válida: rejeitar override conflitante com 422.

**Recheck obrigatório:** se override prevalecer, o caso acima retorna R$ 98,00 e data `2026-10-01`; se a configuração prevalecer, retorna R$ 99,40 e data `2026-10-22` em todos os locais.

### B3 — Limite de upload acontece depois do recebimento/spool do multipart

**Classe:** vulnerabilidade confirmada de disponibilidade/controle de recursos.  
**Evidência:** `LimitedRawIO` envolve `UploadFile.file` dentro do endpoint, depois de FastAPI/Starlette concluir o parsing multipart. Com limite de 100 bytes e corpo de 2 MiB, foi instrumentado o objeto recebido pelo limitador:

```text
UPLOAD_POST_SPOOL=status:413,stream_observed:('SpooledTemporaryFile', True)
```

O `413` é semanticamente correto, mas `_rolled=True` prova que o corpo já havia sido gravado em arquivo temporário. O endpoint JSON também não tinha limite de corpo/quantidade e materializava a lista e um segundo CSV inteiro em memória.

**Impacto:** cliente público pode consumir disco/memória antes da checagem prometida. O teste R3 existente comprova apenas rejeição pós-parse.

**Recomendação:** **CORRIGIR**. Aplicar limite no fluxo ASGI antes do parsing multipart, contando chunks inclusive para requisição sem `Content-Length`; limitar também o JSON. Manter a checagem no arquivo como defesa adicional.

**Recheck obrigatório:** teste ASGI que demonstra interrupção antes de `UploadFile`/spool, com `Content-Length` e transferência sem tamanho declarado; teste separado para JSON excedente.

### B4 — Paths controlados pelo cliente permanecem em logs

**Classe:** vulnerabilidade confirmada de privacidade/logging.  
**Evidência HTTP:** uma rota inexistente com sentinela não coberta pela regex foi registrada integralmente:

```text
GET /api/clientes/cliente-acme-confidencial-2026 -> 404
ARBITRARY_PATH_LOG=sentinel_logged:True
```

A regex de CPF/CNPJ/token não é uma allowlist. Além disso, `Dockerfile` e README iniciavam Uvicorn sem desativar access log; a versão instalada usa `get_path_with_query_string(self.scope)` em `uvicorn/protocols/http/h11_impl.py` e `httptools_impl.py`.

**Impacto:** nomes, documentos com formatação inesperada, tokens em query e outros dados colocados na URL podem aparecer no logger da aplicação e no access log do servidor, contrariando a regra explícita de zero dados pessoais/credenciais em logs.

**Recomendação:** **CORRIGIR**. Registrar somente nome/template de rota de uma allowlist, ou omitir path; desativar/filtrar o access log padrão e não registrar query string.

**Recheck obrigatório:** sentinelas alfabéticas, documentos formatados/percent-encoded e query secrets ausentes em todos os handlers, incluindo execução real via Uvicorn.

## Achados importantes

### I1 — Frações de centavo geram totais contraditórios

`parse_decimal_br` aceitava até quatro casas, mas os agregadores convertiam `Decimal * 100` com `to_integral_value()` sem `ROUND_HALF_UP`. Reprodução com R$ 100,005 e vencimento na data-base:

```text
approved:True
item_nominal:100.00
item_liquid:100.01
total_nominal:100.00
total_liquid:100.01
nominal_cents:10000
liquid_cents:10001
```

**Recomendação:** **CORRIGIR**. Rejeitar valores não exatamente representáveis em centavos, aceitando e normalizando apenas zeros excedentes (`100.000`), ou definir uma normalização única e explícita antes de qualquer regra/persistência. Não arredondar silenciosamente o valor de face.

### I2 — Importador aceita schema ausente e silencia data de aquisição inválida

Reproduções:

```text
CSV contendo apenas cabeçalho NOME_FUNDO:
IMPORT_MISSING_HEADERS=returned:(0, 0, Decimal('0')),cargas:1,receivables:0

DATA_AQUISICAO=99/99/9999:
IMPORT_INVALID_ACQUISITION=returned:(1, 0, Decimal('0')),stored_date:None
```

O primeiro arquivo vira uma carga bem-sucedida vazia; o segundo perde um campo inválido silenciosamente.

**Recomendação:** **CORRIGIR** com validação de cabeçalhos antes de iterar e parsing estrito de toda data preenchida. O erro deve citar linha/campo, sem repetir valor bruto.

### I3 — Idempotência do estoque é apenas identidade exata dos bytes

O arquivo oficial exato funciona bem: importação isolada produziu 100.554 linhas, 10.621 do ANTECIPE, R$ 53.074.028,00, hash oficial; segunda execução manteve uma carga e 100.554 linhas.

O mesmo CSV lógico de uma linha, alterado apenas de LF para CRLF, produziu outro hash e duplicou carteira/carga:

```text
IMPORT_HASH=hash_equal:False,after_exact:(1, 1),after_crlf:(2, 2)
```

Não há unicidade da identidade global em `receivables` para impedir sobreposição entre arquivos.

**Recomendação:** **ESCALAR/DECIDIR** o contrato operacional. Se idempotência significa apenas “mesmos bytes”, documentar e bloquear importação quando já existe uma carteira ativa de outra carga. Se deve aceitar cópia logicamente equivalente/delta, usar identidade global/manifesto de carga e política transacional explícita. Não adicionar unicidade por fundo: a identidade exigida é global.

### I4 — Canal JSON não é equivalente ao CSV e aceita data-base inválida

`POST /api/receivables/evaluate` montava CSV por concatenação de strings, sem `csv.writer`, e usava silenciosamente `2026-10-22` quando a data era inválida.

```text
data_base="data-invalida" -> HTTP 200, response_date=2026-10-22
NOME_CEDENTE="EMPRESA;TESTE" via JSON -> LINHA_MALFORMADA_COLUNAS
mesmo valor em CSV corretamente cotado -> parsing normal e razões de negócio
```

**Recomendação:** **CORRIGIR**. Validar `data_base` como `date` no schema e passar objetos diretamente ao parser compartilhado, ou gerar CSV com `csv.writer` e cotação correta.

### I5 — Validação de configuração não cobre todo o schema alegado

`carregar_configuracao` rejeitou regra desconhecida, parâmetro negativo, booleano textual e código duplicado. Porém aceitou configuração sem `fundo.cnpj`, apesar da própria mensagem declarar nome e CNPJ obrigatórios:

```text
CONFIG_MISSING_FUND_CNPJ=ACCEPTED
```

Também aceita `validadores=[]`. Isso pode ser uma decisão de política administrativa válida, portanto não foi classificado automaticamente como defeito; deve ser decidido explicitamente. O teste `test_11_rule_version_publish_real_config_and_cas_concurrency` afirma validar imutabilidade/hash estável, mas não tenta mutar uma versão nem compara hash/configuração histórica; ele só publica, verifica um 409 e ativa.

**Recomendação:** **CORRIGIR** o CNPJ obrigatório e acrescentar testes reais de append-only, hash e snapshot histórico. **ESCALAR** se administradores podem remover/desativar todas as regras obrigatórias.

### I6 — Modo cadastral conservador não é o default do Compose

O código com `ENABLE_DEMO_CADASTRO=False` passou: inclusive CNPJ mapeado retorna `NAO_VERIFICADA`. Porém `docker-compose.yml` usava `${ENABLE_DEMO_CADASTRO:-true}` e `.env.example` sugeria `true`.

**Recomendação:** **CORRIGIR ou ESCALAR**. Um perfil claramente rotulado de demonstração pode habilitar fixture sintética; o perfil padrão deve ser conservador e expor a fonte no UI/API.

### I7 — Limites monetários divergem do DDL PostgreSQL

O domínio aceitava até `9999999999999999.99`, mas o DDL compilado contém `NUMERIC(15,2)`, que comporta somente 13 dígitos inteiros. `simulation_items` também armazenava valores somente em `NUMERIC(15,2)`, sem colunas de centavos.

**Recomendação:** **CORRIGIR/ALINHAR** parser, constante, `BIGINT` de centavos e `NUMERIC`; usar a menor capacidade comum. PostgreSQL deve validar o limite real e o round-trip.

### I8 — A suíte completa ainda não estava verde

Execução mais ampla do snapshot:

```text
pytest backend/tests qa
97 passed, 3 failed
```

As falhas estavam em `qa/test_api_integracao.py`: uma expectativa de aprovação incompatível com a fixture conservadora e dois `NameError` (`data`, `sim1_data`). São defeitos da suíte/fixture em edição, não prova de defeito adicional no produto, mas impedem usar “todos os testes passam”.

## Controles aceitos com evidência direta

- **Duplicidade global:** uma chave existente somente em outro fundo foi recusada como `DUPLICIDADE_HISTORICA`.
- **Parcelas distintas:** mesmo documento/tipo/partes com vencimentos diferentes teve ambas as parcelas aprovadas.
- **Concentração por raiz:** duas filiais válidas da raiz `04252011` foram agregadas; a primeira entrada permaneceu abaixo de 10% e a segunda foi recusada ao cruzar o limite.
- **Excesso histórico:** nova exposição na raiz já em 12,5% foi recusada; nova raiz pequena foi aprovada e diluiu a carteira.
- **Cadastro no código:** modo demo desligado retorna `NAO_VERIFICADA` para mapeados e desconhecidos.
- **Rollback do importador:** com `batch_size=1`, uma segunda linha inválida após `flush` deixou a contagem inalterada.
- **Arquivo oficial exato:** primeira importação isolada: `100554 / 10621 / 53074028 / SHA-256 313c75...`; repetição exata não duplicou.
- **Admin/erros já cobertos:** ausência de token retorna 503, token incorreto 401 sem eco; handler 422 remove `input`; Compose não contém `ADMIN_TOKEN` fixo.
- **Domínio:** cálculo R$ 5.000/90 dias = R$ 4.700 e dízima de 31 dias = R$ 979,33 permaneceram cobertos; a suite de domínio passou no snapshot.

## Comandos e resultados executados

Ambiente de todas as importações HTTP/backend: `DATABASE_URL=sqlite:///<arquivo-temporario>`, caminhos absolutos para regras/estoque e `.venv/Scripts/python.exe` carregado antes de importar `backend`.

```text
python -m pytest backend/tests qa/test_matriz_casos.py qa/test_safe_logs.py qa/test_security_r3.py -q --tb=short
=> 95 passed, 1 warning, exit 0

python -m pytest backend/tests qa -q --tb=short
=> 97 passed, 3 failed, 1 warning, exit 1

python scripts/check_submission.py
=> Auditoria do kit: OK, exit 0

python scripts/prompt_ledger.py audit
=> Prompts: 3 | Pendências: 1 | P0002, exit 1
```

O ledger aberto é esperado enquanto a entrega está em curso, mas precisa ser fechado antes da alegação final.

## Não verificado / risco residual

- PostgreSQL e Docker/Compose reais: indisponíveis. A falha de FK foi reproduzida com SQLite aplicando a mesma integridade referencial; execução PostgreSQL continua obrigatória após a correção.
- Concorrência real de criação/ativação de versões. `expected_active_version_id` era opcional e SQLite não comprova `SELECT FOR UPDATE` do PostgreSQL.
- Limite pré-multipart sob servidor real e transferência sem `Content-Length`.
- Logs reais do Uvicorn após a correção, incluindo query string e encoding.
- Round-trip dos limites monetários em PostgreSQL.
- Revisão visual Kimi não ocorreu por credencial expirada; nenhuma conclusão visual pode ser inferida.

## Decisão recomendada

- **ACEITAR** os controles de domínio listados acima e a repetição do arquivo oficial byte a byte.
- **CORRIGIR** B1–B4, I1, I2 e I4 antes da submissão; reexecutar as reproduções negativas, a suíte completa e o fluxo real.
- **ESCALAR** a semântica de idempotência entre arquivos, permissão para versão sem regras e default de cadastro demo.
- Não afirmar “seguro”, “PostgreSQL compatível”, “todos os testes passam” ou “pronto” até as lacunas acima terem evidência nova.
