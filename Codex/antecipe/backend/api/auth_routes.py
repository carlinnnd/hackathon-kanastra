"""Adaptador Auth0 do portal; tokens permanecem em cookie HttpOnly no servidor."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])
COOKIE = "antecipe_auth0_session"


def config():
    project = Path(__file__).resolve().parents[2]
    root = project.parents[1]
    local = {}
    for path in (root / 'login/.env', project / '.env'):
        if path.is_file():
            local.update(dotenv_values(path))
    def get(name, default=''):
        return (os.environ.get(name) or local.get(name) or default).strip()
    domain = get('AUTH0_DOMAIN') or get('AUTH0_ISSUER_BASE_URL')
    domain = domain.removeprefix('https://').rstrip('/')
    if domain and not re.fullmatch(r'[a-zA-Z0-9.-]+', domain):
        raise HTTPException(503, detail={'codigo': 'AUTH0_CONFIG_INVALIDA', 'mensagem': 'Revise a configuração do Auth0 no servidor.'})
    return {'domain': domain, 'client_id': get('AUTH0_CLIENT_ID'),
            'client_secret': get('AUTH0_CLIENT_SECRET'),
            'connection': get('AUTH0_DB_CONNECTION', 'Username-Password-Authentication')}


def fail(code, message, status=401):
    raise HTTPException(status, detail={'codigo': code, 'mensagem': message}, headers={'Cache-Control': 'no-store'})


def same_origin(request):
    origin = request.headers.get('origin')
    expected = f'{request.url.scheme}://{request.url.netloc}'
    if origin and origin.rstrip('/') != expected:
        fail('ORIGEM_INVALIDA', 'Origem da solicitação inválida.', 403)


def provider(cfg, path, body=None, token=None):
    if not cfg['domain'] or not cfg['client_id']:
        fail('AUTH0_NAO_CONFIGURADO', 'Configure o Auth0 no servidor para entrar.', 503)
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f"https://{cfg['domain']}/{path}",
        data=json.dumps(body).encode() if body is not None else None, headers=headers,
        method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError:
        fail('AUTH0_AUTENTICACAO_RECUSADA', 'Não foi possível autenticar no Auth0. Confira as credenciais e a configuração da aplicação.')
    except (OSError, ValueError):
        fail('AUTH0_INDISPONIVEL', 'Auth0 indisponível. Tente novamente.', 502)


def profile(cfg, token):
    data = provider(cfg, 'userinfo', token=token)
    if not isinstance(data.get('sub'), str) or not data['sub']:
        fail('AUTH0_PERFIL_INVALIDO', 'Não foi possível confirmar o perfil no Auth0.')
    return {'id': data['sub'], 'nome': data.get('name') or data.get('email') or 'Usuário',
            'email': data.get('email', ''), 'cargo': 'Operador', 'organizacao': 'ANTECIPE FIDC',
            'modo_autenticacao': 'auth0'}


def verify_access(request):
    # A demonstracao publica continua explicita. Ambientes com Auth0 configurado
    # validam a identidade no provedor, inclusive para conexoes WebSocket.
    cfg = config()
    if settings.PUBLIC_DEMO_MODE or not (cfg['domain'] and cfg['client_id']):
        return
    token = request.cookies.get(COOKIE)
    authorization = request.headers.get('authorization', '')
    if not token and authorization.startswith('Bearer '):
        token = authorization[7:]
    if not token:
        fail('SESSAO_AUSENTE', 'Entre para continuar.')
    profile(cfg, token)


def establish(cfg, tokens, request, response):
    token = tokens.get('access_token')
    if not isinstance(token, str) or not token:
        fail('AUTH0_TOKEN_AUSENTE', 'Auth0 não retornou uma sessão válida.')
    user = profile(cfg, token)
    lifetime = min(max(int(tokens.get('expires_in', 3600)), 1), 86400)
    response.set_cookie(COOKIE, token, max_age=lifetime, httponly=True, secure=request.url.scheme == 'https', samesite='lax', path='/api')
    response.headers['Cache-Control'] = 'no-store'
    return {'ok': True, 'user': user, **user}


@router.get('/config')
def public_config(response: Response):
    cfg = config()
    response.headers['Cache-Control'] = 'no-store'
    enabled = bool(cfg['domain'] and cfg['client_id'])
    return {'configured': enabled, 'enabled': enabled, 'domain': cfg['domain'] if enabled else None,
            'clientId': cfg['client_id'] if enabled else None, 'useServerExchange': True}


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
    mode: str = 'login'
    name: str | None = None
    cargo: str | None = None  # Informação visual não concede autorização.


@router.post('/login')
def login(payload: LoginRequest, request: Request, response: Response):
    same_origin(request)
    cfg = config()
    if payload.mode not in {'login', 'signup'}:
        fail('MODO_LOGIN_INVALIDO', 'Selecione entrar ou criar conta.', 422)
    if payload.mode == 'signup':
        body = {'client_id': cfg['client_id'], 'email': payload.email.strip(),
                'password': payload.password, 'connection': cfg['connection']}
        if payload.name:
            body['name'] = payload.name.strip()
        provider(cfg, 'dbconnections/signup', body)
    body = {'grant_type': 'http://auth0.com/oauth/grant-type/password-realm',
            'client_id': cfg['client_id'], 'realm': cfg['connection'], 'username': payload.email.strip(),
            'password': payload.password, 'scope': 'openid profile email'}
    if cfg['client_secret']:
        body['client_secret'] = cfg['client_secret']
    return establish(cfg, provider(cfg, 'oauth/token', body), request, response)


class ExchangeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=8192)
    redirect_uri: str | None = None
    redirectUri: str | None = None
    code_verifier: str | None = None
    codeVerifier: str | None = None


@router.post('/exchange')
def exchange(payload: ExchangeRequest, request: Request, response: Response):
    same_origin(request)
    redirect = payload.redirect_uri or payload.redirectUri or ''
    parsed = urllib.parse.urlsplit(redirect)
    origin = f'{request.url.scheme}://{request.url.netloc}'
    if redirect != origin + '/auth/callback':
        fail('CALLBACK_INVALIDO', 'Callback de autenticação inválido.', 422)
    if parsed.scheme != 'https' and parsed.hostname not in {'localhost', '127.0.0.1'}:
        fail('CALLBACK_INVALIDO', 'Callback deve usar HTTPS.', 422)
    verifier = payload.code_verifier or payload.codeVerifier or ''
    if not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', verifier):
        fail('PKCE_INVALIDO', 'Reinicie o login para obter uma verificação PKCE válida.', 422)
    cfg = config()
    body = {'grant_type': 'authorization_code', 'client_id': cfg['client_id'],
            'code': payload.code, 'redirect_uri': redirect, 'code_verifier': verifier}
    if cfg['client_secret']:
        body['client_secret'] = cfg['client_secret']
    return establish(cfg, provider(cfg, 'oauth/token', body), request, response)


@router.get('/session')
def session(request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    token = request.cookies.get(COOKIE)
    if not token:
        fail('SESSAO_AUSENTE', 'Entre para continuar.')
    return profile(config(), token)


@router.post('/logout')
def logout(request: Request, response: Response):
    same_origin(request)
    response.delete_cookie(COOKIE, path='/api')
    response.headers['Cache-Control'] = 'no-store'
    return {'ok': True}
