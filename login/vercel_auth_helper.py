"""
Adaptador FastAPI para a integração oficial Vercel Marketplace Auth0
(https://vercel.com/marketplace/auth0).

Por que este arquivo existe na pasta `login/`:
1. Quando você instala o Auth0 pelo Marketplace da Vercel, a Vercel cria automaticamente
   as variáveis de ambiente:
   - AUTH0_DOMAIN ou AUTH0_ISSUER_BASE_URL
   - AUTH0_CLIENT_ID
   - AUTH0_CLIENT_SECRET (quando provisionado como Regular Web Application pela Vercel)
2. Este router lê essas variáveis diretamente do ambiente da Vercel (sem precisar renomear para VITE_*)
   e faz a troca segura do código OAuth2 (code -> userinfo) no servidor usando apenas a biblioteca
   padrão do Python (urllib), sem expor o AUTH0_CLIENT_SECRET no navegador e sem registrar PII em logs.

Como plugar no FastAPI (`Codex/antecipe/backend/main.py`):
    from login.vercel_auth_helper import auth_router
    app.include_router(auth_router)
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

auth_router = APIRouter(prefix="/api/auth", tags=["Auth0 Vercel Login"])


class AuthCodeExchangeRequest(BaseModel):
    code: str
    redirect_uri: str
    code_verifier: Optional[str] = None


def _get_vercel_auth0_settings() -> dict:
    raw_domain = (
        os.environ.get("AUTH0_DOMAIN")
        or os.environ.get("AUTH0_ISSUER_BASE_URL")
        or os.environ.get("NEXT_PUBLIC_AUTH0_DOMAIN")
        or os.environ.get("VITE_AUTH0_DOMAIN")
        or ""
    )
    domain = raw_domain.strip().replace("https://", "").replace("http://", "").rstrip("/")
    client_id = (
        os.environ.get("AUTH0_CLIENT_ID")
        or os.environ.get("NEXT_PUBLIC_AUTH0_CLIENT_ID")
        or os.environ.get("VITE_AUTH0_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (os.environ.get("AUTH0_CLIENT_SECRET") or "").strip()

    return {
        "configured": bool(domain and client_id),
        "domain": domain,
        "client_id": client_id,
        "has_client_secret": bool(client_secret),
        "client_secret": client_secret,
    }


@auth_router.get("/config")
def get_public_auth0_config():
    """
    Retorna apenas os parâmetros públicos (domain e clientId) injetados pela
    integração Vercel Marketplace Auth0, permitindo que o Frontend funcione
    automaticamente sem precisar duplicar variáveis com prefixo VITE_.
    """
    cfg = _get_vercel_auth0_settings()
    return {
        "configured": cfg["configured"],
        "domain": cfg["domain"] if cfg["configured"] else None,
        "clientId": cfg["client_id"] if cfg["configured"] else None,
    }


@auth_router.post("/exchange")
def exchange_auth0_code(payload: AuthCodeExchangeRequest):
    """
    Troca o authorization_code pelo perfil do usuário no Auth0.
    Suporta tanto aplicações 'Regular Web App' criadas automaticamente pelo Marketplace
    da Vercel (que exigem AUTH0_CLIENT_SECRET) quanto 'Single Page Applications' (PKCE).
    """
    cfg = _get_vercel_auth0_settings()
    if not cfg["configured"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "codigo": "AUTH0_NAO_CONFIGURADO",
                "mensagem": "Integração Auth0 ainda não configurada nas variáveis de ambiente da Vercel.",
            },
        )

    token_body = {
        "grant_type": "authorization_code",
        "client_id": cfg["client_id"],
        "code": payload.code,
        "redirect_uri": payload.redirect_uri,
    }
    if cfg["client_secret"]:
        token_body["client_secret"] = cfg["client_secret"]
    if payload.code_verifier:
        token_body["code_verifier"] = payload.code_verifier

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
    return {
        "id": sub or "auth0-user",
        "name": profile.get("name") or profile.get("email") or "Empresário Cedente",
        "email": profile.get("email") or "cedente@empresa.com.br",
        "pictureUrl": profile.get("picture"),
        "provider": "google" if "google" in sub.lower() else "auth0",
    }

