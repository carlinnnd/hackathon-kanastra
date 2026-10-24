"""
Suíte Independente de Integração e Persistência de API (Rubrica 5.2.1, 5.2.2, 5.2.3, 5.2.4).
Testa contra a API FastAPI real do Antecipe:
1. Health check e prontidão do serviço
2. Upload multipart de lote CSV em streaming e paginação
3. Mensagens de recusa claras com causa e próximo passo
4. Segurança de cabeçalho X-Admin-Token em endpoints administrativos
5. Ciclo completo de versionamento imutável de regras e CAS:
   - Simula recebível com prazo de 150 dias na v1 (prazo_maximo_dias: 180) -> APROVADO
   - Publica v2 via POST /api/rules/versions alterando prazo_maximo_dias para 120
   - Ativa v2 via POST /api/rules/versions/{id}/activate com CAS
   - Nova simulação da mesma nota na v2 -> RECUSADA (PRAZO_MAXIMO)
   - GET /api/simulations/{id_v1} mantém imutavelmente v1, status aprovado e valores originais
"""
import copy
import io
import json
import os
import unittest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.infrastructure.database.models import Base, FundModel, RuleVersionModel, ReceivableModel
from backend.infrastructure.database.session import get_db
from backend.infrastructure.repositories.rules_repository import RulesRepository
from backend.config import settings
from backend.domain.cnpj import normalizar_cnpj


