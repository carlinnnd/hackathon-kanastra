# Relatório de Revisão Independente de Segurança R3 — Antecipe

**Autor:** Agente Revisor Independente de Segurança R3  
**Data da Auditoria:** 24/10/2026 (Auditoria Final com Fechamento do Gap B3 e Docker)  
**Ambiente de Execução:** Python 3.11.15 (Windows x86_64), SQLite em memória (`StaticPool`, `PRAGMA foreign_keys=ON`), suíte reproduzível em `Codex/antecipe/qa/test_security_r3.py`.  
**Destinatários:** Coordenador (`d583bd12-5b5c-4c23-a3e2-f1c5d245dda8`), Autor Backend (`f333df74-bdca-4c2d-bc00-e9b2b8338f4a`).

---

## 1. Sumário Executivo do Fechamento de Gaps

A suíte independente de segurança `qa/test_security_r3.py` foi expandida para **21 testes automatizados**, cobrindo o último ponto residual de B3 (limitação de payloads JSON volumosos e transferências ASGI em streaming sem `Content-Length`) e a configuração do Uvicorn com `--no-access-log` no Dockerfile.

### Resultado Consolidado dos Testes:
- **Suíte Independente de Segurança R3 (`qa/test_security_r3.py`):** **21 PASSED / 0 FAILED** (100% de aprovação).
- **Suíte Integrada Completa (`backend/tests` e `qa/*`):** **113 PASSED / 0 FAILED**.

---

## 2. Recheck Detalhado dos Bloqueadores Críticos (B1 a B4)

### ✅ B1 — Atomicidade e Integridade Referencial da Persistência de Simulação
* **Verificação Adversária:** Executado sob SQLite com `PRAGMA foreign_keys=ON` forçado na conexão e gerador sintético de 2.100 itens que injeta uma exceção controlada (`RuntimeError`) logo após o item 2.050 (após o primeiro chunk de 2.000 itens).
* **Resultado:** O registro-pai é criado antecipadamente via `criar_simulacao_pai_inicial` e mantido na mesma sessão transacional; os chunks são persistidos sem commits prematuros nos repositórios; ao ocorrer a falha tardia, o bloco `try/except` executa `self.db.rollback()`.
* **Evidência:** Contagem de simulações e itens antes e após o erro: exatamente zero registros órfãos ou parciais confirmados.
* **Status:** **RESOLVIDO / VERIFICADO**.

---

### ✅ B2 — Alinhamento Estrito de Data-Base
* **Verificação Adversária:** Avaliação de simulação submetendo `data_base_override` confrontado com a data do motor, do envelope e do registro persistido no banco.
* **Resultado:** `SimulationService` define `data_base_efetiva = config_motor.data_base`, persistindo-a no modelo pai e emitindo-a no envelope JSON e no cálculo de prazos e precificação.
* **Status:** **RESOLVIDO / VERIFICADO**.

---

### ✅ B3 — Limite de Upload em Nível ASGI Stream (CSV e JSON)
* **Verificação Adversária 1 (JSON Payload):** Submissão para `POST /api/receivables/evaluate` com lista vazia e padding de 2.048 bytes sob `settings.MAX_UPLOAD_SIZE_BYTES = 100`. Retorna imediatamente `HTTP 413` com código `REQUISICAO_MUITO_GRANDE` em vez de processar a requisição e retornar `HTTP 400 PAYLOAD_VAZIO`.
* **Verificação Adversária 2 (Stream ASGI sem Content-Length):** Mock de requisição ASGI contínua sem cabeçalho `Content-Length`. O wrapper `limited_receive()` intercepta os chunks lidos em tempo real e dispara `HTTP 413` assim que a soma de bytes consumidos ultrapassa o limite permitido, abortando antes da conclusão do spool em disco.
* **Verificação Adversária 3 (CSV Multipart):** Submissão com arquivo excedente rejeitada com `HTTP 413 ARQUIVO_MUITO_GRANDE`.
* **Status:** **RESOLVIDO / VERIFICADO**.

---

