"""
Testes dedicados de capacidade monetária e roundtrip boundaries (Numeric 15,2 e limites de totais):
- Teto exato (R$ 9.999.999.999.999,99) e teto - 0.01: POST CSV/JSON -> GET nominal exato roundtrip.
- Teto + 0.01: recusa com VALOR_EXCEDE_CAPACIDADE e nominal=None (nunca 500, nunca persistido alterado/float).
- Lote com soma dentro do teto passa; soma cumulativa excedendo teto aborta com TOTAL_EXCEDE_CAPACIDADE e rollback integral.
- Importador rejeita títulos acima do teto técnico individual.
- Importador: 2 importações distintas sem colisão de chave; e rejeição atômica de carga que excede teto cumulativo da carteira.
"""
import io
import json
import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.config import settings
from backend.infrastructure.database.session import get_db
from backend.infrastructure.database.models import FundModel, ReceivableModel, SimulationModel, SimulationItemModel
from backend.application.importer import importar_estoque_csv
from backend.domain.limits import VALOR_MAXIMO_PERMITIDO, TOTAL_MAXIMO_PERMITIDO
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


class TestCapacidadeMonetariaBoundaries(unittest.TestCase):
    def setUp(self):
        settings.ADMIN_TOKEN = "hackathon-test-admin-token-2026"
        init_shared_test_db()
        self.client = TestClient(app)

    def test_01_teto_exato_roundtrip_preservado(self):
        """
        Título com valor exatamente igual ao teto técnico (R$ 9.999.999.999.999,99)
        é aceito para avaliação e preserva a string nominal exata sem distorção float.
        """
        teto_str = str(VALOR_MAXIMO_PERMITIDO)  # "9999999999999.99"
        payload = {
            "recebiveis": [
                {
                    "NOME_CEDENTE": "CEDENTE TETO",
                    "DOC_CEDENTE": "11.222.333/0001-81",
                    "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                    "DOC_SACADO": "04.252.011/0001-10",
                    "NU_DOCUMENTO": "NF-TETO-EXATO",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": teto_str.replace(".", ","),
                    "DATA_VENCIMENTO_ORIGINAL": "20/12/2026"
                }
            ],
            "data_base": "2026-10-22"
        }
        res = self.client.post("/api/receivables/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        sim_id = res.json()["simulation_id"]

        res_get = self.client.get(f"/api/simulations/{sim_id}")
        self.assertEqual(res_get.status_code, 200)
        item = res_get.json()["resultados"][0]
        self.assertEqual(item["valor_nominal"], teto_str)

    def test_02_teto_menos_um_centavo_roundtrip_preservado(self):
        """
        Título com valor teto - 0.01 (R$ 9.999.999.999.999,98) preserva nominal exato no GET.
        """
        valor = VALOR_MAXIMO_PERMITIDO - Decimal("0.01")
        val_str = f"{valor:.2f}"
        payload = {
            "recebiveis": [
                {
                    "NOME_CEDENTE": "CEDENTE TETO MENOS 1",
                    "DOC_CEDENTE": "11.222.333/0001-81",
                    "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                    "DOC_SACADO": "04.252.011/0001-10",
                    "NU_DOCUMENTO": "NF-TETO-MENOS-1",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": val_str.replace(".", ","),
                    "DATA_VENCIMENTO_ORIGINAL": "20/12/2026"
                }
            ],
            "data_base": "2026-10-22"
        }
        res = self.client.post("/api/receivables/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        sim_id = res.json()["simulation_id"]

        res_get = self.client.get(f"/api/simulations/{sim_id}")
        self.assertEqual(res_get.status_code, 200)
        item = res_get.json()["resultados"][0]
        self.assertEqual(item["valor_nominal"], val_str)

    def test_03_teto_mais_um_centavo_recusa_com_nominal_none_sem_500(self):
        """
        Título com teto + 0.01 (R$ 10.000.000.000.000,00 - 14 dígitos inteiros):
        Deve ser recusado estruturadamente com VALOR_EXCEDE_CAPACIDADE e nominal=None
        (NUNCA retornar 500, NUNCA persistir truncado ou alterado por float).
        """
        val_acima = "10000000000000.00"
        payload = {
            "recebiveis": [
                {
                    "NOME_CEDENTE": "CEDENTE OVERFLOW",
                    "DOC_CEDENTE": "11.222.333/0001-81",
                    "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                    "DOC_SACADO": "04.252.011/0001-10",
                    "NU_DOCUMENTO": "NF-OVERFLOW",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": val_acima.replace(".", ","),
                    "DATA_VENCIMENTO_ORIGINAL": "20/12/2026"
                }
            ],
            "data_base": "2026-10-22"
        }
        res = self.client.post("/api/receivables/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        item = data["resultados"][0]
        self.assertFalse(item["aprovado"])
        self.assertIsNone(item["valor_nominal"], "Valor nominal acima do teto técnico deve ser explicitamente None")
        codigos = [m["codigo"] for m in item["motivos"]]
        self.assertIn("VALOR_EXCEDE_CAPACIDADE", codigos)

    def test_04_lote_com_soma_cumulativa_acima_do_teto_aborta_com_422_e_rollback(self):
        """
        Lote onde cada linha individual é < teto, mas a soma de duas linhas excede o teto técnico:
        O lote inteiro deve ser abortado com HTTP 422 e TOTAL_EXCEDE_CAPACIDADE,
        com rollback completo e sem persistir registros.
        """
        db = SharedTestingSessionLocal()
        sims_antes = db.query(SimulationModel).count()
        db.close()

        val_seis_tri = "6000000000000,00"
        payload = {
            "recebiveis": [
                {
                    "NOME_CEDENTE": "CEDENTE A",
                    "DOC_CEDENTE": "11.222.333/0001-81",
                    "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                    "DOC_SACADO": "04.252.011/0001-10",
                    "NU_DOCUMENTO": "NF-CUMUL-01",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": val_seis_tri,
                    "DATA_VENCIMENTO_ORIGINAL": "20/12/2026"
                },
                {
                    "NOME_CEDENTE": "CEDENTE B",
                    "DOC_CEDENTE": "11.222.333/0001-81",
                    "NOME_SACADO": "SERVICOS BETA LTDA",
                    "DOC_SACADO": "73.410.326/0001-22",
                    "NU_DOCUMENTO": "NF-CUMUL-02",
                    "TIPO_RECEBIVEL": "Duplicata",
                    "VALOR_NOMINAL": val_seis_tri,
                    "DATA_VENCIMENTO_ORIGINAL": "20/12/2026"
                }
            ],
            "data_base": "2026-10-22"
        }
        res = self.client.post("/api/receivables/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["detail"]["codigo"], "TOTAL_EXCEDE_CAPACIDADE")

        db = SharedTestingSessionLocal()
        sims_depois = db.query(SimulationModel).count()
        self.assertEqual(sims_depois, sims_antes, "Rollback deve descartar a simulação inteira em caso de estouro cumulativo")
        db.close()

    def test_05_importer_rejeita_nominal_fora_do_teto(self):
        """
        O importador de estoque deve abortar atomicamente se encontrar título com valor acima do teto.
        """
        db = SharedTestingSessionLocal()
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(
                "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE;11.222.333/0001-81;SACADO;04.252.011/0001-10;NF-TETO-IMP;Duplicata;10000000000000,00;20/12/2026;\n"
            )
            temp_path = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                importar_estoque_csv(db, temp_path)
            self.assertIn("capacidade técnica", str(ctx.exception))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        db.close()

    def test_06_importer_duas_cargas_distintas_sucesso_e_rejeicao_overflow_cumulativo(self):
        """
        Testa duas importações distintas para fundos diferentes com chunks e validação cumulativa de saldo:
        1. Carga A (Fundo Boreal): importa com sucesso novo lote.
        2. Carga B: tenta importar títulos para o Fundo Boreal que, somados ao saldo existente,
           excedem o TOTAL_MAXIMO_PERMITIDO -> aborta atomicamente via rollback.
        """
        db = SharedTestingSessionLocal()
        
        # 1. Carga A válida
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(
                "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                "FUNDO TESTE NOVO;11.111.111/0001-11;CEDENTE NOVO;22.222.222/0001-22;SACADO NOVO;33.333.333/0001-33;NF-NOVOFUNDO-01;Duplicata;500000,00;20/12/2026;01/05/2026\n"
            )
            carga_a_path = f.name

        try:
            total_a, _, _, hash_a = importar_estoque_csv(db, carga_a_path)
            self.assertEqual(total_a, 1)
        finally:
            if os.path.exists(carga_a_path):
                os.remove(carga_a_path)

        # 2. Carga B com estouro cumulativo da carteira do FUNDO TESTE NOVO
        val_overflow = "9999999999999,00"  # Próximo ao teto, somado aos 500k existentes excede o teto
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(
                "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                f"FUNDO TESTE NOVO;11.111.111/0001-11;CEDENTE NOVO;22.222.222/0001-22;SACADO NOVO;33.333.333/0001-33;NF-NOVOFUNDO-02;Duplicata;{val_overflow};20/12/2026;01/05/2026\n"
            )
            carga_b_path = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                importar_estoque_csv(db, carga_b_path)
            self.assertIn("Saldo acumulado da carteira do fundo excede a capacidade técnica", str(ctx.exception))
        finally:
            if os.path.exists(carga_b_path):
                os.remove(carga_b_path)

        db.close()


if __name__ == "__main__":
    unittest.main()
