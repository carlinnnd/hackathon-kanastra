import io
import json
from datetime import date
from unittest.mock import patch

import pytest
from backend.api import auth_routes
from backend.domain import calendar
from backend.tests.test_result_reporting import isolated, lote, upload


@pytest.fixture
def auth_provider(monkeypatch):
    monkeypatch.setattr(auth_routes, 'config', lambda: {'domain': 'example.auth0.com',
        'client_id': 'client-public', 'client_secret': 'synthetic-server-secret',
        'connection': 'Username-Password-Authentication'})
    calls = []
    def provider(cfg, path, body=None, token=None):
        calls.append((path, body, token))
        if path == 'userinfo':
            assert token == 'synthetic-opaque-token'
            return {'sub': 'auth0|synthetic', 'name': 'Pessoa de teste', 'email': 'qa@example.invalid'}
        if path == 'dbconnections/signup':
            return {'_id': 'synthetic'}
        if body.get('password') == 'wrong':
            auth_routes.fail('AUTH0_AUTENTICACAO_RECUSADA', 'Credenciais inválidas.')
        return {'access_token': 'synthetic-opaque-token', 'expires_in': 600}
    monkeypatch.setattr(auth_routes, 'provider', provider)
    return calls


def test_login_session_logout_and_no_fallback(isolated, auth_provider):
    _, client, _ = isolated
    response = client.post('/api/auth/login', json={'email': 'qa@example.invalid', 'password': 'wrong'})
    assert response.status_code == 401
    assert not client.cookies
    assert client.get('/api/auth/session').status_code == 401
    response = client.post('/api/auth/login', json={'email': 'qa@example.invalid', 'password': 'synthetic-password'})
    assert response.status_code == 200
    assert response.json()['modo_autenticacao'] == 'auth0'
    assert 'synthetic-opaque-token' not in response.text
    assert 'httponly' in response.headers['set-cookie'].lower()
    assert 'samesite=lax' in response.headers['set-cookie'].lower()
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/api/auth/session').json()['id'] == 'auth0|synthetic'
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/session').status_code == 401


def test_signup_config_callback_and_origin(isolated, auth_provider):
    _, client, _ = isolated
    client.base_url = 'https://testserver'
    cfg = client.get('/api/auth/config')
    assert cfg.json()['configured']
    assert 'synthetic-server-secret' not in cfg.text
    response = client.post('/api/auth/login', json={'mode': 'signup', 'name': 'Teste', 'email': 'qa@example.invalid', 'password': 'synthetic-password'})
    assert response.status_code == 200
    assert auth_provider[0][0] == 'dbconnections/signup'
    payload = {'code': 'synthetic-code', 'redirect_uri': 'https://testserver/auth/callback', 'code_verifier': 'a' * 43}
    assert client.post('/api/auth/exchange', json={**payload, 'redirect_uri': 'https://evil.invalid/auth/callback'}).status_code == 422
    assert client.post('/api/auth/exchange', json={**payload, 'code_verifier': 'short'}).status_code == 422
    assert client.post('/api/auth/exchange', json=payload, headers={'Origin': 'https://evil.invalid'}).status_code == 403
    exchanged = client.post('/api/auth/exchange', json=payload)
    assert exchanged.status_code == 200
    assert 'secure' in exchanged.headers['set-cookie'].lower()
    assert auth_provider[-2][1]['code_verifier'] == 'a' * 43
    assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.invalid'}).status_code == 403


def test_private_api_requires_server_verified_session(isolated, auth_provider, monkeypatch):
    from backend.config import settings
    from starlette.websockets import WebSocketDisconnect
    _, client, _ = isolated
    monkeypatch.setattr(settings, 'PUBLIC_DEMO_MODE', False)
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/portfolio/summary').status_code == 401
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/api/simulations/stream'):
            pass
    assert client.post('/api/auth/login', json={'email': 'qa@example.invalid', 'password': 'synthetic-password'}).status_code == 200
    assert client.get('/api/portfolio/summary').status_code == 200
    client.post('/api/auth/logout')
    assert client.get('/api/portfolio/summary').status_code == 401


def test_missing_config_and_provider_unavailable_fail_closed(isolated, monkeypatch):
    _, client, _ = isolated
    monkeypatch.setattr(auth_routes, 'config', lambda: {'domain': '', 'client_id': '', 'client_secret': '', 'connection': 'test'})
    assert client.post('/api/auth/login', json={'email': 'qa@example.invalid', 'password': 'synthetic-password'}).status_code == 503
    monkeypatch.setattr(auth_routes, 'config', lambda: {'domain': 'example.auth0.com', 'client_id': 'public', 'client_secret': '', 'connection': 'test'})
    with patch('urllib.request.urlopen', side_effect=OSError('synthetic failure')):
        response = client.post('/api/auth/login', json={'email': 'qa@example.invalid', 'password': 'synthetic-password'})
    assert response.status_code == 502
    assert client.get('/api/auth/session').status_code == 401


def test_individual_what_if_and_samples_use_current_backend(isolated, monkeypatch):
    _, client, _ = isolated
    monkeypatch.setattr(calendar, 'data_atual', lambda: date(2026, 10, 25))
    text = lote([{'DATA_VENCIMENTO_ORIGINAL': '25/10/2026'}])
    import csv
    item = next(csv.DictReader(io.StringIO(text), delimiter=';'))
    response = client.post('/api/receivables/evaluate', json={'recebiveis': [item]})
    assert response.status_code == 200
    assert response.json()['data_base'] == '2026-10-25'
    rules = client.get('/api/rules').json()
    what_if = client.post('/api/simulations/what-if', json={'configuration': rules, 'sample_rows': 100})
    assert what_if.status_code == 200
    assert what_if.json()['data_base'] == '2026-10-25'
    assert what_if.json()['baseline']['total_itens'] == 100
    sample = client.get('/api/samples/100')
    assert sample.status_code == 200
    result = upload(client, sample.text)
    assert result['total_itens'] == 100
    assert result['data_base'] == '2026-10-25'
    assert client.get(f"/api/simulations/{result['simulation_id']}/export?format=csv").status_code == 200
    root = __import__('pathlib').Path(__file__).resolve().parents[4]
    source = (root/'Codex/antecipe/frontend/src/services/api.ts').read_text(encoding='utf-8')
    assert 'jwt-session-active' not in source and 'kanastra-sess-' not in source
