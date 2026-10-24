"""
Adaptador FastAPI para a integração oficial Vercel Marketplace Auth0
(https://vercel.com/marketplace/auth0).

Lê as variáveis de ambiente da Vercel (ou do arquivo local `login/.env` / `.env` ignorado pelo Git):
- AUTH0_DOMAIN ou AUTH0_ISSUER_BASE_URL
- AUTH0_CLIENT_ID
- AUTH0_CLIENT_SECRET
"""
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

auth_router = APIRouter(prefix="/api/auth", tags=["Auth0 Vercel Login"])
router = auth_router

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


class AuthCodeExchangeRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None
    redirectUri: Optional[str] = None
    code_verifier: Optional[str] = None
    codeVerifier: Optional[str] = None


def _load_local_env_file() -> dict:
    """Lê variáveis de `login/.env` ou `.env` local caso não estejam no os.environ."""
    values = {}
    root_dir = Path(__file__).resolve().parent.parent
    candidates = [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent / ".env.local",
        root_dir / ".env",
        root_dir / ".env.local",
    ]
    for env_path in candidates:
        if env_path.is_file():
            try:
                for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    clean_val = val.strip().strip('"').strip("'")
                    if clean_val and not clean_val.startswith("*"):
                        values.setdefault(key.strip(), clean_val)
            except Exception:
                pass
    return values


def _get_env_var(name: str, local_env: dict) -> str:
    return (os.environ.get(name) or local_env.get(name) or "").strip().strip('"').strip("'")


class CredentialsLoginRequest(BaseModel):
    email: str
    password: str
    cargo: Optional[str] = "Analista de Risco FIDC"
    name: Optional[str] = None
    mode: Optional[str] = "login"


@auth_router.post("/login")
def login_with_credentials(payload: CredentialsLoginRequest):
    """
    Autentica usuário por e-mail válido e senha (sem registrar PII em logs),
    gerando digest SHA-256 determinístico para sessão autenticada no portal.
    Aceita qualquer endereço de e-mail válido conforme especificação.
    """
    clean_email = (payload.email or "").strip().lower()
    if not EMAIL_REGEX.match(clean_email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "codigo": "EMAIL_INVALIDO",
                "mensagem": "Informe um endereço de e-mail válido (ex.: nome@dominio.com).",
            },
        )
    if not payload.password or len(payload.password.strip()) < 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "codigo": "SENHA_INVALIDA",
                "mensagem": "A senha deve conter pelo menos 4 caracteres.",
            },
        )

    digest = hashlib.sha256(f"{clean_email}:{payload.password}".encode("utf-8")).hexdigest()
    local_part = clean_email.split("@")[0].replace(".", " ").replace("_", " ").replace("-", " ")
    derived_name = (payload.name or "").strip() or " ".join(
        p.capitalize() for p in local_part.split() if p
    ) or "Operador FIDC"

    return {
        "id": f"usr-{digest[:12]}",
        "nome": derived_name,
        "name": derived_name,
        "email": clean_email,
        "cargo": (payload.cargo or "Analista de Risco FIDC").strip(),
        "organizacao": "Kanastra • ANTECIPE FIDC",
        "token": f"kanastra-sha256-{digest[:32]}",
        "provider": "credentials",
    }


def _get_vercel_auth0_settings() -> dict:
    local_env = _load_local_env_file()
    raw_domain = (
        _get_env_var("AUTH0_DOMAIN", local_env)
        or _get_env_var("AUTH0_ISSUER_BASE_URL", local_env)
        or _get_env_var("NEXT_PUBLIC_AUTH0_DOMAIN", local_env)
        or _get_env_var("VITE_AUTH0_DOMAIN", local_env)
    )
    domain = raw_domain.replace("https://", "").replace("http://", "").rstrip("/")
    client_id = (
        _get_env_var("AUTH0_CLIENT_ID", local_env)
        or _get_env_var("NEXT_PUBLIC_AUTH0_CLIENT_ID", local_env)
        or _get_env_var("VITE_AUTH0_CLIENT_ID", local_env)
    )
    client_secret = _get_env_var("AUTH0_CLIENT_SECRET", local_env)

    configured = bool(domain and client_id)
    return {
        "configured": configured,
        "enabled": configured,
        "domain": domain,
        "client_id": client_id,
        "has_client_secret": bool(client_secret),
        "client_secret": client_secret,
    }


@auth_router.get("/config")
def get_public_auth0_config():
    """
    Retorna apenas os parâmetros públicos (domain e clientId) injetados pela
    integração Vercel Marketplace Auth0 ou pelo arquivo local `login/.env`.
    """
    cfg = _get_vercel_auth0_settings()
    return {
        "configured": cfg["configured"],
        "enabled": cfg["enabled"],
        "domain": cfg["domain"] if cfg["configured"] else None,
        "clientId": cfg["client_id"] if cfg["configured"] else None,
        "useServerExchange": cfg["has_client_secret"],
    }


@auth_router.post("/exchange")
def exchange_auth0_code(payload: AuthCodeExchangeRequest):
    """
    Troca o authorization_code pelo perfil do usuário no Auth0 no backend.
    """
    cfg = _get_vercel_auth0_settings()
    if not cfg["configured"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "codigo": "AUTH0_NAO_CONFIGURADO",
                "mensagem": "Integração Auth0 ainda não configurada nas variáveis de ambiente.",
            },
        )

    redirect_uri = payload.redirect_uri or payload.redirectUri or ""
    code_verifier = payload.code_verifier or payload.codeVerifier

    token_body = {
        "grant_type": "authorization_code",
        "client_id": cfg["client_id"],
        "code": payload.code,
        "redirect_uri": redirect_uri,
    }
    if cfg["client_secret"]:
        token_body["client_secret"] = cfg["client_secret"]
    if code_verifier:
        token_body["code_verifier"] = code_verifier

    token_req = urllib.request.Request(
        url=f"https://{cfg['domain']}/oauth/token",
        data=json.dumps(token_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(token_req, timeout=10) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "codigo": "AUTH0_CODE_INVALIDO",
                "mensagem": "Não foi possível validar o código de autorização com o Auth0.",
            },
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "codigo": "AUTH0_INDISPONIVEL",
                "mensagem": "Falha de comunicação com o provedor Auth0.",
            },
        )

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "codigo": "AUTH0_TOKEN_AUSENTE",
                "mensagem": "Provedor Auth0 não retornou token de acesso.",
            },
        )

    userinfo_req = urllib.request.Request(
        url=f"https://{cfg['domain']}/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(userinfo_req, timeout=10) as user_resp:
            profile = json.loads(user_resp.read().decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "codigo": "AUTH0_USERINFO_ERRO",
                "mensagem": "Não foi possível obter os dados do perfil no Auth0.",
            },
        )

    sub = str(profile.get("sub") or "")
    user_payload = {
        "id": sub or "auth0-user",
        "name": profile.get("name") or profile.get("email") or "Empresário Cedente",
        "email": profile.get("email") or "cedente@empresa.com.br",
        "pictureUrl": profile.get("picture"),
        "provider": "google" if "google" in sub.lower() else "auth0",
    }
    return {
        "ok": True,
        "user": user_payload,
        **user_payload,
    }
