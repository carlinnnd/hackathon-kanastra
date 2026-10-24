"""
Testes independentes do contrato binário estrito (APROVADA / RECUSADA) para novas operações.
Garante:
1. Paridade CSV vs POST JSON para notas ativas, ausentes no cadastro e com erro de parsing,
   com aprovados + recusados = total_itens.
2. Leitura e exportação de simulações com registros históricos contendo status antigos
   (PENDENTE_VERIFICACAO / ERRO_DADOS), normalizados sem terceiro estado no envelope, CSV e analytics.
"""
import io
import json
from datetime import date
import pytest
from backend.domain.models import ResultadoAvaliacao, MotivoRecusa
from backend.infrastructure.database.models import (
    SimulationModel,
    SimulationItemModel,
    SimulationItemDetailModel,
    SimulationReportModel
)
from backend.infrastructure.repositories.simulations_repository import SimulationsRepository
from backend.tests.test_result_reporting import isolated, lote, upload


def test_01_paridade_binaria_csv_e_json(isolated):
    """
    CSV e POST /api/receivables/evaluate produzem a mesma decisão binária,
    motivos e líquido para sacado ativo, ausente e valor inválido.
    Aprovados + Recusados deve ser exatamente igual ao total de itens.
    """
    _, client, _ = isolated

    # Três cenários com vencimento e valor idênticos:
    # 1. Sacado ATIVA no mock (04.252.011/0001-10) -> APROVADA
    # 2. Sacado ausente no mock (11.444.777/0001-61) -> RECUSADA (SITUACAO_CADASTRAL_SACADO)
    # 3. Valor inválido ('abc') -> RECUSADA (FORMATO_INVALIDO_VALOR)
    linhas_csv = [
        {
            "NU_DOCUMENTO": "DOC-ATIVA",
            "DOC_SACADO": "04.252.011/0001-10",
            "VALOR_NOMINAL": "1000,00",
            "DATA_VENCIMENTO_ORIGINAL": "22/11/2026",
            "DATA_AQUISICAO": "22/10/2026",
            "TIPO_RECEBIVEL": "Duplicata",
        },
        {
            "NU_DOCUMENTO": "DOC-AUSENTE",
            "DOC_SACADO": "11.444.777/0001-61",
            "VALOR_NOMINAL": "2000,00",
            "DATA_VENCIMENTO_ORIGINAL": "22/11/2026",
            "DATA_AQUISICAO": "22/10/2026",
            "TIPO_RECEBIVEL": "Duplicata",
        },
        {
            "NU_DOCUMENTO": "DOC-INVALIDO",
            "DOC_SACADO": "04.252.011/0001-10",
            "VALOR_NOMINAL": "abc",
            "DATA_VENCIMENTO_ORIGINAL": "22/11/2026",
            "DATA_AQUISICAO": "22/10/2026",
            "TIPO_RECEBIVEL": "Duplicata",
        },
    ]

    # Execução via CSV
    res_csv = upload(client, lote(linhas_csv))
    assert res_csv["total_itens"] == 3
    assert res_csv["aprovados"] + res_csv["recusados"] == res_csv["total_itens"]
    assert res_csv["aprovados"] == 1
    assert res_csv["recusados"] == 2

    status_csv = [r["status"] for r in res_csv["resultados"]]
    assert status_csv == ["APROVADA", "RECUSADA", "RECUSADA"]

    # Execução via POST /api/receivables/evaluate com os exatos mesmos dados
    payload_json = {
        "data_base": "2026-10-22",
        "recebiveis": [
            {
                "NOME_FUNDO": "ANTECIPE FIDC",
                "DOC_FUNDO": "92.234.400/0001-80",
                "NOME_CEDENTE": "CEDENTE TESTE",
                "DOC_CEDENTE": "11222333000181",
                "NOME_SACADO": "SACADO TESTE",
                "DOC_SACADO": "04.252.011/0001-10",
                "NU_DOCUMENTO": "DOC-ATIVA",
                "VALOR_NOMINAL": "1000,00",
                "DATA_EMISSAO": "22/10/2026",
                "DATA_VENCIMENTO_ORIGINAL": "22/11/2026",
                "DATA_AQUISICAO": "22/10/2026",
                "TIPO_RECEBIVEL": "Duplicata",
            },
            {
                "NOME_FUNDO": "ANTECIPE FIDC",
                "DOC_FUNDO": "92.234.400/0001-80",
                "NOME_CEDENTE": "CEDENTE TESTE",
                "DOC_CEDENTE": "11222333000181",
                "NOME_SACADO": "SACADO TESTE",
                "DOC_SACADO": "11.444.777/0001-61",
                "NU_DOCUMENTO": "DOC-AUSENTE",
                "VALOR_NOMINAL": "2000,00",
                "DATA_EMISSAO": "22/10/2026",
                "DATA_VENCIMENTO_ORIGINAL": "22/11/2026",
                "DATA_AQUISICAO": "22/10/2026",
                "TIPO_RECEBIVEL": "Duplicata",
            },
            {
                "NOME_FUNDO": "ANTECIPE FIDC",
                "DOC_FUNDO": "92.234.400/0001-80",
                "NOME_CEDENTE": "CEDENTE TESTE",
                "DOC_CEDENTE": "11222333000181",
                "NOME_SACADO": "SACADO TESTE",
                "DOC_SACADO": "04.252.011/0001-10",
                "NU_DOCUMENTO": "DOC-INVALIDO",
                "VALOR_NOMINAL": "abc",
                "DATA_EMISSAO": "22/10/2026",
                "DATA_VENCIMENTO_ORIGINAL": "22/11/2026",
                "DATA_AQUISICAO": "22/10/2026",
                "TIPO_RECEBIVEL": "Duplicata",
            }
        ]
    }
    res_json = client.post("/api/receivables/evaluate", json=payload_json).json()

    assert res_json["total_itens"] == 3
    assert res_json["aprovados"] + res_json["recusados"] == res_json["total_itens"]
    assert res_json["aprovados"] == 1
    assert res_json["recusados"] == 2

    status_json = [r["status"] for r in res_json["resultados"]]
    assert status_json == ["APROVADA", "RECUSADA", "RECUSADA"]

    # Mesma precificação líquida na nota aprovada
    assert res_csv["total_liquido"] == res_json["total_liquido"]
    assert res_csv["resultados"][0]["valor_liquido"] == res_json["resultados"][0]["valor_liquido"]

    # Mesmos motivos nas notas recusadas
    motivos_csv_1 = [m["codigo"] for m in res_csv["resultados"][1]["motivos"]]
    motivos_json_1 = [m["codigo"] for m in res_json["resultados"][1]["motivos"]]
    assert motivos_csv_1 == motivos_json_1
    assert "SITUACAO_CADASTRAL_SACADO" in motivos_csv_1

    motivos_csv_2 = [m["codigo"] for m in res_csv["resultados"][2]["motivos"]]
    motivos_json_2 = [m["codigo"] for m in res_json["resultados"][2]["motivos"]]
    assert motivos_csv_2 == motivos_json_2
    assert "FORMATO_INVALIDO_VALOR" in motivos_csv_2


