"""Regressões da recusa Auth0 real: fluxos desabilitados e cookie no WebSocket."""
import io
import json
import urllib.error
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from starlette.websockets import WebSocketDisconnect
from backend.api import auth_routes, policy_routes
from backend.tests.test_result_reporting import isolated

CFG = {'domain':'example.auth0.com','client_id':'public-client','client_secret':'synthetic-secret','connection':'Users'}


def denied(code='unauthorized_client', status=403):
    return urllib.error.HTTPError('https://example.auth0.com/oauth/token', status, 'Denied', {},
        io.BytesIO(json.dumps({'error': code, 'error_description':'raw sensitive sentinel never exposed'}).encode()))


def test_disabled_password_flow_has_specific_code_without_provider_payload():
    with patch('urllib.request.urlopen', side_effect=denied()):
        with pytest.raises(HTTPException) as error:
            auth_routes.provider(CFG, 'oauth/token', {'grant_type':'http://auth0.com/oauth/grant-type/password-realm'})
    assert error.value.status_code == 503
    assert error.value.detail['codigo'] == 'AUTH0_FLUXO_NAO_AUTORIZADO'
    assert 'sentinel' not in str(error.value.detail)


def test_signup_committed_is_not_reported_as_failed_registration(isolated, monkeypatch):
    _, client, _ = isolated
    monkeypatch.setattr(auth_routes, 'config', lambda: CFG)
    def provider(cfg, path, body=None, token=None):
        if path == 'dbconnections/signup': return {'_id':'synthetic'}
        auth_routes.fail('AUTH0_FLUXO_NAO_AUTORIZADO', 'Entre na página segura do Auth0.',503)
    monkeypatch.setattr(auth_routes, 'provider', provider)
    response=client.post('/api/auth/login',json={'mode':'signup','name':'Teste','email':'qa@example.invalid','password':'synthetic-password'})
    assert response.status_code==409
    assert response.json()['detail']['cadastro_criado'] is True
    assert response.json()['detail']['causa_codigo']=='AUTH0_FLUXO_NAO_AUTORIZADO'
    assert not client.cookies


def test_old_cookie_stream_returns_actionable_error_before_any_csv(isolated, monkeypatch):
    _, client, _ = isolated
    monkeypatch.setattr(auth_routes, 'profile', lambda cfg, token: {'id':'auth0|account-a'})
    client.cookies.set(auth_routes.COOKIE,'synthetic-old-token')
    with patch('urllib.request.urlopen', side_effect=denied('invalid_token',401)):
        with client.websocket_connect('/api/simulations/stream') as ws:
            event=ws.receive_json()
            assert event['type']=='error'
            assert event['codigo']=='POLITICAS_REAUTENTICACAO_NECESSARIA'
            assert 'Saia e entre novamente' in event['mensagem']
            with pytest.raises(WebSocketDisconnect): ws.receive_json()


def test_personal_token_merges_legacy_read_only_and_default_shadows_old_selection(monkeypatch):
    monkeypatch.setattr(auth_routes,'config',lambda:CFG)
    response={'app_metadata':{'antecipe_active_policy':'old','antecipe_policy_old':{'name':'Anterior'}},
        'user_metadata':{'antecipe_active_policy':'default'}}
    with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as call:
        metadata=policy_routes.management('auth0|account-a',{'antecipe_active_policy':'default'}, token='synthetic-self-token')
    request=call.call_args.args[0]
    assert request.get_header('Authorization')=='Bearer synthetic-self-token'
    assert json.loads(request.data)=={'user_metadata':{'antecipe_active_policy':'default'}}
    assert metadata['antecipe_active_policy']=='default'
    assert metadata['antecipe_policy_old']['name']=='Anterior'


def test_invalid_saved_config_fails_with_structured_error(isolated,monkeypatch):
    _,client,_=isolated
    client.cookies.set(auth_routes.COOKIE,'synthetic-self-token')
    monkeypatch.setattr(auth_routes,'profile',lambda *args:{'id':'auth0|self'})
    monkeypatch.setattr(policy_routes,'management',lambda *args,**kwargs:{policy_routes.ACTIVE:'bad',policy_routes.PREFIX+'bad':{'configuration':{}}})
    assert client.get('/api/rules').status_code==409