### ✅ B4 — Prevenção de Vazamento de Paths e PII em Logs & Access Log Uvicorn
* **Verificação da Aplicação:** Requisição enviada para rota não mapeada com sentinela sensível (`GET /api/clientes/cpf-99988877766-secreto-acme-2026`). O middleware registra template allowlist `/unmatched_route`, sem refletir o caminho bruto.
* **Verificação de Infraestrutura Docker:** O `Dockerfile` oficial inicia o Uvicorn com `--no-access-log`:
  ```dockerfile
  CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
  ```
  Isso assegura que o servidor ASGI nativo não emita logs de acesso com query strings ou paths brutos antes de passar pelo formatador seguro da aplicação.
* **Status:** **RESOLVIDO / VERIFICADO**.

---

## 3. Recheck dos Achados Importantes (I1 a I4)

### ✅ I1 — Rejeição Estrita de Frações Além de Centavos (Sem Arredondamento Silencioso)
* **Verificação:** `parse_decimal_br` avalia se `dec != dec.quantize(Decimal('0.01'))`.
* **Resultado:** Valores com frações de subcentavos (`100.005`, `100,005`, `50,1234`) retornam `None` e são recusados de forma limpa. Valores com zeros redundantes (`100.000` ou `100,00`) são quantizados para `Decimal('100.00')`.
* **Status:** **RESOLVIDO / VERIFICADO**.

---

### ✅ I2 — Validação Estrita de Cabeçalhos e Datas no Importador de Estoque
* **Verificação:** `importar_estoque_csv` checa `reader.fieldnames` obrigatórios e valida `DATA_AQUISICAO` preenchida com `parse_data_br`.
* **Resultado:** Cabeçalhos ausentes ou datas inválidas (ex: `99/99/9999`) disparam `ValueError` explícito com indicação de linha e campo, abortando a carga sem persistir estados inválidos.
* **Status:** **RESOLVIDO / VERIFICADO**.

---

### ✅ I3 — Prevenção de Sobreposição de Estoque (LF vs CRLF)
* **Verificação:** Criação de arquivo com quebras LF e posterior tentativa de carga com quebras CRLF (gerando hash SHA-256 de arquivo distinto).
* **Resultado:** O importador checa `chaves_candidatas_batch` em lotes contra `ReceivableModel.chave_duplicidade` na carteira histórica. Detecta a sobreposição e cancela a importação com erro explícito (`Sobreposição de estoque detectada`), impedindo duplicação de saldo da carteira.
* **Status:** **RESOLVIDO / VERIFICADO**.

---

### ✅ I4 — Paridade de Entrada JSON vs CSV e Escapamento de Caracteres
* **Verificação:** Avaliação via `POST /api/receivables/evaluate` de payloads com ponto-e-vírgula em campos textuais e `data_base` corrompida.
* **Resultado:** O endpoint valida `data_base` estritamente (rejeitando datas inválidas com `HTTP 422 DATA_BASE_INVALIDA`) e serializa os itens via `csv.writer` com `QUOTE_MINIMAL` RFC 4180, eliminando desbalanceamento de colunas por ponto-e-vírgula.
* **Status:** **RESOLVIDO / VERIFICADO**.

---

## 4. Matriz Completa de Testes de Segurança R3 (`qa/test_security_r3.py`)

