"""Regressões do cadastro recebido, decisões, carteira e exportações da mesma fonte."""
import base64
import csv
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.api.bulk_routes import criar_sessao_isolada_para_conexao
from backend.infrastructure.database.session import get_db
from backend.infrastructure.database.models import SimulationModel, SimulationItemDetailModel, SimulationReportModel
from backend.application.cadastral_service import carregar_cadastro
from backend.application.simulation_service import SimulationService
from backend.domain.ingestion import CABECALHOS_OBRIGATORIOS, iterar_csv_recebiveis


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    mock = tmp_path / "cadastro.csv"
    mock.write_text("DOC;SITUACAO_CADASTRAL\n04.252.011/0001-10;ATIVA\n33.000.167/0001-01;INAPTA\n", encoding="utf-8")
    monkeypatch.setattr(settings, "PUBLIC_DEMO_MODE", True)
    monkeypatch.setattr(settings, "ENABLE_DEMO_CADASTRO", True)
    monkeypatch.setattr(settings, "CADASTRO_MOCK_PATH", str(mock))
    db, engine = criar_sessao_isolada_para_conexao()
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = lambda: db
    yield db, TestClient(app), mock
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    db.close(); engine.dispose()


def lote(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(CABECALHOS_OBRIGATORIOS + ["REFERENCIA_CLIENTE"])
    for i, overrides in enumerate(rows):
        row = ["ANTECIPE FIDC", "92234400000180", "CEDENTE TESTE", "11222333000181", "SACADO TESTE",
               "04252011000110", f"NF-{i}", "Duplicata", "5000,00", "20/01/2027", "", "=1+1"]
        for key, value in overrides.items():
            row[(CABECALHOS_OBRIGATORIOS + ["REFERENCIA_CLIENTE"]).index(key)] = value
        writer.writerow(row)
    return output.getvalue()


def upload(client, text, tipo="novas_operacoes"):
    response = client.post(f"/api/simulations?tipo_analise={tipo}", files={"file": ("lote.csv", text.encode(), "text/csv")})
    assert response.status_code == 200, response.status_code
    return response.json()


def test_mock_normaliza_e_falha_fechado(isolated, monkeypatch):
    _, _, mock = isolated
    mapa, source = carregar_cadastro()
    assert mapa["04252011000110"] == "ATIVA"
    assert mapa["33000167000101"] == "INAPTA"
    assert source.startswith("SIMULADO_CSV_SHA256_")
    monkeypatch.setattr(settings, "ENABLE_DEMO_CADASTRO", False)
    assert carregar_cadastro()[0] == {}
    monkeypatch.setattr(settings, "ENABLE_DEMO_CADASTRO", True)
    mock.write_text("DOC;SITUACAO_CADASTRAL\n04252011000110;ATIVA\n04252011000110;INAPTA\n", encoding="utf-8")
    assert carregar_cadastro()[0] == {}
    monkeypatch.setattr(settings, "CADASTRO_MOCK_PATH", str(mock.parent / 'ausente.csv'))
    assert carregar_cadastro()[0] == {}


def test_decisao_binaria_precificacao_e_multiplas_violacoes(isolated):
    _, client, _ = isolated
    data = upload(client, lote([
        {}, {"DOC_SACADO": "11444777000161"}, {"DOC_SACADO": "33000167000101"},
        {"VALOR_NOMINAL": "abc"},
        {"DOC_SACADO": "11444777000161", "TIPO_RECEBIVEL": "Cheque", "DATA_VENCIMENTO_ORIGINAL": "01/06/2027"},
    ]))
    assert [r["status"] for r in data["resultados"]] == ["APROVADA", "RECUSADA", "RECUSADA", "RECUSADA", "RECUSADA"]
    assert data["aprovados"] + data["recusados"] == data["total_itens"]
    assert data["analytics"]["status_counts"] == {"APROVADA": 1, "RECUSADA": 4}
    assert data["total_liquido"] == "4700.00"
    assert data["analytics"]["valor_desconto"] == "300.00"
    assert {m["codigo"] for m in data["resultados"][-1]["motivos"]} >= {"SITUACAO_CADASTRAL_SACADO", "TIPO_RECEBIVEL", "PRAZO_MAXIMO"}
    assert all(r["valor_liquido"] is None for r in data["resultados"][1:])
    rejected = client.get(f"/api/simulations/{data['simulation_id']}/items?status=RECUSADA").json()
    assert rejected["pagination"]["total"] == 4
    assert all(r["status"] == "RECUSADA" for r in rejected["resultados"])


def test_estoque_nao_vira_nova_operacao(isolated):
    _, client, _ = isolated
    data = upload(client, lote([{}, {"TIPO_RECEBIVEL": "Cheque", "VALOR_NOMINAL": "50,00", "DATA_VENCIMENTO_ORIGINAL": "01/01/2020"}]), "carteira")
    assert data["analytics"]["status_counts"] == {"CARTEIRA_HISTORICA": 2}
    assert data["total_liquido"] == "0.00"
    assert data["recusados"] == 0
    assert data["analytics"]["valor_nominal_elegivel"] == "0.00"
    assert data["analytics"]["valor_nominal_total"] == "5050.00"
    assert data["analytics"]["exposicoes"][0]["percentual"] == "100.00"
    assert all(r["motivos"] == [] for r in data["resultados"])


def test_demo_usa_cadastro_ativo_da_fonte_selecionada(isolated):
    _, client, mock = isolated
    with mock.open('a', encoding='utf-8') as stream:
        stream.write('11444777000161;ATIVA\n')
    response = client.get('/api/demo.csv')
    data = upload(client, response.content.decode('utf-8-sig'))
    assert data['resultados'][0]['status'] == 'APROVADA'
    assert data['resultados'][0]['doc_sacado'] == '11444777000161'


def test_export_csv_completo_sobre_paginacao_e_pdf(isolated, tmp_path):
    _, client, _ = isolated
    data = upload(client, lote([{} for _ in range(63)]))
    assert len(data["resultados"]) == 50
    base = f"/api/simulations/{data['simulation_id']}"
    csv_response = client.get(base + "/export?format=csv")
    assert csv_response.status_code == 200
    assert csv_response.content.startswith(b'\xef\xbb\xbf')
    rows = list(csv.DictReader(io.StringIO(csv_response.content.decode('utf-8-sig')), delimiter=';'))
    assert len(rows) == 63
    assert rows[0]['REFERENCIA_CLIENTE'] == "'=1+1"
    assert rows[0]['valor_liquido'] == '4700,00'
    assert rows[0]['valor_desconto'] == '300,00'
    assert all(r['valor_liquido'] == '' for r in rows if r['status'] != 'APROVADA')
    analytics = client.get(base + '/analytics').json()
    assert analytics == data['analytics']
    violacoes = client.get(base + '/export?format=violacoes')
    violations = list(csv.DictReader(io.StringIO(violacoes.content.decode('utf-8-sig')), delimiter=';'))
    assert len(violations) == sum(int(r['quantidade_violacoes']) for r in rows)
    pdf_response = client.get(base + '/export?format=pdf')
    assert pdf_response.status_code == 200 and pdf_response.content.startswith(b'%PDF-')
    import re
    assert 4 <= len(re.findall(rb'/Type\s*/Page\b', pdf_response.content)) <= 6
    assert client.get(base + '/export?format=html').status_code == 422
    assert client.get('/api/simulations/inexistente/export?format=csv').status_code == 404


def test_duplicidade_e_regras_inativas_preservadas(isolated):
    _, client, _ = isolated
    data = upload(client, lote([
        {"NU_DOCUMENTO": "REPETIDA", "DATA_VENCIMENTO_ORIGINAL": "23/10/2026"},
        {"NU_DOCUMENTO": "REPETIDA", "DATA_VENCIMENTO_ORIGINAL": "23/10/2026"},
        {"NU_DOCUMENTO": "REPETIDA", "DATA_VENCIMENTO_ORIGINAL": "24/10/2026"},
    ]))
    assert data["resultados"][0]["status"] == "APROVADA"
    assert data["resultados"][1]["status"] == "RECUSADA"
    assert any(m['codigo'] == 'DUPLICIDADE_LOTE' for m in data['resultados'][1]['motivos'])
    assert data["resultados"][2]["status"] == "APROVADA"
    assert not any(m['codigo'] == 'PRAZO_MINIMO' for r in data['resultados'] for m in r['motivos'])


def test_rollback_inclui_detalhes_e_relatorio(isolated):
    db, _, _ = isolated
    stream = iterar_csv_recebiveis(io.StringIO(lote([{} for _ in range(2001)])))
    with pytest.raises(ValueError):
        SimulationService(db).executar_simulacao_lote(stream, max_records=2000)
    assert db.query(SimulationModel).count() == 0
    assert db.query(SimulationItemDetailModel).count() == 0
    assert db.query(SimulationReportModel).count() == 0


def test_websocket_exporta_mesma_sessao_sem_aceitar_id_externo(isolated):
    _, client, _ = isolated
    text = lote([{}, {"DOC_SACADO": "11444777000161"}]).encode()
    with client.websocket_connect('/api/simulations/stream') as ws:
        ws.send_json({'type':'start', 'filename':'lote.csv', 'size_bytes':len(text), 'protocol_version':1})
        assert ws.receive_json()['type'] == 'ready'
        ws.send_bytes(text)
        while ws.receive_json()['type'] != 'ack': pass
        ws.send_json({'type':'finish'})
        while True:
            event = ws.receive_json()
            assert event['type'] != 'error'
            if event['type'] == 'complete': break
        ws.send_json({'type':'export', 'request_id':'e1', 'format':'csv', 'simulation_id':'outro-id'})
        chunks=[]
        while True:
            event = ws.receive_json()
            assert event['type'] != 'error'
            if event['type'] == 'export_complete': break
            chunks.append(base64.b64decode(event['data']))
        rows=list(csv.DictReader(io.StringIO(b''.join(chunks).decode('utf-8-sig')),delimiter=';'))
        assert len(rows) == 2
        assert {r['status'] for r in rows} == {'APROVADA', 'RECUSADA'}
        ws.send_json({'type':'close'})