def test_02_normalizacao_legada_sem_terceiro_estado(isolated):
    """
    Simulações gravadas anteriormente com payload ou status PENDENTE_VERIFICACAO
    ou ERRO_DADOS são expostas pela API, exports CSV e analytics estritamente como
    APROVADA ou RECUSADA, sem alterar ou apagar registros no banco.
    """
    db, client, _ = isolated

    # Cria uma simulação gravando dados com status antigos diretamente na tabela
    sim_id = "sim-legada-test-binary"
    repo = SimulationsRepository(db)
    sim = repo.criar_simulacao_pai_inicial(
        simulation_id=sim_id,
        fundo_id=1,
        rule_version_id=1,
        data_base=date(2026, 10, 22),
        cadastro_fonte="TESTE_LEGADO",
        carteira_referencia="TESTE_CARTEIRA",
        configuration_hash="hash_teste_legado",
    )

    # Injeta 3 itens: um aprovado, um com status gravado PENDENTE_VERIFICACAO, um ERRO_DADOS
    payload_item1 = {
        "linha": 1, "documento": "DOC-1", "sacado": "SAC-1",
        "aprovado": True, "valor_nominal": "100.00", "valor_liquido": "98.00",
        "motivos": [], "status": "APROVADA", "originais": {}
    }
    payload_item2 = {
        "linha": 2, "documento": "DOC-2", "sacado": "SAC-2",
        "aprovado": False, "valor_nominal": "200.00", "valor_liquido": None,
        "motivos": [{"codigo": "SITUACAO_CADASTRAL_SACADO", "mensagem": "Pendente de teste"}],
        "status": "PENDENTE_VERIFICACAO", "originais": {}
    }
    payload_item3 = {
        "linha": 3, "documento": "DOC-3", "sacado": "SAC-3",
        "aprovado": False, "valor_nominal": None, "valor_liquido": None,
        "motivos": [{"codigo": "FORMATO_INVALIDO_VALOR", "mensagem": "Valor malformado"}],
        "status": "ERRO_DADOS", "originais": {}
    }

    # Grava itens filhos com status legados na tabela de detalhes
    db.add(SimulationItemDetailModel(simulation_id=sim_id, linha=1, status="APROVADA", payload_json=json.dumps(payload_item1)))
    db.add(SimulationItemDetailModel(simulation_id=sim_id, linha=2, status="PENDENTE_VERIFICACAO", payload_json=json.dumps(payload_item2)))
    db.add(SimulationItemDetailModel(simulation_id=sim_id, linha=3, status="ERRO_DADOS", payload_json=json.dumps(payload_item3)))

    db.add(SimulationItemModel(simulation_id=sim_id, linha=1, documento="DOC-1", sacado="SAC-1", aprovado=True, motivos_json="[]"))
    db.add(SimulationItemModel(simulation_id=sim_id, linha=2, documento="DOC-2", sacado="SAC-2", aprovado=False, motivos_json=json.dumps(payload_item2["motivos"])))
    db.add(SimulationItemModel(simulation_id=sim_id, linha=3, documento="DOC-3", sacado="SAC-3", aprovado=False, motivos_json=json.dumps(payload_item3["motivos"])))

    # Injeta analytics legado com status_counts contendo PENDENTE_VERIFICACAO e ERRO_DADOS
    analytics_legado = {
        "tipo_analise": "novas_operacoes",
        "status_counts": {
            "APROVADA": 1,
            "PENDENTE_VERIFICACAO": 1,
            "ERRO_DADOS": 1
        },
        "cadastro_counts": {},
        "fundos_distintos": 1,
        "grupos_sacado_distintos": 2,
        "valor_nominal_total": "300.00",
        "valor_nominal_elegivel": "100.00",
        "valor_desconto": "2.00",
        "valor_liquido": "98.00",
        "aprovacao_valor_pct": "33.33",
        "prazo_medio_ponderado": "30.00",
        "motivos": [],
        "faixas_vencimento": {},
        "exposicoes": [],
        "metodologia": "Teste legado",
        "regras": {"validadores": [], "precificacao": {}}
    }
    db.add(SimulationReportModel(simulation_id=sim_id, tipo_analise="novas_operacoes", analytics_json=json.dumps(analytics_legado)))
    db.commit()

    # Consulta a simulação via API REST
    res_get = client.get(f"/api/simulations/{sim_id}")
    assert res_get.status_code == 200
    data_get = res_get.json()

    # Verifica que os itens retornados não têm terceiro estado
    statuses = [item["status"] for item in data_get["resultados"]]
    assert statuses == ["APROVADA", "RECUSADA", "RECUSADA"]

    # Verifica analytics normalizado: apenas APROVADA e RECUSADA em status_counts
    analytics = data_get["analytics"]
    assert "PENDENTE_VERIFICACAO" not in analytics["status_counts"]
    assert "ERRO_DADOS" not in analytics["status_counts"]
    assert analytics["status_counts"] == {"APROVADA": 1, "RECUSADA": 2}

    # Verifica exportação CSV: o CSV gerado reflete status RECUSADA para as linhas 2 e 3
    csv_resp = client.get(f"/api/simulations/{sim_id}/export?format=csv")
    assert csv_resp.status_code == 200
    csv_text = csv_resp.text
    assert "PENDENTE_VERIFICACAO" not in csv_text
    assert "ERRO_DADOS" not in csv_text
    assert "APROVADA" in csv_text
    assert "RECUSADA" in csv_text
