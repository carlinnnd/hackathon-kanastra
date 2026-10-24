"""Adaptador Auth0 do portal; tokens permanecem em cookie HttpOnly no servidor."""
import hashlib
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
from ..logger import logger

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
    if not origin:
        return
    origin_clean = origin.rstrip('/')
    scheme = request.headers.get('x-forwarded-proto') or request.url.scheme
    expected = f"{scheme}://{request.url.netloc}"
    direct = f"{request.url.scheme}://{request.url.netloc}"
    if origin_clean != expected and origin_clean != direct:
        try:
            origin_netloc = urllib.parse.urlsplit(origin).netloc
            if origin_netloc and origin_netloc == request.url.netloc:
                return
        except Exception:
            pass
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
    except urllib.error.HTTPError as exc:
        try:
            rejection = json.loads(exc.read(8192))
        except (ValueError, OSError):
            rejection = {}
        error = rejection.get('error') if isinstance(rejection, dict) else None
        management = body is not None and body.get('grant_type') == 'client_credentials'
        if management:
            code, message, status = ('POLITICAS_AUTORIZACAO_RECUSADA',
                'O Auth0 recusou o serviço de políticas. Revise a aplicação Machine-to-Machine e autorize a Management API com read:users e update:users_app_metadata.', 503)
        elif exc.code == 429:
            code, message, status = 'AUTH0_LIMITE_CONSULTAS', 'O Auth0 limitou as consultas. Aguarde e tente novamente.', 503
        elif path == 'userinfo':
            code, message, status = 'SESSAO_EXPIRADA', 'Sua sessão não pôde ser confirmada. Entre novamente.', 401
        elif error == 'unauthorized_client' and path == 'oauth/token':
            code, message, status = ('AUTH0_FLUXO_NAO_AUTORIZADO',
                'A entrada deve ser concluída na página segura do Auth0.', 503)
        elif error in {'invalid_client', 'unauthorized_client'}:
            code, message, status = ('AUTH0_CONFIGURACAO_RECUSADA',
                'O Auth0 recusou a configuração do aplicativo. O administrador deve conferir a credencial, a conexão de usuários e o fluxo de autenticação habilitado.', 503)
        elif path == 'dbconnections/signup':
            code, message, status = ('AUTH0_CADASTRO_RECUSADO',
                'O cadastro não foi concluído. Confira os dados e os requisitos de senha; se já possui uma conta, utilize Entrar.', 422)
        else:
            code, message, status = 'AUTH0_AUTENTICACAO_RECUSADA', 'Não foi possível entrar. Confira seus dados ou recupere o acesso pelo Auth0.', 401
        # Somente códigos internos e status; nunca corpo, descrição, credenciais ou perfil do provedor.
        logger.warning('Auth0 recusou uma operação', extra={'event': 'AUTH0_PROVIDER_REJECTED',
            'error_code': code, 'status_code': exc.code})
        fail(code, message, status)
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
            'clientId': cfg['client_id'] if enabled else None, 'useServerExchange': True,
            'personalPoliciesConfigured': enabled, 'databaseConnection': cfg['connection'] if enabled else None}


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
    mode: str = 'login'
    name: str | None = None
    cargo: str | None = None  # Informação visual não concede autorização.


@router.get('/login')
@router.get('/signup')
@router.get('/register')
def auth_methods_get(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return {'ok': True, 'mensagem': 'Endpoint de autenticação ativo. Utilize POST para entrar ou criar conta.'}


@router.post('/signup')
@router.post('/register')
def signup_alias(payload: LoginRequest, request: Request, response: Response):
    payload.mode = 'signup'
    return login(payload, request, response)


@router.post('/login')
def login(payload: LoginRequest, request: Request, response: Response):
    same_origin(request)
    email = payload.email.strip()
    if "@" not in email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        fail("EMAIL_INVALIDO", "Informe um e-mail válido com @ e domínio.", 422)

    cfg = config()
    if not cfg['domain'] or not cfg['client_id']:
        fail('AUTH0_NAO_CONFIGURADO', 'Configure o Auth0 no servidor para entrar.', 503)

    if payload.mode not in {'login', 'signup'}:
        fail('MODO_LOGIN_INVALIDO', 'Selecione entrar ou criar conta.', 422)
    if payload.mode == 'signup':
        body = {'client_id': cfg['client_id'], 'email': email,
                'password': payload.password, 'connection': cfg['connection']}
        if payload.name:
            body['name'] = payload.name.strip()
        provider(cfg, 'dbconnections/signup', body)
    body = {'grant_type': 'http://auth0.com/oauth/grant-type/password-realm',
            'client_id': cfg['client_id'], 'realm': cfg['connection'], 'username': email,
            'password': payload.password, 'scope': 'openid profile email read:current_user update:current_user_metadata create:current_user_metadata',
            'audience': f"https://{cfg['domain']}/api/v2/"}
    if cfg['client_secret']:
        body['client_secret'] = cfg['client_secret']
    try:
        return establish(cfg, provider(cfg, 'oauth/token', body), request, response)
    except HTTPException as exc:
        if payload.mode == 'signup':
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            raise HTTPException(status_code=409, detail={
                'codigo': 'CONTA_CRIADA_LOGIN_NAO_CONCLUIDO',
                'mensagem': 'Sua conta foi criada no Auth0, mas a entrada não foi concluída. Não repita o cadastro. ' + detail.get('mensagem', 'Entre novamente.'),
                'causa_codigo': detail.get('codigo'),
                'cadastro_criado': True,
            }, headers={'Cache-Control': 'no-store'}) from None
        raise


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
    cfg = config()
    if not (cfg['domain'] and cfg['client_id']) or token.startswith('demo-token-'):
        user_id = token.removeprefix('demo-token-') if token.startswith('demo-token-') else 'demo-local-user'
        return {
            'id': user_id,
            'nome': 'Usuário Demonstração',
            'email': 'demo@antecipe.com.br',
            'cargo': 'Analista de Risco FIDC',
            'organizacao': 'ANTECIPE FIDC',
            'modo_autenticacao': 'local_demo'
        }
    return profile(cfg, token)


@router.post('/logout')
@router.get('/logout')
def logout(request: Request, response: Response):
    same_origin(request)
    scheme = request.headers.get('x-forwarded-proto') or request.url.scheme
    is_secure = scheme == 'https'
    for p in ('/api', '/', ''):
        response.delete_cookie(COOKIE, path=p, samesite='lax', secure=is_secure, httponly=True)
        response.set_cookie(COOKIE, '', max_age=0, expires='Thu, 01 Jan 1970 00:00:00 GMT', path=p, samesite='lax', secure=is_secure, httponly=True)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return {'ok': True}
