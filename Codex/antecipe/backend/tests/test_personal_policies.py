"""Isolamento entre contas, persistÃªncia remota e uso efetivo das polÃ­ticas."""
import copy
import csv
import io
import json
import pytest
from backend.api import auth_routes, policy_routes
from backend.tests.test_result_reporting import isolated, lote, upload


@pytest.fixture
def accounts(monkeypatch):
    remote = {}
    monkeypatch.setenv('AUTH0_MANAGEMENT_API_CLIENT_ID', 'synthetic-client')
    monkeypatch.setattr(auth_routes, 'profile', lambda cfg, token: {'id': 'auth0|' + token})
    def management(subject, patch=None, token=None):
        metadata = remote.setdefault(subject, {})
        if patch is not None:
            metadata.update(copy.deepcopy(patch))
        return copy.deepcopy(metadata)
    monkeypatch.setattr(policy_routes, 'management', management)
    return remote


def test_accounts_own_versions_and_active_selection(isolated, accounts):
    _, client, _ = isolated
    cfg = client.get('/api/rules').json()
    assert client.get('/api/policies').status_code == 401
    client.cookies.set(auth_routes.COOKIE, 'account-a')
    cfg['precificacao']['taxa_mensal_percentual'] = 3
    saved = client.post('/api/policies', json={'name': 'PolÃ­tica A', 'configuration': cfg})
    assert saved.status_code == 200
    policy_id = saved.json()['id']
    assert client.get('/api/policies').json()[0]['is_active']
    assert client.get('/api/rules').json()['precificacao']['taxa_mensal_percentual'] == 3
    first = upload(client, lote([{}]))
    assert first['total_liquido'] == '4550.00'
    assert first['analytics']['regras']['precificacao']['taxa_mensal_percentual'] == 3
    client.cookies.set(auth_routes.COOKIE, 'account-b')
    assert client.get('/api/policies').json() == []
    assert client.post(f'/api/policies/{policy_id}/activate').status_code == 404
    assert float(client.get('/api/rules').json()['precificacao']['taxa_mensal_percentual']) == 2
    client.cookies.set(auth_routes.COOKIE, 'account-a')
    assert client.get('/api/policies').json()[0]['id'] == policy_id
    assert client.post('/api/policies/default/activate').status_code == 200
    assert not client.get('/api/policies').json()[0]['is_active']
    assert float(client.get('/api/rules').json()['precificacao']['taxa_mensal_percentual']) == 2
    assert client.post(f'/api/policies/{policy_id}/activate', headers={'Origin': 'https://evil.invalid'}).status_code == 403
    assert client.post(f'/api/policies/{policy_id}/activate').status_code == 200
    item = next(csv.DictReader(io.StringIO(lote([{}])), delimiter=';'))
    single = client.post('/api/receivables/evaluate', json={'recebiveis': [item]}).json()
    assert single['total_liquido'] == first['total_liquido']
    # Selecionar outra polÃ­tica nÃ£o reescreve a fonte do relatÃ³rio concluÃ­do.
    client.post('/api/policies/default/activate')
    report = client.get(f"/api/simulations/{first['simulation_id']}/analytics").json()
    assert report['regras']['precificacao']['taxa_mensal_percentual'] == 3


def test_validation_limits_and_remote_failure(isolated, accounts, monkeypatch):
    _, client, _ = isolated
    cfg = client.get('/api/rules').json()
    client.cookies.set(auth_routes.COOKIE, 'account-a')
    for name, configuration in [(' ', cfg), ('InvÃ¡lida', {}), ('Grande', {**cfg, 'extra': 'x'*13000})]:
        assert client.post('/api/policies', json={'name': name, 'configuration': configuration}).status_code == 422
    def unavailable(*args, **kwargs):
        auth_routes.fail('POLITICAS_INDISPONIVEIS', 'NÃ£o foi possÃ­vel salvar.', 503)
    monkeypatch.setattr(policy_routes, 'management', unavailable)
    assert client.post('/api/policies', json={'name': 'NÃ£o salva', 'configuration': cfg}).status_code == 503
    assert client.get('/api/policies').status_code == 503


def test_management_uses_encoded_verified_subject_and_patch_namespace(monkeypatch):
    from unittest.mock import patch
    monkeypatch.setattr(auth_routes, 'config', lambda: {'domain':'example.auth0.com','client_id':'public'})
    class Response(io.BytesIO):
        pass
    def urlopen(request, timeout):
        assert request.full_url.endswith('/api/v2/users/auth0%7Caccount-a')
        assert request.method == 'PATCH'
        assert json.loads(request.data) == {'user_metadata': {'antecipe_active_policy': 'id'}}
        return Response(b'{"app_metadata":{"unrelated":"preserved"}}')
    with patch('urllib.request.urlopen', side_effect=urlopen):
        assert policy_routes.management('auth0|account-a', {'antecipe_active_policy':'id'}, token='synthetic-current-user-token') == {'unrelated':'preserved'}


def test_stream_freezes_personal_policy_at_start(isolated, accounts):
    _, client, _ = isolated
    cfg = client.get('/api/rules').json()
    cfg['precificacao']['taxa_mensal_percentual'] = 3
    client.cookies.set(auth_routes.COOKIE, 'account-a')
    assert client.post('/api/policies', json={'name': 'Taxa 3', 'configuration': cfg}).status_code == 200
    comparison = client.post('/api/simulations/what-if', json={'configuration': cfg, 'sample_rows': 100})
    assert comparison.status_code == 200
    assert comparison.json()['delta']['liquido_delta_brl'] == '0.00'
    text = lote([{}]).encode()
    with client.websocket_connect('/api/simulations/stream') as ws:
        ws.send_json({'type':'start', 'filename':'lote.csv', 'size_bytes':len(text), 'protocol_version':1})
        assert ws.receive_json()['type'] == 'ready'
        # Uma troca posterior não deve alterar o lote em andamento.
        assert client.post('/api/policies/default/activate').status_code == 200
        ws.send_bytes(text)
        while ws.receive_json()['type'] != 'ack': pass
        ws.send_json({'type':'finish'})
        while True:
            event = ws.receive_json()
            assert event['type'] != 'error'
            if event['type'] == 'complete': break
        assert event['simulation']['total_liquido'] == '4550.00'
        ws.send_json({'type':'close'})
