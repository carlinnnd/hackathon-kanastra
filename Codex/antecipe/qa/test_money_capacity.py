"""
Suíte Exclusiva e Independente de Capacidade Monetária, Boundaries e Robustez Financeira.
Auditoria de Conformidade e Resiliência (Numeric 15,2 e limites de totais):
1. Teto técnico exato individual (R$ 9.999.999.999.999,99) via POST CSV/JSON -> GET: preservação exata em centavos (sem float, sem truncamento).
2. Teto - 0.01: roundtrip preservado com precisão Decimal exata.
3. Teto + 0.01: recusa com código 'VALOR_EXCEDE_CAPACIDADE' e 'nominal=None' (nunca persiste corrompido, nunca dispara 500).
4. Lote cumulativo que ultrapassa o teto total: aborto com HTTP 422 'TOTAL_EXCEDE_CAPACIDADE' e rollback integral (zero itens órfãos).
5. Rollback atômico em lote grande após o chunk 2000 em caso de estouro cumulativo tardio.
6. Importer: rejeição de título individual acima do teto e de estouro cumulativo do saldo da carteira por fundo.
7. Importer: preservação transacional do estado existente em caso de falha de carga (sem poluição de banco).
8. Logs estritamente sanitizados: nenhuma menção a valores nominais brutos, sentinelas ou dados pessoais nos logs de erro.
"""
import csv
import io
import json
import logging
import os
import unittest
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings
from backend.infrastructure.database.session import Base, get_db
from backend.infrastructure.database.models import FundModel, ReceivableModel, SimulationModel, SimulationItemModel
from backend.application.importer import inicializar_fundos_e_regras, importar_estoque_csv
from backend.domain.limits import VALOR_MAXIMO_PERMITIDO, TOTAL_MAXIMO_PERMITIDO
from backend.logger import logger, SafeJsonFormatter, ALLOWED_LOG_FIELDS
from backend.main import app