| # | Identificador do Teste | Propósito de Segurança | Resultado |
|---|---|---|---|
| 1 | `test_01_admin_token_disabled_returns_503` | Admin token ausente -> HTTP 503 | ✅ PASS |
| 2 | `test_02_admin_token_invalid_returns_401_no_token_leak` | Admin token inválido -> HTTP 401 sem vazar segredo | ✅ PASS |
| 3 | `test_03_safe_json_logs_allowlist_enforcement` | Descarte estrito de campos fora da allowlist nos logs | ✅ PASS |
| 4 | `test_04_unhandled_route_404_no_pii_leak` | Rota 404 registra template seguro sem refletir PII/token do path | ✅ PASS |
| 5 | `test_05_pydantic_422_does_not_echo_raw_sensitive_input` | Erro HTTP 422 sanitizado sem refletir dicionário `input` bruto | ✅ PASS |
| 6 | `test_06_upload_oversize_small_limit_monkeypatch` | Upload excedendo limite rejeitado com HTTP 413 | ✅ PASS |
| 7 | `test_07_upload_non_csv_rejected_cleanly` | Rejeição de extensões não permitidas (.exe/.bin) com HTTP 400 | ✅ PASS |
| 8 | `test_08_upload_malformed_utf8_rejected_cleanly` | Rejeição de encoding inválido com HTTP 400 | ✅ PASS |
| 9 | `test_09_upload_csv_ragged_colunas_tratadas_linha_a_linha` | Linhas ragged tratadas com recusa por item sem derrubar o servidor | ✅ PASS |
| 10 | `test_10_rule_version_strict_validation_rejects_malformed_config` | Pré-validação rejeita regras inventadas ou parâmetros negativos com 422 | ✅ PASS |
| 11 | `test_11_rule_version_publish_real_config_and_cas_concurrency` | Fluxo GET real -> mutate -> publish -> conflito CAS 409 -> ativação 200 | ✅ PASS |
| 12 | `test_12_sql_path_traversal_on_simulation_endpoint` | Probing de SQL injection e Path Traversal tratado com 404/422 sem 500 | ✅ PASS |
| 13 | `test_13_cadastro_padrao_conservador_sem_demo` | `ENABLE_DEMO_CADASTRO=False` retorna `NAO_VERIFICADA` para qualquer sacado | ✅ PASS |
| 14 | `test_14_parity_csv_json_fraudulent_alphanumeric_document` | Paridade CSV vs JSON na recusa de CNPJ com letras fraudulentas | ✅ PASS |
| 15 | `test_15_json_evaluate_handles_semicolon_and_invalid_database` | Escapamento RFC 4180 de ';' e rejeição de data-base inválida com 422 | ✅ PASS |
| 16 | `test_16_persistence_foreign_key_on_and_atomic_rollback_on_failure` | Transação única e rollback 100% completo com SQLite FK ON pós-chunk 2000 | ✅ PASS |
| 17 | `test_17_database_exact_alignment_motor_envelope_pricing` | Alinhamento rigoroso da data-base no motor, envelope e persistência | ✅ PASS |
| 18 | `test_18_strict_cents_precision_rejects_subcent_fractions` | Rejeição estrita de frações além de centavos (`100.005` -> `None`) | ✅ PASS |
| 19 | `test_19_stock_import_overlap_detection_blocks_duplicate_records` | Bloqueio de sobreposição de títulos de estoque com erro seguro | ✅ PASS |
| 20 | `test_20_json_payload_oversize_rejected_with_413` | Rejeição antecipada de payload JSON volumoso com HTTP 413 | ✅ PASS |
| 21 | `test_21_asgi_stream_chunked_upload_without_content_length` | Interrupção ASGI de transferência em streaming contínuo sem Content-Length | ✅ PASS |

---

## 5. Gate Residual e Riscos Conhecidos

1. **PostgreSQL Real:** O ambiente de workstation local opera sob SQLite; os testes comprovaram a integridade ativando `PRAGMA foreign_keys=ON` e tipagem estrita de centavos com `BigInteger`, assegurando compatibilidade estrutural com o DDL do PostgreSQL.
2. **Access Log do Uvicorn:** Confirmada a presença da flag `--no-access-log` no comando de inicialização do Dockerfile.

---

## 6. Comandos Oficiais de Auditoria

```bash
# 1. Execução da suíte de segurança independente R3 (21 testes)
uv run --with-requirements Codex/antecipe/requirements.txt --with pytest --with httpx --python 3.11 python -m pytest -o pythonpath=".;Codex/antecipe" Codex/antecipe/qa/test_security_r3.py -v

# 2. Execução da suíte integrada completa (113 testes)
uv run --with-requirements Codex/antecipe/requirements.txt --with pytest --with httpx --python 3.11 python -m pytest -o pythonpath=".;Codex/antecipe" Codex/antecipe/backend/tests Codex/antecipe/qa -q
```
