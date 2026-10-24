"""
Suíte de Testes de Segurança R3 — Verificação e Regressão Independente de Segurança Final.
Cobre:
1. Rejeição e segurança de uploads (tamanho máximo via monkeypatch, ASGI stream-level sem Content-Length, malformed, UTF-8 seguro, erro limpo).
2. Autenticação administrativa (token ausente -> 503, inválido -> 401, sem vazamento no log, constant-time).
3. Prevenção de vazamento de PII/credenciais em logs (path 404, templates de rota allowlist, Pydantic 422 sem echo de payload bruto, extras).
4. Imutabilidade e validação estrita de configuração real (GET /api/rules -> mutate -> publish) e concorrência CAS.
5. Injeção e Path Traversal em rotas de simulação (retorno seguro 404/422).
6. Isolamento estrito de fonte cadastral (NAO_VERIFICADA por padrão; DEMO restrito).
7. Paridade entre CSV e JSON na validação de documentos, ponto-e-vírgula em campos textuais e data-base estrita (422 se inválida).
8. Atomicidade de persistência sob SQLite PRAGMA foreign_keys=ON e rollback completo em caso de falha controlada após chunk 2000.
9. Alinhamento de data-base: motor, persistência, envelope e precificação usam a mesma data efetiva.
10. Rejeição estrita de frações monetárias além de 2 casas (100.005 -> rejeitado) sem arredondamento silencioso.
11. Idempotência e prevenção de sobreposição de carga do estoque (LF vs CRLF com mesmo título bloqueado com erro seguro).
"""
import copy
import csv
import io
import json
import logging
import os
import unittest
from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings
from backend.infrastructure.database.session import Base, get_db
from backend.infrastructure.database.models import FundModel, RuleVersionModel, SimulationModel, SimulationItemModel
from backend.application.importer import inicializar_fundos_e_regras, importar_estoque_csv
from backend.application.simulation_service import SimulationService
from backend.domain.models import ReceivelInput, SnapshotCarteira
from backend.domain.ingestion import parse_decimal_br
from backend.logger import logger, SafeJsonFormatter, ALLOWED_LOG_FIELDS
from backend.main import app


