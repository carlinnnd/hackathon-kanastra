"""Entrypoint ASGI da demonstração pública na Vercel."""
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent / "Codex" / "antecipe"
sys.path.insert(0, str(PROJECT_DIR))

from backend.vercel_app import app  # noqa: E402,F401