class TestMoneyCapacity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings.ADMIN_TOKEN = "hackathon-test-admin-token-2026"
        settings.ENABLE_DEMO_CADASTRO = True

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

        # Inicializa fundo ANTECIPE FIDC e regras V1
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

    # -------------------------------------------------------------------------
    # 1. TETO INDIVIDUAL EXATO (POST CSV/JSON -> GET ROUNDTRIP COM CENTAVOS EXATOS)
    # -------------------------------------------------------------------------
    def test_01_teto_exato_roundtrip_csv_e_json(self):
        """
        R$ 9.999.999.999.999,99 é o limite representável em Numeric(15,2).
        Submissão via CSV e JSON deve ser aceita sintaticamente, calculada e
        persistida preservando exatamente os centavos tanto no POST quanto no GET /api/simulations/{id}.
        """
        teto_str = "9999999999999.99"
        teto_br = "9.999.999.999.999,99"

        # Canal A: CSV
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            f"ANTECIPE FIDC;92.234.400/0001-80;COMERCIAL ALPHA LTDA;04.252.011/0001-10;SERVICOS BETA LTDA;73.410.326/0001-22;NF-TETO-CSV;Duplicata;{teto_br};20/11/2026;\n"
        )
        files = {"file": ("teto.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res_post = self.client.post("/api/simulations", files=files)
        self.assertEqual(res_post.status_code, 200)
        sim_id = res_post.json()["simulation_id"]
        item_post = res_post.json()["resultados"][0]
        self.assertEqual(item_post["valor_nominal"], teto_str)

        # GET da simulação deve manter exatamente o mesmo valor string em centavos
        res_get = self.client.get(f"/api/simulations/{sim_id}")
        self.assertEqual(res_get.status_code, 200)
        item_get = res_get.json()["resultados"][0]
        self.assertEqual(item_get["valor_nominal"], teto_str)

        # Canal B: JSON (/api/receivables/evaluate)
        payload_json = {
            "recebiveis": [
                {
                    "NOME_FUNDO": "ANTECIPE FIDC",
                    "DOC_FUNDO": "92.234.400/0001-80",
                    "NOME_CEDENTE": "COMERCIAL ALPHA LTDA",
                    "DOC_CEDENTE": "04.252.011/0001-10",
                    "NOME_SACADO": "SERVICOS BETA LTDA",
                    "DOC_SACADO": "73.410.326/0001-22",
                    "NU_DOCUMENTO": "NF-TETO-JSON",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": teto_br,
                    "DATA_VENCIMENTO_ORIGINAL": "20/11/2026"
                }
            ],
            "data_base": "2026-10-22"
        }
        res_json = self.client.post("/api/receivables/evaluate", json=payload_json)
        self.assertEqual(res_json.status_code, 200)
        sim_id_json = res_json.json()["simulation_id"]
        item_json = res_json.json()["resultados"][0]
        self.assertEqual(item_json["valor_nominal"], teto_str)

        res_get_json = self.client.get(f"/api/simulations/{sim_id_json}")
        self.assertEqual(res_get_json.status_code, 200)
        self.assertEqual(res_get_json.json()["resultados"][0]["valor_nominal"], teto_str)

    # -------------------------------------------------------------------------
    # 2. TETO - 0.01 (VALOR ADJACENTE VÁLIDO)
    # -------------------------------------------------------------------------
    def test_02_teto_menos_um_centavo_roundtrip(self):
        """
        R$ 9.999.999.999.999,98: preservação fiel no banco e envelope.
        """
        val_str = "9999999999999.98"
        val_br = "9.999.999.999.999,98"
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            f"ANTECIPE FIDC;92.234.400/0001-80;COMERCIAL ALPHA LTDA;04.252.011/0001-10;SERVICOS BETA LTDA;73.410.326/0001-22;NF-TETO-MINUS;Duplicata;{val_br};20/11/2026;\n"
        )
        files = {"file": ("teto_minus.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res = self.client.post("/api/simulations", files=files)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["resultados"][0]["valor_nominal"], val_str)

    # -------------------------------------------------------------------------
    # 3. TETO + 0.01 (RECUSA COM 'VALOR_EXCEDE_CAPACIDADE' E NOMINAL=NONE)
    # -------------------------------------------------------------------------
    def test_03_teto_mais_um_centavo_recusa_com_nominal_none(self):
        """
        R$ 10.000.000.000.000,00 (teto + 0.01):
        - NÃO dispara HTTP 500.
        - Recusa o item com motivo 'VALOR_EXCEDE_CAPACIDADE'.
        - 'valor_nominal' do resultado é estritamente None (nunca truncado para float ou bigint quebrado).
        - Consulta subsequente via GET preserva valor_nominal nulo.
        """
        overflow_br = "10.000.000.000.000,00"
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            f"ANTECIPE FIDC;92.234.400/0001-80;COMERCIAL ALPHA LTDA;04.252.011/0001-10;SERVICOS BETA LTDA;73.410.326/0001-22;NF-OVERFLOW;Duplicata;{overflow_br};20/11/2026;\n"
        )
        files = {"file": ("overflow.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res = self.client.post("/api/simulations", files=files)
        self.assertEqual(res.status_code, 200)
        envelope = res.json()
        item = envelope["resultados"][0]
        self.assertFalse(item["aprovado"])
        self.assertIsNone(item["valor_nominal"])
        self.assertIsNone(item["valor_liquido"])

        codigos_motivo = [m["codigo"] for m in item["motivos"]]
        self.assertIn("VALOR_EXCEDE_CAPACIDADE", codigos_motivo)

        # GET subsequente deve refletir valor_nominal None
        sim_id = envelope["simulation_id"]
        res_get = self.client.get(f"/api/simulations/{sim_id}")
        self.assertEqual(res_get.status_code, 200)
        item_get = res_get.json()["resultados"][0]
        self.assertIsNone(item_get["valor_nominal"])

    # -------------------------------------------------------------------------
    # 4. SOMA CUMULATIVA DO LOTE ACIMA DO TETO: ABORTO ATÔMICO COM HTTP 422
    # -------------------------------------------------------------------------
    def test_04_lote_com_soma_cumulativa_acima_do_teto_aborta_com_422_e_rollback(self):
        """
        Duas notas fiscais cada uma com R$ 5.000.000.000.000,00 (soma = R$ 10.000.000.000.000,00 > teto):
        - Endpoint aborta atomicamente com HTTP 422 e código 'TOTAL_EXCEDE_CAPACIDADE'.
        - Nenhuma linha ou simulação é persistida no banco (rollback integral).
        """
        db = self.TestingSessionLocal()
        sims_antes = db.query(SimulationModel).count()
        itens_antes = db.query(SimulationItemModel).count()

        val_grande_br = "5.000.000.000.000,00"
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            f"ANTECIPE FIDC;92.234.400/0001-80;COMERCIAL ALPHA LTDA;04.252.011/0001-10;SERVICOS BETA LTDA;73.410.326/0001-22;NF-SOMA-1;Duplicata;{val_grande_br};20/11/2026;\n"
            f"ANTECIPE FIDC;92.234.400/0001-80;COMERCIAL ALPHA LTDA;04.252.011/0001-10;SERVICOS BETA LTDA;73.410.326/0001-22;NF-SOMA-2;Duplicata;{val_grande_br};20/11/2026;\n"
        )
        files = {"file": ("soma_overflow.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res = self.client.post("/api/simulations", files=files)
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["detail"]["codigo"], "TOTAL_EXCEDE_CAPACIDADE")

        # Rollback verificado diretamente no banco
        sims_depois = db.query(SimulationModel).count()
        itens_depois = db.query(SimulationItemModel).count()
        self.assertEqual(sims_depois, sims_antes, "Simulação pai confirmada indevidamente após aborto!")
        self.assertEqual(itens_depois, itens_antes, "Itens confirmados indevidamente após aborto!")
        db.close()

    # -------------------------------------------------------------------------
    # 5. ROLLBACK ATÔMICO APÓS O CHUNK 2000 EM ESTOURO TARDIO
    # -------------------------------------------------------------------------
    def test_05_rollback_atomico_em_lote_grande_apos_chunk_2000(self):
        """
        Lote com mais de 2.000 itens (ex: 2.050 itens).
        Os primeiros 2.000 itens acumulam valores normais. No item 2.005, um valor faz
        a soma cumulativa ultrapassar o teto técnico:
        - Deve abortar com HTTP 422 TOTAL_EXCEDE_CAPACIDADE.
        - Os 2.000 itens já enviados em batch_size para o banco devem ser 100% desfeitos pelo rollback.
        """
        db = self.TestingSessionLocal()
        sims_antes = db.query(SimulationModel).count()
        itens_antes = db.query(SimulationItemModel).count()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow([
            "NOME_FUNDO", "DOC_FUNDO", "NOME_CEDENTE", "DOC_CEDENTE", "NOME_SACADO", "DOC_SACADO",
            "NU_DOCUMENTO", "TIPO_RECEBIVEL", "VALOR_NOMINAL", "DATA_VENCIMENTO_ORIGINAL", "DATA_AQUISICAO"
        ])

        # 2.000 itens normais de R$ 100,00
        for i in range(1, 2001):
            writer.writerow([
                "ANTECIPE FIDC", "92.234.400/0001-80", "COMERCIAL ALPHA LTDA", "04.252.011/0001-10",
                "SERVICOS BETA LTDA", "73.410.326/0001-22", f"NF-CHUNK-{i}", "Duplicata",
                "100,00", "20/11/2026", ""
            ])

        # Itens pós-chunk 2000 que estouram a capacidade
        writer.writerow([
            "ANTECIPE FIDC", "92.234.400/0001-80", "COMERCIAL ALPHA LTDA", "04.252.011/0001-10",
            "SERVICOS BETA LTDA", "73.410.326/0001-22", "NF-CHUNK-BOOM", "Duplicata",
            "9.999.999.999.900,00", "20/11/2026", ""
        ])

        files = {"file": ("chunk_overflow.csv", io.BytesIO(output.getvalue().encode("utf-8")), "text/csv")}
        res = self.client.post("/api/simulations", files=files)
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["detail"]["codigo"], "TOTAL_EXCEDE_CAPACIDADE")

        sims_depois = db.query(SimulationModel).count()
        itens_depois = db.query(SimulationItemModel).count()
        self.assertEqual(sims_depois, sims_antes, "Chunk 1 da simulação vazou após falha tardia!")
        self.assertEqual(itens_depois, itens_antes, "Itens do chunk 1 permaneceram no banco!")
        db.close()

    # -------------------------------------------------------------------------
    # 6. IMPORTER: REJEIÇÃO DE TÍTULO INDIVIDUAL FORA DO TETO
    # -------------------------------------------------------------------------
    def test_06_importer_rejeita_nominal_fora_do_teto(self):
        """
        O importador de estoque rejeita qualquer arquivo contendo títulos acima de R$ 9.999.999.999.999,99.
        """
        db = self.TestingSessionLocal()
        tmp_csv = "tmp_overflow_importer.csv"
        try:
            with open(tmp_csv, "w", encoding="utf-8", newline="\n") as f:
                f.write(
                    "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                    "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE A;00.111.222/0001-33;SACADO B;11.222.333/0001-81;DOC1;Duplicata;10.000.000.000.000,00;20/11/2026;\n"
                )
            with self.assertRaises(ValueError) as ctx:
                importar_estoque_csv(db, tmp_csv)
            self.assertIn("excede a capacidade técnica", str(ctx.exception))
        finally:
            if os.path.exists(tmp_csv):
                os.remove(tmp_csv)
            db.close()

    # -------------------------------------------------------------------------
    # 7. IMPORTER: CHECAGEM DE CAPACIDADE CUMULATIVA POR FUNDO E ESTADO EXISTENTE
    # -------------------------------------------------------------------------
    def test_07_importer_capacidade_cumulativa_por_fundo_e_preservacao_de_estado(self):
        """
        Verificação do importador sob cargas consecutivas:
        - Fundos distintos (Fundo A e Fundo B) somam capacidades independentes por fund_id.
        - Tentativa de carga de um segundo arquivo que faz o saldo do mesmo fundo estourar o teto
          cumulativo total aborta a carga e preserva integralmente os títulos da primeira carga válida.
        """
        db = self.TestingSessionLocal()
        tmp_carga_1 = "tmp_carga_valida.csv"
        tmp_carga_2 = "tmp_carga_estouro.csv"

        try:
            # Carga 1: Fundo A com R$ 6.000.000.000.000,00 (dentro do teto)
            val_6_tri = "6.000.000.000.000,00"
            with open(tmp_carga_1, "w", encoding="utf-8", newline="\n") as f:
                f.write(
                    "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                    f"FUNDO ALPHA;11.111.111/0001-11;CEDENTE A;00.111.222/0001-33;SACADO B;11.222.333/0001-81;DOC-A1;Duplicata;{val_6_tri};20/11/2026;\n"
                )

            total_1, _, _, _ = importar_estoque_csv(db, tmp_carga_1)
            self.assertEqual(total_1, 1)

            # Carga 2: Fundo ALPHA tenta adicionar mais R$ 5.000.000.000.000,00 (soma = 11 trilhões > teto)
            val_5_tri = "5.000.000.000.000,00"
            with open(tmp_carga_2, "w", encoding="utf-8", newline="\n") as f:
                f.write(
                    "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                    f"FUNDO ALPHA;11.111.111/0001-11;CEDENTE A;00.111.222/0001-33;SACADO B;11.222.333/0001-81;DOC-A2;Duplicata;{val_5_tri};21/11/2026;\n"
                )

            with self.assertRaises(ValueError) as ctx:
                importar_estoque_csv(db, tmp_carga_2)
            self.assertIn("acumulado da carteira do fundo excede a capacidade técnica", str(ctx.exception))
            # Verifica se os títulos da Carga 1 permanecem íntegros e a Carga 2 não deixou órfãos
            titulos_alpha = db.query(ReceivableModel).filter(ReceivableModel.nu_documento == "DOC-A1").count()
            self.assertEqual(titulos_alpha, 1, "Título da Carga 1 foi perdido indevidamente!")
            titulos_estouro = db.query(ReceivableModel).filter(ReceivableModel.nu_documento == "DOC-A2").count()
            self.assertEqual(titulos_estouro, 0, "Título da Carga 2 estourada vazou para o banco!")
        finally:
            if os.path.exists(tmp_carga_1):
                os.remove(tmp_carga_1)
            if os.path.exists(tmp_carga_2):
                os.remove(tmp_carga_2)
            db.close()

    # -------------------------------------------------------------------------
    # 8. LOGS SEGUROS: NENHUM VALOR NOMINAL OU DADO PESSOAL EM CASOS DE ESTOURO
    # -------------------------------------------------------------------------
    def test_08_safe_logs_nao_registram_valores_monetarios_brutos_em_erros(self):
        """
        Em qualquer situação de erro (recusa por capacidade ou estouro de total),
        o logger estruturado NUNCA deve emitir o valor nominal bruto ou dados de cliente no log.
        """
        sentinela_valor = "9999999999999.99"
        sentinela_doc = "NF-SENTINELA-VALOR-12345"

        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            f"ANTECIPE FIDC;92.234.400/0001-80;COMERCIAL ALPHA LTDA;04.252.011/0001-10;SERVICOS BETA LTDA;73.410.326/0001-22;{sentinela_doc};Duplicata;{sentinela_valor};20/11/2026;\n"
        )
        files = {"file": ("log_test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res = self.client.post("/api/simulations", files=files)
        self.assertEqual(res.status_code, 200)

        log_raw = self.log_stream.getvalue()
        # Garante ausência total do documento e do valor bruto nos logs gerados
        self.assertNotIn(sentinela_doc, log_raw)
        self.assertNotIn(sentinela_valor, log_raw)


if __name__ == "__main__":
    unittest.main()
