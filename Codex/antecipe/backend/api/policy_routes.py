"""Políticas pessoais persistidas no Auth0, nunca no estado global do fundo."""
import json
import uuid
import urllib.parse
import urllib.error
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


def identity(request):
    token = request.cookies.get(auth.COOKIE)
    header = request.headers.get('authorization', '')
    if not token and header.startswith('Bearer '):
        token = header[7:]
    if not token:
        auth.fail('SESSAO_AUSENTE', 'Entre para acessar suas políticas.')
    return auth.profile(auth.config(), token)['id']


def management(subject, patch=None, token=None):
    """Token do próprio usuário: acesso restrito pelo Auth0 ao seu perfil.

    Preferências de simulação ficam em user_metadata, sem papéis/permissões.
    app_metadata anterior é somente lido para preservar opções legadas.
    """
    if not token:
        auth.fail('SESSAO_AUSENTE', 'Entre para acessar suas políticas.')
    cfg = auth.config()
    url = f"https://{cfg['domain']}/api/v2/users/{urllib.parse.quote(subject, safe='')}"
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        data=json.dumps({'user_metadata': patch}).encode() if patch is not None else None,
        method='PATCH' if patch is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.load(response)
        if not isinstance(data, dict):
            raise ValueError('Invalid profile response')
        legacy = data.get('app_metadata') or {}
        personal = data.get('user_metadata') or {}
        return {**legacy, **personal}
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            auth.fail('POLITICAS_REAUTENTICACAO_NECESSARIA',
                'Sua sessão precisa de autorização para suas políticas. Saia e entre novamente; o Auth0 solicitará acesso somente ao seu perfil.', 401)
        auth.fail('POLITICAS_INDISPONIVEIS', 'O serviço de políticas está indisponível. Tente novamente.', 503)
    except (OSError, ValueError, TypeError):
        auth.fail('POLITICAS_INDISPONIVEIS', 'Não foi possível ler ou salvar suas políticas. Tente novamente.', 503)


def session_token(request):
    token = request.cookies.get(auth.COOKIE)
    authorization = request.headers.get('authorization', '')
    if not token and authorization.startswith('Bearer '):
        token = authorization[7:]
    return token


def policies(metadata):
    return sorted([dict(value, id=key[len(PREFIX):], is_active=metadata.get(ACTIVE) == key[len(PREFIX):])
        for key, value in metadata.items() if key.startswith(PREFIX) and isinstance(value, dict)],
        key=lambda item: item.get('created_at', ''), reverse=True)


def active_configuration(request):
    # Chamadas anônimas mantêm o contrato público. Contas autenticadas usam somente seu perfil.
    if not request.cookies.get(auth.COOKIE) and not request.headers.get('authorization'):
        return None
    metadata = management(identity(request), token=session_token(request))
    selected = metadata.get(ACTIVE)
    if not selected or selected == 'default':
        return None
    record = metadata.get(PREFIX + selected)
    if not isinstance(record, dict) or not isinstance(record.get('configuration'), dict):
        auth.fail('POLITICA_INVALIDA', 'Selecione novamente uma política da sua conta.', 409)
    try:
        carregar_configuracao(record['configuration'], calendar.data_atual())
    except (ValueError, KeyError, TypeError):
        auth.fail('POLITICA_INVALIDA', 'Revise a política salva antes de analisar um lote.', 409)
    return record['configuration']


@router.get('')
def list_policies(request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return policies(management(identity(request), token=session_token(request)))


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
    if len(policies(management(subject, token=session_token(request)))) >= 20:
        auth.fail('LIMITE_POLITICAS', 'Sua conta atingiu o limite de 20 políticas salvas.', 409)
    policy_id = uuid.uuid4().hex
    record = {'name': name, 'configuration': payload.configuration,
        'configuration_hash': calcular_hash_config(payload.configuration), 'created_at': datetime.now(timezone.utc).isoformat()}
    # Cada opção é uma chave independente: salvar em outra aba não sobrescreve opções anteriores.
    management(subject, {PREFIX + policy_id: record, ACTIVE: policy_id}, token=session_token(request))
    response.headers['Cache-Control'] = 'no-store'
    return dict(record, id=policy_id, is_active=True)


@router.post('/{policy_id}/activate')
def activate_policy(policy_id: str, request: Request, response: Response):
    auth.same_origin(request)
    subject = identity(request)
    metadata = management(subject, token=session_token(request))
    if policy_id != 'default' and PREFIX + policy_id not in metadata:
        auth.fail('POLITICA_NAO_ENCONTRADA', 'Política não encontrada na sua conta.', 404)
    management(subject, {ACTIVE: policy_id}, token=session_token(request))
    response.headers['Cache-Control'] = 'no-store'
    return {'id': policy_id}