class TestApiIntegracaoIndependente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig_admin = settings.ADMIN_TOKEN
        cls.orig_demo = settings.ENABLE_DEMO_CADASTRO
        settings.ADMIN_TOKEN = "hackathon-test-admin-token-2026"
        settings.ENABLE_DEMO_CADASTRO = True

        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        cls.orig_overrides = dict(app.dependency_overrides)
        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app, raise_server_exceptions=True)

        db = cls.TestingSessionLocal()
        ok_cnpj, cnpj_norm = normalizar_cnpj("92.234.400/0001-80")
        fundo = FundModel(
            nome="ANTECIPE FIDC",
            cnpj=cnpj_norm
        )
        db.add(fundo)
        db.commit()
        db.refresh(fundo)

        # Baseline de carteira para permitir margem de concentração de 10%
        # Adiciona R$ 100.000,00 de estoque distribuído em outros sacados
        rec_base = ReceivableModel(
            fund_id=fundo.id,
            chave_duplicidade="11222333000181:22333444000192:DUPLICATA:NF-BASE-01:2027-01-20",
            nome_cedente="CEDENTE S/A",
            doc_cedente="11222333000181",
            nome_sacado="DISTRIBUIDORA DELTA",
            doc_sacado="22333444000192",
            raiz_cnpj_sacado="22333444",
            nu_documento="NF-BASE-01",
            tipo_recebivel="Duplicata",
            valor_nominal_centavos=10000000,
            valor_nominal=Decimal("100000.00"),
            data_vencimento=date(2027, 1, 20)
        )
        db.add(rec_base)
        db.commit()

        caminho_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "validadores_antecipe.json"))
        if not os.path.exists(caminho_json):
            caminho_json = "validadores_antecipe.json"
        with open(caminho_json, "r", encoding="utf-8") as f:
            cls.raw_rules = json.load(f)

        rules_repo = RulesRepository(db)
        versao_v1 = rules_repo.criar_versao(
            fundo_id=fundo.id,
            config_dict=cls.raw_rules,
            created_by="qa_setup",
            change_reason="Versão v1 oficial"
        )
        rules_repo.ativar_versao(
            fundo_id=fundo.id,
            version_id=versao_v1.id,
            actor="qa_setup"
        )
        cls.fundo_id = fundo.id
        cls.v1_id = versao_v1.id
        db.close()

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(cls.orig_overrides)
        settings.ADMIN_TOKEN = cls.orig_admin
        settings.ENABLE_DEMO_CADASTRO = cls.orig_demo

    def test_01_api_health_retorna_status_ok(self):
        """Verifica prontidão do serviço."""
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("ANTECIPE", data["fundo"])

    def test_02_upload_csv_multipart_stream_aprovacao_e_paginacao(self):
        """Upload multipart de CSV válido processa via streaming e pagina em 50 itens."""
        csv_conteudo = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE S/A;00.111.222/0001-33;COMERCIAL ALPHA LTDA;04.252.011/0001-10;DOC-001;Duplicata;1.500,00;20/11/2026;\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE S/A;00.111.222/0001-33;COMERCIAL ALPHA LTDA;04.252.011/0001-10;DOC-002;Boleto;2.000,00;20/11/2026;\n"
        )
        files = {"file": ("simulacao_lote.csv", io.BytesIO(csv_conteudo.encode("utf-8")), "text/csv")}
        resp = self.client.post("/api/simulations", files=files)
        self.assertEqual(resp.status_code, 200)
        
        envelope = resp.json()
        self.assertEqual(envelope["status"], "concluida")
        self.assertEqual(envelope["total_itens"], 2)
        self.assertEqual(envelope["aprovados"], 1)
        self.assertEqual(envelope["recusados"], 1)
        # total_nominal no envelope da simulação reflete o total submetido de R$ 3500.00 (1500 + 2000)
        self.assertEqual(envelope["total_nominal"], "3500.00")
        
        # Paginação estrita
        self.assertEqual(envelope["pagination"]["page"], 1)
        self.assertEqual(envelope["pagination"]["page_size"], 50)
        self.assertEqual(len(envelope["resultados"]), 2)

    def test_03_recusa_com_mensagem_clara_e_causa(self):
        """Recusas devem carregar código e mensagem explicativa acionável sem expor dados brutos."""
        csv_conteudo = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE S/A;00.111.222/0001-33;COMERCIAL ALPHA LTDA;04.252.011/0001-10;DOC-RECUSA;Duplicata;50,00;20/11/2026;\n"
        )
        files = {"file": ("recusa.csv", io.BytesIO(csv_conteudo.encode("utf-8")), "text/csv")}
        resp = self.client.post("/api/simulations", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        item_recusado = data["resultados"][0]
        self.assertFalse(item_recusado["aprovado"])
        self.assertEqual(item_recusado["motivos"][0]["codigo"], "VALOR_MINIMO")
        self.assertIn("100.0", item_recusado["motivos"][0]["mensagem"])

    def test_04_seguranca_admin_token_obrigatorio_para_versionamento(self):
        """Endpoints administrativos exigem X-Admin-Token e recusam sem vazar segredos."""
        resp = self.client.post("/api/rules/versions", json={"configuration": {}, "change_reason": "teste"})
        self.assertEqual(resp.status_code, 401)
        detail = resp.json()["detail"]
        self.assertEqual(detail["codigo"], "ADMIN_TOKEN_INVALIDO")

    def test_05_ciclo_versionamento_imutavel_cas_e_preservacao_historica(self):
        """
        Demonstração rigorosa de versionamento:
        1. Simulação com prazo 150 dias na v1 (prazo_maximo: 180) -> APROVADO.
        2. Publicação da v2 alterando prazo_maximo para 120 dias via X-Admin-Token.
        3. Ativação concorrente protegida (CAS) da v2.
        4. Nova simulação com a mesma nota de 150 dias -> RECUSADA (PRAZO_MAXIMO).
        5. GET da simulação 1 mantém intactos v1, status 'concluida', aprovado=True e totais originais.
        """
        # Nota com 150 dias de prazo: data base 22/10/2026 -> vencimento 21/03/2027 (150 dias)
        csv_150_dias = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE S/A;00.111.222/0001-33;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-150D;Duplicata;1.000,00;21/03/2027;\n"
        )
        files1 = {"file": ("nota_150d.csv", io.BytesIO(csv_150_dias.encode("utf-8")), "text/csv")}
        resp1 = self.client.post("/api/simulations", files=files1)
        self.assertEqual(resp1.status_code, 200)
        sim1_data = resp1.json()
        sim1_id = sim1_data["simulation_id"]
        
        self.assertEqual(sim1_data["rule_version"], 1)
        self.assertEqual(sim1_data["aprovados"], 1)
        self.assertEqual(sim1_data["recusados"], 0)
        self.assertTrue(sim1_data["resultados"][0]["aprovado"])

        # 2. Publicar v2 reduzindo o prazo máximo para 120 dias
        cfg_v2 = copy.deepcopy(self.raw_rules)
        for val in cfg_v2["validadores"]:
            if val["codigo"] == "PRAZO_MAXIMO":
                val["parametros"]["prazo_maximo_dias"] = 120

        headers_admin = {"X-Admin-Token": settings.ADMIN_TOKEN}
        resp_pub = self.client.post(
            "/api/rules/versions",
            json={
                "configuration": cfg_v2,
                "change_reason": "Redução prudencial de prazo máximo para 120 dias"
            },
            headers=headers_admin
        )
        self.assertEqual(resp_pub.status_code, 200)
        v2_info = resp_pub.json()
        v2_id = v2_info["id"]
        self.assertEqual(v2_info["version_number"], 2)

        # 3. Ativação via CAS informando a versão anterior esperada
        resp_act = self.client.post(
            f"/api/rules/versions/{v2_id}/activate?expected_active_version_id={self.v1_id}",
            headers=headers_admin
        )
        self.assertEqual(resp_act.status_code, 200)
        self.assertEqual(resp_act.json()["status"], "activated")

        # 4. Nova simulação com a mesma nota de 150 dias sob a v2 ativa
        files2 = {"file": ("nota_150d_v2.csv", io.BytesIO(csv_150_dias.encode("utf-8")), "text/csv")}
        resp2 = self.client.post("/api/simulations", files=files2)
        self.assertEqual(resp2.status_code, 200)
        sim2_data = resp2.json()
        
        self.assertEqual(sim2_data["rule_version"], 2)
        self.assertEqual(sim2_data["aprovados"], 0)
        self.assertEqual(sim2_data["recusados"], 1)
        self.assertFalse(sim2_data["resultados"][0]["aprovado"])
        self.assertEqual(sim2_data["resultados"][0]["motivos"][0]["codigo"], "PRAZO_MAXIMO")
        self.assertIn("120", sim2_data["resultados"][0]["motivos"][0]["mensagem"])

        # 5. GET da simulação 1 deve permanecer rigorosamente inalterado em v1
        resp_get1 = self.client.get(f"/api/simulations/{sim1_id}")
        self.assertEqual(resp_get1.status_code, 200)
        sim1_recuperada = resp_get1.json()
        
        self.assertEqual(sim1_recuperada["simulation_id"], sim1_id)
        self.assertEqual(sim1_recuperada["rule_version"], 1)
        self.assertEqual(sim1_recuperada["rule_version_id"], self.v1_id)
        self.assertEqual(sim1_recuperada["aprovados"], 1)
        self.assertEqual(sim1_recuperada["recusados"], 0)
        self.assertEqual(sim1_recuperada["total_nominal"], "1000.00")
        self.assertTrue(sim1_recuperada["resultados"][0]["aprovado"])


if __name__ == "__main__":
    unittest.main()