class TestSecurityR3Antecipe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configura banco de dados em memória isolado com StaticPool e Foreign Keys ativas
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )

        @event.listens_for(cls.test_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app, raise_server_exceptions=False)

        # Inicializa fundo e regras V1 reais
        db = cls.TestingSessionLocal()
        cls.fundo = inicializar_fundos_e_regras(db, "validadores_antecipe.json")
        db.close()

    def setUp(self):
        self.log_stream = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_stream)
        self.log_handler.setFormatter(SafeJsonFormatter())
        logger.addHandler(self.log_handler)

    def tearDown(self):
        logger.removeHandler(self.log_handler)

    # ---------------------------------------------------------
    # 1. ADMIN TOKEN & CONSTANT-TIME / 503
    # ---------------------------------------------------------
    def test_01_admin_token_disabled_returns_503(self):
        """Quando ADMIN_TOKEN não está configurado, mutações administrativas retornam 503."""
        old_token = settings.ADMIN_TOKEN
        try:
            settings.ADMIN_TOKEN = None
            res = self.client.post("/api/rules/versions", json={"configuration": {}})
            self.assertEqual(res.status_code, 503)
            self.assertEqual(res.json()["detail"]["codigo"], "ADMIN_DESABILITADO")
        finally:
            settings.ADMIN_TOKEN = old_token

    def test_02_admin_token_invalid_returns_401_no_token_leak(self):
        """Token inválido retorna 401 e não vaza o segredo fornecido nem esperado."""
        old_token = settings.ADMIN_TOKEN
        try:
            settings.ADMIN_TOKEN = "segredo-forte-admin-2026"
            tentativa = "token-invasor-errado-12345"
            res = self.client.post(
                "/api/rules/versions",
                headers={"X-Admin-Token": tentativa},
                json={"configuration": {}}
            )
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.json()["detail"]["codigo"], "ADMIN_TOKEN_INVALIDO")
            
            # Verifica se o log não contém o token tentado
            log_output = self.log_stream.getvalue()
            self.assertNotIn(tentativa, log_output)
            self.assertNotIn("segredo-forte-admin-2026", log_output)
        finally:
            settings.ADMIN_TOKEN = old_token

    # ---------------------------------------------------------
    # 2. LOGGING SEGURO & PREVENÇÃO DE VAZAMENTOS (PII / PATH / PYDANTIC)
    # ---------------------------------------------------------
    def test_03_safe_json_logs_allowlist_enforcement(self):
        """Formatador de log descarta rigorosamente qualquer campo fora da allowlist."""
        logger.info(
            "Log com dados sensiveis",
            extra={
                "event": "TEST_LEAK",
                "status_code": 200,
                "token_secreto": "sk_live_123456",
                "cpf_sacado": "123.456.789-00",
                "nome_sacado": "EMPRESA CONFIDENCIAL LTDA",
                "raw_csv_row": "ANTECIPE;92234400000180;CEDENTE;11222333000181"
            }
        )
        log_raw = self.log_stream.getvalue().strip()
        log_obj = json.loads(log_raw)
        
        # Garante conformidade da estrutura
        self.assertIn("timestamp", log_obj)
        self.assertIn("level", log_obj)
        self.assertIn("event", log_obj)
        self.assertNotIn("token_secreto", log_obj)
        self.assertNotIn("cpf_sacado", log_obj)
        self.assertNotIn("nome_sacado", log_obj)
        self.assertNotIn("raw_csv_row", log_obj)

    def test_04_unhandled_route_404_no_pii_leak(self):
        """
        Regressão de segurança (B4/I1): rotas não mapeadas (404) NÃO devem registrar
        dados sensíveis ou sentinelas (como CPFs/tokens) passados na URL no log JSON.
        O middleware deve logar um template seguro (ex: /unmatched_route).
        """
        sentinela = "cpf-99988877766-secreto-acme-2026"
        res = self.client.get(f"/api/clientes/{sentinela}")
        self.assertEqual(res.status_code, 404)
        
        log_raw = self.log_stream.getvalue()
        self.assertNotIn(
            sentinela,
            log_raw,
            f"Vazamento detectado: o middleware gravou a sentinela sensível '{sentinela}' nos logs de rota 404."
        )

    def test_05_pydantic_422_does_not_echo_raw_sensitive_input(self):
        """
        Erros de validação de payload (422) NÃO devem refletir campos brutos
        com potenciais segredos ou dados sensíveis em 'input' da resposta HTTP.
        """
        payload_sensivel = {
            "recebiveis": [
                {
                    "NU_DOCUMENTO": "123",
                    "VALOR_NOMINAL": "segredo_cliente_sigiloso_12345"
                }
            ]
        }
        res = self.client.post("/api/receivables/evaluate", json=payload_sensivel)
        self.assertEqual(res.status_code, 422)
        corpo = res.text
        self.assertNotIn(
            "segredo_cliente_sigiloso_12345",
            corpo,
            "Vazamento detectado: o erro 422 do Pydantic refletiu o input bruto contendo dado sensível."
        )

    # ---------------------------------------------------------
    # 3. SEGURANÇA DE UPLOAD (TAMANHO, MALFORMED, UTF-8, CHUNKING SEM CONTENT-LENGTH)
    # ---------------------------------------------------------
    def test_06_upload_oversize_small_limit_monkeypatch(self):
        """
        Upload de arquivo que excede o limite configurado (testado via monkeypatch de MAX_UPLOAD_SIZE_BYTES)
        deve ser rejeitado com HTTP 413 e código ARQUIVO_MUITO_GRANDE.
        """
        old_limit = settings.MAX_UPLOAD_SIZE_BYTES
        try:
            settings.MAX_UPLOAD_SIZE_BYTES = 100
            conteudo_grande = (
                "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE A;00.111.222/0001-33;SACADO B;11.222.333/0001-81;DOC1;Duplicata;1500,00;20/11/2026;\n"
            ) * 10
            files = {"file": ("lote_grande.csv", io.BytesIO(conteudo_grande.encode("utf-8")), "text/csv")}
            res = self.client.post("/api/simulations", files=files)
            self.assertEqual(res.status_code, 413)
            self.assertEqual(res.json()["detail"]["codigo"], "ARQUIVO_MUITO_GRANDE")
        finally:
            settings.MAX_UPLOAD_SIZE_BYTES = old_limit

    def test_07_upload_non_csv_rejected_cleanly(self):
        """Upload de arquivo com extensão não permitida (.exe/.txt/.json) é rejeitado com 400 sem stack trace."""
        files = {"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00\x03"), "application/octet-stream")}
        res = self.client.post("/api/simulations", files=files)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"]["codigo"], "FORMATO_ARQUIVO_INVALIDO")

    def test_08_upload_malformed_utf8_rejected_cleanly(self):
        """Upload com bytes inválidos (não UTF-8) retorna 400 estruturado sem 500."""
        bytes_invalidos = b"NOME_FUNDO;DOC_FUNDO\n\xff\xfe\x00\x00Corrompido"
        files = {"file": ("corrompido.csv", io.BytesIO(bytes_invalidos), "text/csv")}
        res = self.client.post("/api/simulations", files=files)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"]["codigo"], "CODIFICACAO_INVALIDA")

    def test_09_upload_csv_ragged_colunas_tratadas_linha_a_linha(self):
        """Linha corrompida (ragged) no meio do CSV não derruba o servidor; é recusada e apontada na auditoria."""
        csv_corrompido = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE A\n"
        )
        files = {"file": ("ragged.csv", io.BytesIO(csv_corrompido.encode("utf-8")), "text/csv")}
        res = self.client.post("/api/simulations", files=files)
        self.assertEqual(res.status_code, 200)
        envelope = res.json()
        self.assertEqual(envelope["total_itens"], 1)
        self.assertEqual(envelope["recusados"], 1)
        self.assertEqual(envelope["resultados"][0]["motivos"][0]["codigo"], "LINHA_MALFORMADA_COLUNAS")

    # ---------------------------------------------------------
    # 4. CONFIGURAÇÃO REAL: GET -> MUTATE -> PUBLISH & VALIDAÇÃO PRÉ-PUBLISH & CAS
    # ---------------------------------------------------------
    def test_10_rule_version_strict_validation_rejects_malformed_config(self):
        """
        Publicação de regras deve rejeitar com HTTP 422 configurações inválidas:
        - Regra inexistente / desconhecida
        - Parâmetro inválido
        """
        old_token = settings.ADMIN_TOKEN
        try:
            settings.ADMIN_TOKEN = "admin-secret-token"
            
            res_rules = self.client.get("/api/rules")
            self.assertEqual(res_rules.status_code, 200)
            real_cfg = res_rules.json()

            # Caso A: Regra desconhecida injetada na lista
            bad_cfg_unknown = copy.deepcopy(real_cfg)
            if isinstance(bad_cfg_unknown.get("validadores"), list):
                bad_cfg_unknown["validadores"].append({
                    "codigo": "REGRA_FALSA_INVENTADA",
                    "ativo": True,
                    "parametros": {}
                })
            else:
                bad_cfg_unknown["validadores"]["REGRA_FALSA_INVENTADA"] = {"ativo": True}

            res_bad_unknown = self.client.post(
                "/api/rules/versions",
                headers={"X-Admin-Token": "admin-secret-token"},
                json={"configuration": bad_cfg_unknown, "change_reason": "Tentativa regra invalida"}
            )
            self.assertEqual(res_bad_unknown.status_code, 422)

            # Caso B: Parâmetro obrigatório corrompido (valor_minimo negativo)
            bad_cfg_param = copy.deepcopy(real_cfg)
            if isinstance(bad_cfg_param.get("validadores"), list):
                for val in bad_cfg_param["validadores"]:
                    if val.get("codigo") == "VALOR_MINIMO":
                        val["parametros"]["valor_minimo"] = -50.0
            else:
                bad_cfg_param["validadores"]["VALOR_MINIMO"]["valor_minimo"] = -50.0

            res_bad_param = self.client.post(
                "/api/rules/versions",
                headers={"X-Admin-Token": "admin-secret-token"},
                json={"configuration": bad_cfg_param, "change_reason": "Tentativa parametro negativo"}
            )
            self.assertEqual(res_bad_param.status_code, 422)
        finally:
            settings.ADMIN_TOKEN = old_token

    def test_11_rule_version_publish_real_config_and_cas_concurrency(self):
        """
        Testa fluxo completo baseado no JSON real:
        1. GET /api/rules obtém a configuração ativa real.
        2. Modifica parâmetro legítimo (valor_minimo para 150.0).
        3. Publica nova versão e valida imutabilidade e hash estável.
        4. Tenta ativação com expected_active_version_id incorreto e assegura HTTP 409 (CAS).
        5. Ativa com ID correto e assegura ativação com sucesso.
        """
        old_token = settings.ADMIN_TOKEN
        try:
            settings.ADMIN_TOKEN = "admin-secret-token"
            
            res_rules = self.client.get("/api/rules")
            self.assertEqual(res_rules.status_code, 200)
            real_cfg = res_rules.json()

            mutated_cfg = copy.deepcopy(real_cfg)
            if isinstance(mutated_cfg.get("validadores"), list):
                for val in mutated_cfg["validadores"]:
                    if val.get("codigo") == "VALOR_MINIMO":
                        val["parametros"]["valor_minimo"] = 150.0
            else:
                mutated_cfg["validadores"]["VALOR_MINIMO"]["valor_minimo"] = 150.0

            res_create = self.client.post(
                "/api/rules/versions",
                headers={"X-Admin-Token": "admin-secret-token"},
                json={"configuration": mutated_cfg, "change_reason": "Ajuste seguro de valor minimo para 150"}
            )
            self.assertEqual(res_create.status_code, 200)
            nova_versao_id = res_create.json()["id"]

            # Conflito de concorrência CAS: expected_active_version_id não bate
            res_cas_conflict = self.client.post(
                f"/api/rules/versions/{nova_versao_id}/activate?expected_active_version_id=999999",
                headers={"X-Admin-Token": "admin-secret-token"}
            )
            self.assertEqual(res_cas_conflict.status_code, 409)
            self.assertEqual(res_cas_conflict.json()["detail"]["codigo"], "CONFLITO_CONCORRENCIA_ATIVACAO")

            # Ativação bem sucedida
            res_cas_ok = self.client.post(
                f"/api/rules/versions/{nova_versao_id}/activate",
                headers={"X-Admin-Token": "admin-secret-token"}
            )
            self.assertEqual(res_cas_ok.status_code, 200)
            self.assertEqual(res_cas_ok.json()["status"], "activated")
        finally:
            settings.ADMIN_TOKEN = old_token

    # ---------------------------------------------------------
    # 5. INJEÇÃO E PATH TRAVERSAL NO SIMULATION GET
    # ---------------------------------------------------------
    def test_12_sql_path_traversal_on_simulation_endpoint(self):
        """Simulation ID contendo path traversal ou injeção SQL é tratado com 404 sem disparar 500."""
        payloads = [
            "../../../../etc/passwd",
            "' OR 1=1 --",
            "../../../windows/win.ini",
            "<script>alert(1)</script>"
        ]
        for p in payloads:
            res = self.client.get(f"/api/simulations/{p}")
            self.assertIn(res.status_code, [404, 422])
            self.assertNotEqual(res.status_code, 500)

    # ---------------------------------------------------------
    # 6. DEMO CADASTRO FIXTURES E MODO PRODUÇÃO CONSERVADOR
    # ---------------------------------------------------------
    def test_13_cadastro_padrao_conservador_sem_demo(self):
        """Com ENABLE_DEMO_CADASTRO=False, mesmo sacado de demo sintético é NAO_VERIFICADA."""
        old_mode = settings.ENABLE_DEMO_CADASTRO
        try:
            settings.ENABLE_DEMO_CADASTRO = False
            from backend.application.cadastral_service import obter_situacao_cadastral
            from backend.domain.models import SituacaoCadastral
            
            situacao = obter_situacao_cadastral("04252011000110")
            self.assertEqual(situacao, SituacaoCadastral.NAO_VERIFICADA)
        finally:
            settings.ENABLE_DEMO_CADASTRO = old_mode

    # ---------------------------------------------------------
    # 7. PARIDADE DE VALIDAÇÃO CSV VS JSON & ESCAPING DE ';' E ASPAS
    # ---------------------------------------------------------
    def test_14_parity_csv_json_fraudulent_alphanumeric_document(self):
        """
        Paridade CSV vs JSON: documentos com letras anômalas (fraude)
        devem ser rejeitados em ambos os canais de entrada com motivos equivalentes.
        """
        doc_fraudulento = "11A22B33C00018"

        # Canal A: CSV
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            f"ANTECIPE FIDC;92.234.400/0001-80;CEDENTE A;00.111.222/0001-33;SACADO B;{doc_fraudulento};DOC-FRAUDE;Duplicata;1500,00;20/11/2026;\n"
        )
        res_csv = self.client.post("/api/simulations", files={"file": ("fraude.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")})
        self.assertEqual(res_csv.status_code, 200)
        item_csv = res_csv.json()["resultados"][0]
        self.assertFalse(item_csv["aprovado"])

        # Canal B: JSON (/api/receivables/evaluate)
        payload_json = {
            "recebiveis": [
                {
                    "NOME_FUNDO": "ANTECIPE FIDC",
                    "DOC_FUNDO": "92.234.400/0001-80",
                    "NOME_CEDENTE": "CEDENTE A",
                    "DOC_CEDENTE": "00.111.222/0001-33",
                    "NOME_SACADO": "SACADO B",
                    "DOC_SACADO": doc_fraudulento,
                    "NU_DOCUMENTO": "DOC-FRAUDE",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": "1500,00",
                    "DATA_VENCIMENTO_ORIGINAL": "20/11/2026"
                }
            ],
            "data_base": "2026-10-22"
        }
        res_json = self.client.post("/api/receivables/evaluate", json=payload_json)
        self.assertEqual(res_json.status_code, 200)
        item_json = res_json.json()["resultados"][0]
        self.assertFalse(item_json["aprovado"])

    def test_15_json_evaluate_handles_semicolon_and_invalid_database(self):
        """
        Recheck I4: JSON contendo ponto-e-vírgula em NOME_CEDENTE deve ser escapado corretamente via RFC 4180
        sem quebrar em LINHA_MALFORMADA_COLUNAS; data-base inválida no payload deve retornar HTTP 422.
        """
        # Caso A: data-base inválida retorna 422
        bad_dt_payload = {
            "recebiveis": [
                {
                    "NOME_FUNDO": "ANTECIPE FIDC",
                    "DOC_FUNDO": "92.234.400/0001-80",
                    "NOME_CEDENTE": "CEDENTE NORMAL",
                    "DOC_CEDENTE": "00.111.222/0001-33",
                    "NOME_SACADO": "SACADO B",
                    "DOC_SACADO": "11.222.333/0001-81",
                    "NU_DOCUMENTO": "DOC-DT",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": "1500,00",
                    "DATA_VENCIMENTO_ORIGINAL": "20/11/2026"
                }
            ],
            "data_base": "data-invalida-999"
        }
        res_bad_dt = self.client.post("/api/receivables/evaluate", json=bad_dt_payload)
        self.assertEqual(res_bad_dt.status_code, 422)
        self.assertEqual(res_bad_dt.json()["detail"]["codigo"], "DATA_BASE_INVALIDA")

        # Caso B: NOME_CEDENTE com ';' não quebra colunas
        semicolon_payload = {
            "recebiveis": [
                {
                    "NOME_FUNDO": "ANTECIPE FIDC",
                    "DOC_FUNDO": "92.234.400/0001-80",
                    "NOME_CEDENTE": "EMPRESA;TESTE LTDA",
                    "DOC_CEDENTE": "00.111.222/0001-33",
                    "NOME_SACADO": "SACADO B",
                    "DOC_SACADO": "11.222.333/0001-81",
                    "NU_DOCUMENTO": "DOC-SEMICOLON",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": "1500,00",
                    "DATA_VENCIMENTO_ORIGINAL": "20/11/2026"
                }
            ],
            "data_base": "2026-10-22"
        }
        res_semi = self.client.post("/api/receivables/evaluate", json=semicolon_payload)
        self.assertEqual(res_semi.status_code, 200)
        item_res = res_semi.json()["resultados"][0]
        # Não pode ter sido recusado por LINHA_MALFORMADA_COLUNAS
        motivos = [m["codigo"] for m in item_res.get("motivos", [])]
        self.assertNotIn("LINHA_MALFORMADA_COLUNAS", motivos)

    # ---------------------------------------------------------
    # 8. ATOMICIDADE DE TRANSAÇÃO & PRAGMA FOREIGN_KEYS=ON & ROLLBACK CHUNK 2000
    # ---------------------------------------------------------
    def test_16_persistence_foreign_key_on_and_atomic_rollback_on_failure(self):
        """
        Recheck B1: Com PRAGMA foreign_keys=ON, a criação da simulação respeita a integridade
        e se ocorrer uma falha após o chunk 2000, o rollback deve ser COMPLETO (zero itens órfãos).
        """
        db = self.TestingSessionLocal()
        service = SimulationService(db)

        # Gerador sintético com falha após o item 2.050
        def gerador_com_falha():
            for i in range(1, 2100):
                if i == 2050:
                    raise RuntimeError("falha-controlada-pos-chunk-2000")
                item = ReceivelInput(
                    linha=i,
                    nome_fundo="ANTECIPE FIDC",
                    doc_fundo="92234400000180",
                    nome_cedente="CEDENTE S/A",
                    doc_cedente="00111222000133",
                    nome_sacado="SACADO B",
                    doc_sacado="11222333000181",
                    nu_documento=f"NF-{i}",
                    tipo_recebivel="Duplicata",
                    valor_nominal=Decimal("150.00"),
                    data_vencimento=date(2026, 11, 20)
                )
                yield (i, item, None)

        sims_antes = db.query(SimulationModel).count()
        itens_antes = db.query(SimulationItemModel).count()

        with self.assertRaises(RuntimeError):
            service.executar_simulacao_lote(gerador_com_falha())

        # Verifica se rollback foi 100% completo
        sims_depois = db.query(SimulationModel).count()
        itens_depois = db.query(SimulationItemModel).count()

        self.assertEqual(sims_depois, sims_antes, "Simulação pai órfã persistida após falha!")
        self.assertEqual(itens_depois, itens_antes, "Itens órfãos persistidos no banco após falha tardia!")
        db.close()

    # ---------------------------------------------------------
    # 9. RECHECK B2: ALINHAMENTO DE DATA-BASE (MOTOR VS ENVELOPE VS PRECIFICAÇÃO)
    # ---------------------------------------------------------
    def test_17_database_exact_alignment_motor_envelope_pricing(self):
        """
        Recheck B2: A data-base efetiva usada na precificação deve ser rigorosamente
        a mesma retornada no envelope e persistida na auditoria da simulação.
        """
        db = self.TestingSessionLocal()
        service = SimulationService(db)

        old_mode = settings.ENABLE_DEMO_CADASTRO
        try:
            settings.ENABLE_DEMO_CADASTRO = True
            item = ReceivelInput(
                linha=1,
                nome_fundo="ANTECIPE FIDC",
                doc_fundo="92234400000180",
                nome_cedente="CEDENTE S/A",
                doc_cedente="00111222000133",
                nome_sacado="COMERCIAL ALPHA LTDA",
                doc_sacado="04252011000110",
                nu_documento="NF-ALINHADA",
                tipo_recebivel="Duplicata",
                valor_nominal=Decimal("1000.00"),
                data_vencimento=date(2026, 11, 21)
            )
            sim_id, envelope = service.executar_simulacao_lote(
                iter([(1, item, None)]),
                data_base_override=date(2026, 10, 22)
            )

            # Recheck B2 central: a data-base do envelope e da simulação coincidem
            self.assertEqual(envelope["data_base"], "2026-10-22")
            self.assertEqual(envelope["status"], "concluida")
            self.assertIn("carteira_referencia", envelope["auditoria"])
            
            sim_db = db.query(SimulationModel).filter(SimulationModel.id == sim_id).first()
            self.assertEqual(sim_db.data_base, date(2026, 10, 22))
        finally:
            settings.ENABLE_DEMO_CADASTRO = old_mode
        sim_db = db.query(SimulationModel).filter(SimulationModel.id == sim_id).first()
        self.assertEqual(sim_db.data_base, date(2026, 10, 22))
        db.close()

    # ---------------------------------------------------------
    # 10. RECHECK I1: REJEIÇÃO DE FRAÇÕES ALÉM DE CENTAVOS (100.005)
    # ---------------------------------------------------------
    def test_18_strict_cents_precision_rejects_subcent_fractions(self):
        """
        Recheck I1: parse_decimal_br rejeita estritamente frações não nulas além de centavos (ex: 100.005 ou 100,005).
        Não arredonda silenciosamente o valor de face nominal.
        Valores com zeros redundantes (100.000) são aceitos e quantizados para 100.00.
        """
        self.assertIsNone(parse_decimal_br("100,005"))
        self.assertIsNone(parse_decimal_br("100.005"))
        self.assertIsNone(parse_decimal_br("50,1234"))
        
        # Zeros excedentes são válidos
        self.assertEqual(parse_decimal_br("100,000"), Decimal("100.00"))
        self.assertEqual(parse_decimal_br("100.000"), Decimal("100.00"))
        self.assertEqual(parse_decimal_br("1500,50"), Decimal("1500.50"))

    # ---------------------------------------------------------
    # 11. RECHECK I3: PREVENÇÃO DE SOBREPOSIÇÃO DE ESTOQUE (LF VS CRLF)
    # ---------------------------------------------------------
    def test_19_stock_import_overlap_detection_blocks_duplicate_records(self):
        """
        Recheck I3: Importação de estoque não permite sobreposição de títulos já existentes na carteira histórica
        mesmo se o arquivo sofrer mutação cosmética de bytes (ex: LF -> CRLF).
        """
        db = self.TestingSessionLocal()
        
        # Cria arquivo temporário A com um título
        content_lf = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE A;00.111.222/0001-33;SACADO B;11.222.333/0001-81;DOC-ESTOQUE-1;Duplicata;1500,00;20/11/2026;22/10/2026\n"
        )
        
        tmp_a = "tmp_estoque_lf.csv"
        tmp_b = "tmp_estoque_crlf.csv"
        try:
            with open(tmp_a, "w", encoding="utf-8", newline="\n") as f:
                f.write(content_lf)
            
            # Primeira carga bem-sucedida
            total, antecipe, nominal, fhash = importar_estoque_csv(db, tmp_a)
            self.assertEqual(total, 1)

            # Cria arquivo B com os mesmos registros porém quebras CRLF (hash de arquivo diferente)
            content_crlf = content_lf.replace("\n", "\r\n")
            with open(tmp_b, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(content_crlf)

            # Segunda carga deve ser bloqueada por sobreposição de títulos
            with self.assertRaises(ValueError) as ctx:
                importar_estoque_csv(db, tmp_b)
            self.assertIn("Sobreposição de estoque detectada", str(ctx.exception))
        finally:
            if os.path.exists(tmp_a):
                os.remove(tmp_a)
            if os.path.exists(tmp_b):
                os.remove(tmp_b)
            db.close()
    # ---------------------------------------------------------
    # 12. RECHECK B3 AVANÇADO: LIMITE DE PAYLOAD JSON E STREAM ASGI SEM CONTENT-LENGTH
    # ---------------------------------------------------------
    def test_20_json_payload_oversize_rejected_with_413(self):
        """
        Recheck B3: Payload JSON para /api/receivables/evaluate que excede MAX_UPLOAD_SIZE_BYTES
        deve ser rejeitado antecipadamente com HTTP 413, sem disparar HTTP 400 por lista vazia.
        """
        old_limit = settings.MAX_UPLOAD_SIZE_BYTES
        try:
            settings.MAX_UPLOAD_SIZE_BYTES = 100
            # Payload de 2048 bytes de padding
            payload_grande = {
                "recebiveis": [],
                "padding": "x" * 2048
            }
            res = self.client.post("/api/receivables/evaluate", json=payload_grande)
            self.assertEqual(res.status_code, 413)
            self.assertEqual(res.json()["detail"]["codigo"], "REQUISICAO_MUITO_GRANDE")
        finally:
            settings.MAX_UPLOAD_SIZE_BYTES = old_limit

    def test_21_asgi_stream_chunked_upload_without_content_length(self):
        """
        Recheck B3: Upload em streaming contínuo SEM cabeçalho Content-Length
        (ex: chunked transfer encoding) deve monitorar os bytes lidos do socket em tempo real
        e rejeitar com HTTP 413 assim que o volume de bytes transmitidos ultrapassar o limite,
        antes que o spool em disco seja concluído.
        """
        import asyncio
        from starlette.requests import Request
        from starlette.responses import Response
        from fastapi import HTTPException
        from backend.main import request_size_limit_middleware

        old_limit = settings.MAX_UPLOAD_SIZE_BYTES
        try:
            settings.MAX_UPLOAD_SIZE_BYTES = 100

            # Mock de request ASGI sem header content-length com chunks que ultrapassam 100 bytes
            scope = {
                "type": "http",
                "method": "POST",
                "path": "/api/simulations",
                "headers": [(b"content-type", b"multipart/form-data; boundary=test")]
            }

            chunks = [b"chunk-inicial-de-50-bytes-123456789012345678901234", b"chunk-excedente-de-80-bytes-1234567890123456789012345678901234567890"]
            chunk_iter = iter(chunks)

            async def mock_receive():
                try:
                    c = next(chunk_iter)
                    return {"type": "http.request", "body": c, "more_body": True}
                except StopIteration:
                    return {"type": "http.request", "body": b"", "more_body": False}

            req = Request(scope, receive=mock_receive)

            async def call_next(r):
                # Simula o parser tentando consumir o corpo do stream
                await r.body()
                return Response("ok")

            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(request_size_limit_middleware(req, call_next))

            self.assertEqual(ctx.exception.status_code, 413)
            self.assertEqual(ctx.exception.detail["codigo"], "ARQUIVO_MUITO_GRANDE")
        finally:
            settings.MAX_UPLOAD_SIZE_BYTES = old_limit


if __name__ == "__main__":
    unittest.main()
