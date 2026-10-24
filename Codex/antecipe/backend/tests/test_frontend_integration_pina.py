"""
Testes dos endpoints de integração do Frontend (PINA-0009):
- Login por e-mail/senha (router de Elias em login/vercel_auth_helper.py);
- Edição e ativação de regras pelo Front (PUT /api/rules/active) e restauração do padrão;
- Simulação What-If sem persistir regra;
- Raio-X do grupo econômico.
Nenhum teste registra credenciais ou dados de CSV em log.
"""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.infrastructure.database.session import get_db
from backend.main import app
from backend.config import settings
from backend.tests.test_db_shared import SharedTestingSessionLocal, init_shared_test_db

settings.ENABLE_DEMO_CADASTRO = True
settings.PUBLIC_DEMO_MODE = True


def _override_get_db():
    db = SharedTestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    settings.PUBLIC_DEMO_MODE = True
    settings.ENABLE_DEMO_CADASTRO = True
    client.cookies.clear()
    init_shared_test_db()


def test_login_aceita_qualquer_email_valido(monkeypatch):
    monkeypatch.setattr("backend.api.auth_routes.config", lambda: {"domain": "mock.auth0.com", "client_id": "test_id", "client_secret": "", "connection": "Username-Password-Authentication"})
    monkeypatch.setattr("backend.api.auth_routes.provider", lambda cfg, path, body=None, token=None: {"access_token": "mock-token", "sub": "auth0|mock123", "email": "pessoa.teste@gmail.com"})
    res = client.post("/api/auth/login", json={"email": "Pessoa.Teste@Gmail.com", "password": "segredo123", "cargo": "Outros"})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "pessoa.teste@gmail.com"
    assert data["cargo"] == "Operador"
    assert "segredo123" not in str(data)


def test_login_rejeita_email_invalido():
    res = client.post("/api/auth/login", json={"email": "sem-arroba", "password": "segredo123"})
    assert res.status_code == 422
    assert res.json()["detail"]["codigo"] == "EMAIL_INVALIDO"


def test_put_rules_active_cria_e_ativa_nova_versao_sem_admin_token():
    atual = client.get("/api/rules").json()
    nova = copy.deepcopy(atual)
    for v in nova["validadores"]:
        if v["codigo"] == "VALOR_MINIMO":
            v["parametros"]["valor_minimo"] = 250
    res = client.put("/api/rules/active", json={"configuration": nova, "change_reason": "Teste front"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "activated"

    ativa = client.get("/api/rules").json()
    valor = next(v for v in ativa["validadores"] if v["codigo"] == "VALOR_MINIMO")["parametros"]["valor_minimo"]
    assert float(valor) == 250

    versoes = client.get("/api/rules/versions").json()
    assert sum(1 for v in versoes if v["is_active"]) == 1
    assert next(v for v in versoes if v["is_active"])["version_number"] == body["version_number"]

    reset = client.post("/api/rules/reset-default")
    assert reset.status_code == 200
    padrao = client.get("/api/rules").json()
    valor_padrao = next(v for v in padrao["validadores"] if v["codigo"] == "VALOR_MINIMO")["parametros"]["valor_minimo"]
    assert float(valor_padrao) != 250


def test_put_rules_active_rejeita_configuracao_invalida():
    atual = client.get("/api/rules").json()
    invalida = copy.deepcopy(atual)
    invalida["validadores"] = "nao-e-lista"
    res = client.put("/api/rules/active", json={"configuration": invalida})
    assert res.status_code == 422


def test_admin_continua_exigindo_token_em_rules_versions():
    atual = client.get("/api/rules").json()
    res = client.post("/api/rules/versions", json={"configuration": atual}, headers={"X-Admin-Token": "errado"})
    assert res.status_code in (401, 503)


def test_what_if_nao_altera_regra_ativa():
    antes = client.get("/api/rules/versions").json()
    atual = client.get("/api/rules").json()
    res = client.post("/api/simulations/what-if", json={"configuration": atual, "sample_rows": 100})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["baseline"]["total_itens"] == data["what_if"]["total_itens"] == 100
    assert data["delta"]["aprovados_delta"] == 0
    assert client.get("/api/rules/versions").json() == antes


def test_raio_x_grupo_economico_estrutura():
    res = client.get("/api/portfolio/economic-group/58.206.002")
    assert res.status_code == 200
    data = res.json()
    assert data["raiz_cnpj"] == "58206002"
    assert "filiais" in data and isinstance(data["filiais"], list)

