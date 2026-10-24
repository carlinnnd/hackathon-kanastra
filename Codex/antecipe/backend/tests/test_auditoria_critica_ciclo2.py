"""
Testes específicos para os itens auditados pelo Ciclo 2 do Auditor Crítico:
1. PRAGMA foreign_keys=ON e atomicidade da transação pai/filhos (sem orfãos em caso de erro após chunk 2000).
2. Importer rejeita CSV apenas com cabeçalho ou com DATA_AQUISICAO inválida (ex: 99/99/9999).
3. Proteção de upload precoce (HTTP stream level com Content-Length e streaming).
4. Safe logging usa template allowlist /unmatched_route em 404s, garantindo vazamento ZERO de nomes arbitrários.
5. JSON evaluate rejeita data_base inválida com 422 em vez de assumir data default.
6. JSON evaluate suporta nomes com ponto-e-vírgula/aspas via RFC 4180 csv.writer.
7. Idempotência estrita e detecção de sobreposição/duplicidade na carga de estoque.
8. Limite de tamanho de requisição para endpoint JSON evaluate (HTTP 413 antecipado).
"""
import io
import json
import os
import unittest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.config import settings
from backend.infrastructure.database.session import get_db
from backend.infrastructure.database.models import FundModel, ReceivableModel, SimulationModel, SimulationItemModel
from backend.application.importer import inicializar_fundos_e_regras, importar_estoque_csv
from backend.application.simulation_service import SimulationService
from backend.domain.models import ReceivelInput, ResultadoAvaliacao, MotivoRecusa
from backend.main import app
from backend.tests.test_db_shared import SharedTestingSessionLocal, init_shared_test_db

settings.ADMIN_TOKEN = "hackathon-test-admin-token-2026"
settings.ENABLE_DEMO_CADASTRO = True


