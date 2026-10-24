"""Políticas pessoais persistidas no Auth0, nunca no estado global do fundo."""
import json
import os
import time
import uuid
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from . import auth_routes as auth
from ..domain import calendar
from ..domain.engine import carregar_configuracao
from ..infrastructure.repositories.rules_repository import calcular_hash_config

router = APIRouter(prefix='/api/policies', tags=['Políticas pessoais'])
PREFIX = 'antecipe_policy_'
ACTIVE = 'antecipe_active_policy'
_token_cache = {'key': None, 'token': '', 'expires': 0}


def identity(request):
    token = request.cookies.get(auth.COOKIE)
    header = request.headers.get('authorization', '')
    if not token and header.startswith('Bearer '):
        token = header[7:]
    if not token:
        auth.fail('SESSAO_AUSENTE', 'Entre para acessar suas políticas.')
    return auth.profile(auth.config(), token)['id']


def management(subject, patch=None):
    cfg = auth.config()
    client = os.environ.get('AUTH0_MANAGEMENT_API_CLIENT_ID', '')
    secret = os.environ.get('AUTH0_MANAGEMENT_API_CLIENT_SECRET', '')
    if not client or not secret:
        auth.fail('POLITICAS_INDISPONIVEIS', 'O armazenamento de políticas da sua conta não está configurado.', 503)
    key = (cfg['domain'], client, secret)
    if _token_cache['key'] != key or time.monotonic() >= _token_cache['expires']:
        tokens = auth.provider(cfg, 'oauth/token', {'grant_type': 'client_credentials',
            'client_id': client, 'client_secret': secret, 'audience': f"https://{cfg['domain']}/api/v2/"})
        token = tokens.get('access_token')
        if not token:
            auth.fail('POLITICAS_INDISPONIVEIS', 'Não foi possível acessar suas políticas salvas.', 503)
        _token_cache.update(key=key, token=token, expires=time.monotonic() + max(1, min(int(tokens.get('expires_in', 60)), 3600)-30))
    url = f"https://{cfg['domain']}/api/v2/users/{urllib.parse.quote(subject, safe='')}"
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + _token_cache['token'], 'Content-Type': 'application/json'},
        data=json.dumps({'app_metadata': patch}).encode() if patch is not None else None,
        method='PATCH' if patch is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response).get('app_metadata', {})
    except (OSError, ValueError):
        auth.fail('POLITICAS_INDISPONIVEIS', 'Não foi possível ler ou salvar suas políticas. Tente novamente; se persistir, revise as permissões do armazenamento.', 503)


def policies(metadata):
    return sorted([dict(value, id=key[len(PREFIX):], is_active=metadata.get(ACTIVE) == key[len(PREFIX):])
        for key, value in metadata.items() if key.startswith(PREFIX) and isinstance(value, dict)],
        key=lambda item: item.get('created_at', ''), reverse=True)


def active_configuration(request):
    # Chamadas anônimas mantêm o contrato público. Contas autenticadas usam somente seu perfil.
    if not request.cookies.get(auth.COOKIE) and not request.headers.get('authorization'):
        return None
    if not os.environ.get('AUTH0_MANAGEMENT_API_CLIENT_ID'):
        return None
    metadata = management(identity(request))
    selected = metadata.get(ACTIVE)
    if not selected:
        return None
    record = metadata.get(PREFIX + selected)
    if not isinstance(record, dict) or not isinstance(record.get('configuration'), dict):
        auth.fail('POLITICA_INVALIDA', 'Selecione novamente uma política da sua conta.', 409)
    carregar_configuracao(record['configuration'], calendar.data_atual())
    return record['configuration']


@router.get('')
def list_policies(request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return policies(management(identity(request)))


class CreatePolicy(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    configuration: dict


@router.post('')
def save_policy(payload: CreatePolicy, request: Request, response: Response):
    auth.same_origin(request)
    subject = identity(request)
    name = payload.name.strip()
    if not name or len(json.dumps(payload.configuration).encode()) > 12000:
        auth.fail('POLITICA_INVALIDA', 'Informe um nome e uma configuração válida de até 12 KB.', 422)
    try:
        carregar_configuracao(payload.configuration, calendar.data_atual())
    except (ValueError, KeyError, TypeError):
        auth.fail('POLITICA_INVALIDA', 'Revise os parâmetros da política antes de salvar.', 422)
    if len(policies(management(subject))) >= 20:
        auth.fail('LIMITE_POLITICAS', 'Sua conta atingiu o limite de 20 políticas salvas.', 409)
    policy_id = uuid.uuid4().hex
    record = {'name': name, 'configuration': payload.configuration,
        'configuration_hash': calcular_hash_config(payload.configuration), 'created_at': datetime.now(timezone.utc).isoformat()}
    # Cada opção é uma chave independente: salvar em outra aba não sobrescreve opções anteriores.
    management(subject, {PREFIX + policy_id: record, ACTIVE: policy_id})
    response.headers['Cache-Control'] = 'no-store'
    return dict(record, id=policy_id, is_active=True)


@router.post('/{policy_id}/activate')
def activate_policy(policy_id: str, request: Request, response: Response):
    auth.same_origin(request)
    subject = identity(request)
    metadata = management(subject)
    if policy_id != 'default' and PREFIX + policy_id not in metadata:
        auth.fail('POLITICA_NAO_ENCONTRADA', 'Política não encontrada na sua conta.', 404)
    management(subject, {ACTIVE: None if policy_id == 'default' else policy_id})
    response.headers['Cache-Control'] = 'no-store'
    return {'id': policy_id}
