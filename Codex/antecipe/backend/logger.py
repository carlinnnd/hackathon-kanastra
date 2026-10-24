"""
Módulo de logging estruturado seguro (Safe JSON Logs).
Garante conformidade com o Critério 5.2.4:
- Formato JSON em linha única por registro.
- Campos permitidos explícitos (allowlist).
- NUNCA registra linhas de CSV, dados financeiros brutos, CNPJs, nomes de sacados/cedentes,
  payloads brutos ou credenciais/tokens.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


ALLOWED_LOG_FIELDS = {
    "timestamp",
    "level",
    "event",
    "message",
    "simulation_id",
    "rule_version_id",
    "total_itens",
    "aprovados",
    "recusados",
    "duration_ms",
    "status_code",
    "method",
    "path",
    "error_code",
}


class SafeJsonFormatter(logging.Formatter):
    """
    Formatador estrito que emite logs como JSON e filtra qualquer dado fora da allowlist.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Copia extras permitidos
        for key, val in record.__dict__.items():
            if key in ALLOWED_LOG_FIELDS and key not in log_obj:
                log_obj[key] = val

        return json.dumps(log_obj, ensure_ascii=False)


def setup_logger(name: str = "antecipe", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    # Evita múltiplos handlers ao recarregar
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(SafeJsonFormatter())
        logger.addHandler(handler)

    return logger


logger = setup_logger()