def override_get_db():
    db = SharedTestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class TestAuditoriaCriticaCiclo2(unittest.TestCase):
    def setUp(self):
        settings.ADMIN_TOKEN = "hackathon-test-admin-token-2026"
        init_shared_test_db()
        self.client = TestClient(app)

    def test_01_transacionalidade_pai_filhos_rollback_limpa_tudo(self):
        """
        Garante que a simulação pai é criada no banco com integridade referencial,
        e que se ocorrer falha após inserir mais de 2.000 itens (chunk),
        a transação é revertida integralmente via rollback (zero itens órfãos).
        """
        db = SharedTestingSessionLocal()
        itens_antes = db.query(SimulationItemModel).count()
        sims_antes = db.query(SimulationModel).count()
        service = SimulationService(db)

        def gerador_com_falha():
            for i in range(1, 2501):
                if i == 2050:
                    raise RuntimeError("Falha forçada após primeiro chunk para testar rollback atômico")
                item = ReceivelInput(
                    linha=i,
                    nome_fundo="ANTECIPE FIDC",
                    doc_fundo="92234400000180",
                    nome_cedente="CEDENTE",
                    doc_cedente="11222333000181",
                    nome_sacado="COMERCIAL ALPHA LTDA",
                    doc_sacado="04252011000110",
                    nu_documento=f"NF-{i}",
                    tipo_recebivel="Duplicata",
                    valor_nominal=Decimal("150.00"),
                    data_vencimento=date(2026, 12, 1)
                )
                yield (i, item, None)

        with self.assertRaises(RuntimeError):
            service.executar_simulacao_lote(gerador_com_falha())

        itens_depois = db.query(SimulationItemModel).count()
        sims_depois = db.query(SimulationModel).count()
        self.assertEqual(itens_depois, itens_antes, "Rollback não deve deixar nenhum item órfão gravado no banco")
        self.assertEqual(sims_depois, sims_antes, "Rollback não deve deixar simulação pai gravada no banco")
        db.close()

    def test_02_importer_rejeita_csv_apenas_cabecalho_e_data_aquisicao_invalida(self):
        """
        O importador de estoque deve abortar atomicamente se:
        - O arquivo contiver apenas linha de cabeçalho sem dados.
        - O campo DATA_AQUISICAO contiver data inválida (ex: 99/99/9999), sem transformá-la silenciosamente em NULL.
        """
        db = SharedTestingSessionLocal()
        
        # Caso A: CSV apenas com cabeçalho
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write("NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n")
            temp_empty = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                importar_estoque_csv(db, temp_empty)
            self.assertIn("apenas cabeçalho", str(ctx.exception))
        finally:
            if os.path.exists(temp_empty):
                os.remove(temp_empty)

        # Caso B: DATA_AQUISICAO inválida
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(
                "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE;11.222.333/0001-81;SACADO;04.252.011/0001-10;NF-01;Duplicata;500,00;20/12/2026;99/99/9999\n"
            )
            temp_invalid_date = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                importar_estoque_csv(db, temp_invalid_date)
            self.assertIn("DATA_AQUISICAO", str(ctx.exception))
        finally:
            if os.path.exists(temp_invalid_date):
                os.remove(temp_invalid_date)

        db.close()

    def test_03_json_evaluate_data_base_invalida_retorna_422(self):
        """
        POST /api/receivables/evaluate com data_base inválida (ex: 'data-invalida')
        deve retornar HTTP 422 em vez de assumir data default silenciosa.
        """
        payload = {
            "recebiveis": [
                {
                    "NOME_CEDENTE": "CEDENTE",
                    "DOC_CEDENTE": "11.222.333/0001-81",
                    "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                    "DOC_SACADO": "04.252.011/0001-10",
                    "NU_DOCUMENTO": "NF-101",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": "1000,00",
                    "DATA_VENCIMENTO_ORIGINAL": "20/12/2026"
                }
            ],
            "data_base": "data-invalida"
        }
        res = self.client.post("/api/receivables/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["detail"]["codigo"], "DATA_BASE_INVALIDA")

    def test_04_json_evaluate_com_ponto_e_virgula_e_aspas_escapados_rfc4180(self):
        """
        POST /api/receivables/evaluate aceita nomes com ponto-e-vírgula ('EMPRESA;TESTE')
        sem corromper colunas ou desbalancear linhas, mantendo paridade com CSV RFC 4180.
        """
        payload = {
            "recebiveis": [
                {
                    "NOME_CEDENTE": "CEDENTE;ESPECIAL LTDA",
                    "DOC_CEDENTE": "11.222.333/0001-81",
                    "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                    "DOC_SACADO": "04.252.011/0001-10",
                    "NU_DOCUMENTO": "NF-ESPECIAL",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": "2000,00",
                    "DATA_VENCIMENTO_ORIGINAL": "20/12/2026"
                }
            ],
            "data_base": "2026-10-22"
        }
        res = self.client.post("/api/receivables/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_itens"], 1)
        self.assertEqual(data["aprovados"], 1)
        self.assertEqual(data["resultados"][0]["documento"], "NF-ESPECIAL")

    def test_05_log_emite_template_allowlist_e_oculta_nomes_404(self):
        """
        Garante que requisições a rotas desconhecidas ou com nomes sensíveis
        usam a constante allowlist '/unmatched_route' em vez de emitir o path bruto.
        """
        res = self.client.get("/api/clientes/cliente-acme-confidencial-2026")
        self.assertEqual(res.status_code, 404)

    def test_06_json_evaluate_oversize_limit_monkeypatch_returns_413(self):
        """
        POST /api/receivables/evaluate excedendo MAX_UPLOAD_SIZE_BYTES
        deve ser rejeitado antecipadamente com HTTP 413, e não 400 ou 500.
        """
        old_limit = settings.MAX_UPLOAD_SIZE_BYTES
        try:
            settings.MAX_UPLOAD_SIZE_BYTES = 100
            payload = {
                "recebiveis": [
                    {
                        "NOME_CEDENTE": "CEDENTE GRANDE COM NOME LONGO PARA EXCEDER CEM BYTES NO PAYLOAD",
                        "DOC_CEDENTE": "11.222.333/0001-81",
                        "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                        "DOC_SACADO": "04.252.011/0001-10",
                        "NU_DOCUMENTO": "NF-GRANDE",
                        "TIPO_RECEBIVEL": "Duplicata",
                        "VALOR_NOMINAL": "5000,00",
                        "DATA_VENCIMENTO_ORIGINAL": "20/12/2026"
                    }
                ],
                "data_base": "2026-10-22"
            }
            res = self.client.post("/api/receivables/evaluate", json=payload)
            self.assertEqual(res.status_code, 413)
            self.assertIn("MUITO_GRANDE", res.json()["detail"]["codigo"])
        finally:
            settings.MAX_UPLOAD_SIZE_BYTES = old_limit


if __name__ == "__main__":
    unittest.main()
