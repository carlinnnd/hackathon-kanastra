"""Entrypoint ASGI da demonstração pública na Vercel."""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ROOT_DIR / "Codex" / "antecipe"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(PROJECT_DIR))

from backend.vercel_app import app  # noqa: E402,F401
from login.vercel_auth_helper import router as vercel_auth_router  # noqa: E402

if not any( getattr(r, "path", None) == "/api/auth/config" for r in app.routes ):
    app.include_router(vercel_auth_router)

