"""
Configurações da aplicação Antecipe.
Carrega variáveis de ambiente com validação estrita via Pydantic Settings.
Sem token default inseguro; banco padrão isolado em Codex/antecipe.
Padrão absoluto de cadastro: False (conservador, sem demo implícito).
"""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = (BASE_DIR / "antecipe.db").as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_PATH}"
    DATA_BASE: str = "2026-10-22"
    
    # Sem segredo default; mutações administrativas retornam 503 se não configurado
    ADMIN_TOKEN: Optional[str] = None

    MAX_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100MB
    ESTOQUE_CSV_PATH: str = "estoque_antecipe_100k/estoque_antecipe.csv"
    VALIDADORES_JSON_PATH: str = "validadores_antecipe.json"

    # Modo DEMO DESATIVADO por padrão (conservador estrito: qualquer sacado retorna NAO_VERIFICADA)
    # Apenas habilitado se explicitamente configurado ENABLE_DEMO_CADASTRO=true no ambiente
    ENABLE_DEMO_CADASTRO: bool = False

    # Modo de demonstração pública efêmera (ex: Vercel serverless)
    PUBLIC_DEMO_MODE: bool = False

    LOG_LEVEL: str = "INFO"


settings = Settings()
