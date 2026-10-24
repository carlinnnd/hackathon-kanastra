"""
Suíte abrangente de testes automatizados HTTP e de integração do Backend Antecipe via httpx.
Cobre todos os 20 requisitos relevantes com StaticPool compartilhado.
"""
import io
import json
import os
import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.infrastructure.database.session import get_db
from backend.main import app
from backend.config import settings
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

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    init_shared_test_db()


def test_01_healthcheck():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "ANTECIPE" in data["fundo"]


def test_02_demo_csv_endpoint():
    res = client.get("/api/demo.csv")
    assert res.status_code == 200
    assert "NOME_FUNDO" in res.text
    assert "COMERCIAL ALPHA LTDA" in res.text


def test_03_portfolio_summary_endpoint():
    res = client.get("/api/portfolio/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_nominal" in data
    assert "total_recebiveis" in data


def test_04_get_active_rules():
    res = client.get("/api/rules")
    assert res.status_code == 200
    data = res.json()
    assert "validadores" in data
    assert "precificacao" in data
    assert data["precificacao"]["metodo"] == "DESCONTO_SIMPLES"


def test_05_upload_csv_calculo_precificacao():
    csv_content = (
        "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-TESTE-90D;Duplicata;5000,00;20/01/2027;\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["total_itens"] == 1
    assert data["aprovados"] == 1
    assert data["recusados"] == 0
    assert data["total_nominal"] == "5000.00"
    assert data["total_liquido"] == "4700.00"
    item = data["resultados"][0]
    assert item["aprovado"] is True
    assert item["valor_liquido"] == "4700.00"


def test_06_recusa_por_valor_minimo():
    csv_content = (
        "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-VALOR-BAIXO;Duplicata;99,99;20/01/2027;\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["aprovados"] == 0
    assert data["recusados"] == 1
    motivos = [m["codigo"] for m in data["resultados"][0]["motivos"]]
    assert "VALOR_MINIMO" in motivos


def test_07_recusa_por_prazo_maximo():
    csv_content = (
        "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-PRAZO-LONGO;Duplicata;1500,00;20/12/2027;\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["recusados"] == 1
    motivos = [m["codigo"] for m in data["resultados"][0]["motivos"]]
    assert "PRAZO_MAXIMO" in motivos


def test_08_recusa_por_tipo_recebivel():
    csv_content = (
        "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-CHEQUE;Cheque;1500,00;20/01/2027;\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["recusados"] == 1
    motivos = [m["codigo"] for m in data["resultados"][0]["motivos"]]
    assert "TIPO_RECEBIVEL" in motivos


def test_09_recusa_por_situacao_cadastral_inativa_e_nao_verificada():
    csv_content = (
        "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;EMPRESA INATIVA;33.000.167/0001-01;NF-INATIVA;Duplicata;2000,00;20/01/2027;\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;EMPRESA DESCONHECIDA;88.888.888/0001-88;NF-DESCONHECIDA;Duplicata;2000,00;20/01/2027;\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["recusados"] == 2
    motivos_item1 = [m["codigo"] for m in data["resultados"][0]["motivos"]]
    motivos_item2 = [m["codigo"] for m in data["resultados"][1]["motivos"]]
    assert "SITUACAO_CADASTRAL_SACADO" in motivos_item1
    assert "PENDENTE_VERIFICACAO" in motivos_item2
    assert data["resultados"][1]["status"] == "RECUSADA"  # CNPJ inválido é violação confirmada.


def test_10_duplicidade_intra_lote():
    csv_content = (
        "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-DUP-INTRA;Duplicata;2000,00;20/01/2027;\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-DUP-INTRA;Duplicata;2000,00;20/01/2027;\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["aprovados"] == 1
    assert data["recusados"] == 1
    motivos_dup = [m["codigo"] for m in data["resultados"][1]["motivos"]]
    assert "DUPLICIDADE_LOTE" in motivos_dup


def test_11_duplicidade_com_estoque_historico():
    csv_content = (
        "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
        "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-HIST-01;Duplicata;2000,00;20/01/2027;\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["recusados"] == 1
    motivos = [m["codigo"] for m in data["resultados"][0]["motivos"]]
    assert "DUPLICIDADE_HISTORICA" in motivos


def test_12_rejeicao_cabecalho_invalido():
    csv_invalido = "COLUNA_A;COLUNA_B\n1;2\n"
    files = {"file": ("test.csv", io.BytesIO(csv_invalido.encode("utf-8")), "text/csv")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code in (200, 422)
    if res.status_code == 200:
        data = res.json()
        assert data["recusados"] == 1
        assert "CABECALHO" in data["resultados"][0]["motivos"][0]["codigo"]
    else:
        assert res.json()["detail"]["codigo"] in ("CABECALHO_INVALIDO", "ERRO_PROCESSAMENTO")


def test_13_avaliacao_via_json_evaluate():
    payload = {
        "recebiveis": [
            {
                "NOME_CEDENTE": "INDUSTRIA BRASIL SA",
                "DOC_CEDENTE": "11.222.333/0001-81",
                "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                "DOC_SACADO": "04.252.011/0001-10",
                "NU_DOCUMENTO": "NF-JSON-01",
                "TIPO_RECEBIVEL": "Duplicata",
                "VALOR_NOMINAL": "5000,00",
                "DATA_VENCIMENTO_ORIGINAL": "20/01/2027"
            }
        ],
        "data_base": "2026-10-22"
    }
    res = client.post("/api/receivables/evaluate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_itens"] == 1
    assert data["aprovados"] == 1
    assert data["total_liquido"] == "4700.00"


def test_14_admin_auth_invalida_retorna_401():
    payload = {"configuration": {}, "change_reason": "teste"}
    res = client.post("/api/rules/versions", json=payload, headers={"X-Admin-Token": "token-falso"})
    assert res.status_code == 401
    assert res.json()["detail"]["codigo"] == "ADMIN_TOKEN_INVALIDO"


def test_15_versionamento_persistente_criar_e_ativar():
    token = "hackathon-test-admin-token-2026"
    res_ativa = client.get("/api/rules")
    cfg = res_ativa.json()
    
    for val in cfg["validadores"]:
        if val["codigo"] == "PRAZO_MAXIMO":
            val["parametros"]["prazo_maximo_dias"] = 120

    res_pub = client.post(
        "/api/rules/versions",
        json={"configuration": cfg, "change_reason": "Redução do prazo máximo para 120 dias"},
        headers={"X-Admin-Token": token}
    )
    assert res_pub.status_code == 200
    v2_id = res_pub.json()["id"]
    assert res_pub.json()["version_number"] == 2

    res_act = client.post(
        f"/api/rules/versions/{v2_id}/activate",
        headers={"X-Admin-Token": token}
    )
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "activated"

    res_ativa_nova = client.get("/api/rules")
    pm = next(v for v in res_ativa_nova.json()["validadores"] if v["codigo"] == "PRAZO_MAXIMO")
    assert pm["parametros"]["prazo_maximo_dias"] == 120


def test_16_consulta_simulacao_paginada_e_filtros():
    payload = {
        "recebiveis": [
            {
                "NOME_CEDENTE": "INDUSTRIA BRASIL SA",
                "DOC_CEDENTE": "11.222.333/0001-81",
                "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                "DOC_SACADO": "04.252.011/0001-10",
                "NU_DOCUMENTO": "NF-PAG-01",
                "TIPO_RECEBIVEL": "Duplicata",
                "VALOR_NOMINAL": "1000,00",
                "DATA_VENCIMENTO_ORIGINAL": "20/11/2026"
            },
            {
                "NOME_CEDENTE": "INDUSTRIA BRASIL SA",
                "DOC_CEDENTE": "11.222.333/0001-81",
                "NOME_SACADO": "COMERCIAL ALPHA LTDA",
                "DOC_SACADO": "04.252.011/0001-10",
                "NU_DOCUMENTO": "NF-PAG-02",
                "TIPO_RECEBIVEL": "Cheque",
                "VALOR_NOMINAL": "1000,00",
                "DATA_VENCIMENTO_ORIGINAL": "20/11/2026"
            }
        ]
    }
    res_sim = client.post("/api/receivables/evaluate", json=payload)
    assert res_sim.status_code == 200
    sim_id = res_sim.json()["simulation_id"]

    res_get_aprovados = client.get(f"/api/simulations/{sim_id}?status=aprovado")
    assert res_get_aprovados.status_code == 200
    data_aprov = res_get_aprovados.json()
    assert len(data_aprov["resultados"]) == 1
    assert data_aprov["resultados"][0]["aprovado"] is True

    res_get_recusados = client.get(f"/api/simulations/{sim_id}?status=recusado")
    assert res_get_recusados.status_code == 200
    data_rec = res_get_recusados.json()
    assert len(data_rec["resultados"]) == 1
    assert data_rec["resultados"][0]["aprovado"] is False


def test_17_arquivo_nao_csv_rejeitado_400():
    files = {"file": ("malicioso.exe", io.BytesIO(b"dados"), "application/octet-stream")}
    res = client.post("/api/simulations", files=files)
    assert res.status_code == 400
    assert res.json()["detail"]["codigo"] == "FORMATO_ARQUIVO_INVALIDO"


def test_18_payload_vazio_evaluate_retorna_400():
    res = client.post("/api/receivables/evaluate", json={"recebiveis": []})
    assert res.status_code == 400
    assert res.json()["detail"]["codigo"] == "PAYLOAD_VAZIO"


def test_19_simulacao_nao_encontrada_retorna_404():
    res = client.get("/api/simulations/sim-inexistente-12345")
    assert res.status_code == 404
    assert res.json()["detail"]["codigo"] == "SIMULACAO_NAO_ENCONTRADA"


def test_20_lista_versoes_mostra_ativo():
    res = client.get("/api/rules/versions")
    assert res.status_code == 200
    versoes = res.json()
    assert len(versoes) >= 2
    ativos = [v for v in versoes if v["is_active"]]
    assert len(ativos) == 1
