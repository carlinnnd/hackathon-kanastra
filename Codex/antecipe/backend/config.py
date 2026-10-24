"""
Configurações da aplicação Antecipe.
Carrega variáveis de ambiente com validação estrita via Pydantic Settings.
Suporte a streaming bulk upload até 1 milhão de registros e 512 MiB.
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
    
    # Sem segredo default; mutações administrativas retornam 503 se não configurado
    ADMIN_TOKEN: Optional[str] = None

    # Limite HTTP padrão local (512 MiB para até 1M de registros; Vercel sobrescreve para 4.5MB via env)
    MAX_UPLOAD_SIZE_BYTES: int = 512 * 1024 * 1024  # 512 MiB

    # Parâmetros de transporte WebSocket Stream
    MAX_STREAM_FILE_BYTES: int = 512 * 1024 * 1024  # 512 MiB
    MAX_STREAM_RECORDS: int = 1_000_000
    STREAM_CHUNK_BYTES: int = 256 * 1024  # 256 KiB
    STREAM_WINDOW_BYTES: int = 4 * 1024 * 1024  # 4 MiB

    ESTOQUE_CSV_PATH: str = "estoque_antecipe_100k/estoque_antecipe.csv"
    VALIDADORES_JSON_PATH: str = "validadores_antecipe.json"

    # Modo DEMO DESATIVADO por padrão (conservador estrito: qualquer sacado retorna NAO_VERIFICADA)
    # Apenas habilitado se explicitamente configurado ENABLE_DEMO_CADASTRO=true no ambiente
    ENABLE_DEMO_CADASTRO: bool = False
    CADASTRO_MOCK_PATH: str = str(BASE_DIR / "data" / "cnpj_situacao_mock.csv")

    # Modo de demonstração pública efêmera (ex: Vercel serverless)
    PUBLIC_DEMO_MODE: bool = False

    LOG_LEVEL: str = "INFO"


settings = Settings()
