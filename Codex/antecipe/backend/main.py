"""
Aplicação Principal FastAPI Antecipe.
Configura middlewares (CORS, Safe Logging com template allowlist, tratamento de exceções sem vazamento,
proteção de tamanho HTTP, e inclusão de rotas REST e WebSocket Bulk Stream).
"""
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.routes import router
from .api.bulk_routes import bulk_router
from .api.policy_routes import router as policy_router
from .infrastructure.database.session import Base, engine, SessionLocal
from .application.importer import inicializar_fundos_e_regras, importar_estoque_csv, seed_carteira_base_sintetica
from .config import settings
from .logger import logger

from .api.auth_routes import router as auth_router
from .api.auth_routes import verify_access
from starlette.concurrency import run_in_threadpool


def init_db():
    """Inicialização explícita e controlada do esquema de banco."""
    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan gerenciado do FastAPI."""
    init_db()
    db = SessionLocal()
    try:
        fundo = inicializar_fundos_e_regras(db, settings.VALIDADORES_JSON_PATH)
        seed_carteira_base_sintetica(db, fundo.id)
        logger.info(
            "Aplicacao Antecipe inicializada com sucesso",
            extra={
                "event": "APP_STARTUP",
                "status_code": 200,
            }
        )
    finally:
        db.close()
    yield


app = FastAPI(
    title="Antecipe API",
    description="Plataforma de Antecipação de Recebíveis para FIDCs",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS aberto para integração com frontend React local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        content = {"detail": detail}
    else:
        content = {"detail": {"codigo": f"HTTP_{exc.status_code}", "mensagem": str(detail)}}

    # Preserva rigorosamente o cabeçalho 'Allow' em respostas HTTP 405 Method Not Allowed
    headers = dict(exc.headers) if exc.headers else {}
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Tratamento seguro de RequestValidationError:
    NUNCA ecoa o campo 'input' bruto com dados de clientes ou tokens acidentais.
    """
    erros_sanitizados = []
    for err in exc.errors():
        loc_str = " -> ".join(str(loc) for loc in err.get("loc", []))
        erros_sanitizados.append({
            "campo": loc_str,
            "motivo": err.get("msg", "Valor inválido"),
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "codigo": "ERRO_VALIDACAO_PAYLOAD",
                "mensagem": "Dados da requisição malformados ou incompletos.",
                "campos_invalidos": erros_sanitizados
            }
        }
    )


@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):
    """
    Proteção antecipada de tamanho de requisição (HTTP stream level):
    Atua tanto em uploads de CSV (/api/simulations) quanto em payloads JSON (/api/receivables/evaluate).
    Verifica Content-Length e conta bytes recebidos do socket em tempo real.
    Se ultrapassar settings.MAX_UPLOAD_SIZE_BYTES, rejeita com HTTP 413 antecipadamente.
    """
    if request.method == "POST" and request.url.path in ("/api/simulations", "/api/receivables/evaluate"):
        codigo_erro = "ARQUIVO_MUITO_GRANDE" if request.url.path == "/api/simulations" else "REQUISICAO_MUITO_GRANDE"
        msg_erro = f"O tamanho da requisição excede o limite máximo permitido de {settings.MAX_UPLOAD_SIZE_BYTES} bytes."

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.MAX_UPLOAD_SIZE_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": {"codigo": codigo_erro, "mensagem": msg_erro}}
            )

        bytes_received = 0
        original_receive = request.receive

        async def limited_receive():
            nonlocal bytes_received
            message = await original_receive()
            if message.get("type") == "http.request":
                body_chunk = message.get("body", b"")
                bytes_received += len(body_chunk)
                if bytes_received > settings.MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={"codigo": codigo_erro, "mensagem": msg_erro}
                    )
            return message

        request._receive = limited_receive

    return await call_next(request)


@app.middleware("http")
async def safe_logging_middleware(request: Request, call_next):
    """
    Safe JSON Logging Middleware:
    Usa TEMPLATE de rota allowlist (request.scope.get('route').path) para rotas válidas,
    e '/unmatched_route' para 404s/rotas não mapeadas.
    Garante vazamento ZERO de nomes, CPFs ou tokens na URL.
    """
    start_time = time.time()
    try:
        if request.url.path.startswith('/api/') and not request.url.path.startswith('/api/auth/') and request.url.path != '/api/health':
            try:
                await run_in_threadpool(verify_access, request)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            logged_path = route.path
        elif response.status_code == 404:
            logged_path = "/unmatched_route"
        else:
            logged_path = "/unmatched_route"

        logger.info(
            "HTTP request completed",
            extra={
                "event": "HTTP_REQUEST",
                "method": request.method,
                "path": logged_path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )
        return response
    except (StarletteHTTPException, HTTPException):
        raise
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "HTTP request failed with unhandled exception",
            extra={
                "event": "HTTP_ERROR",
                "method": request.method,
                "path": "/unmatched_route",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error_code": "INTERNAL_SERVER_ERROR",
            }
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": {"codigo": "ERRO_INTERNO", "mensagem": "Ocorreu um erro interno no servidor durante o processamento."}}
        )


app.include_router(router)
app.include_router(bulk_router)
if auth_router is not None:
    app.include_router(auth_router)

app.include_router(policy_router)


@app.get("/video_fundo_login.mp4")
def serve_login_background_video():
    from fastapi.responses import FileResponse
    repo_root = Path(__file__).resolve().parents[3]
    codex_root = Path(__file__).resolve().parents[1]
    candidates = [
        repo_root / "public" / "video_fundo_login.mp4",
        repo_root / "video_fundo_login.mp4",
        codex_root / "public" / "video_fundo_login.mp4",
        codex_root / "frontend" / "public" / "video_fundo_login.mp4",
    ]
    for cand in candidates:
        if cand.is_file():
            return FileResponse(str(cand), media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Vídeo não encontrado")
