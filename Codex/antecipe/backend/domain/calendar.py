"""Data operacional calculada a cada nova simulacao no fuso de Brasilia."""
from datetime import date, datetime
from zoneinfo import ZoneInfo


def data_atual() -> date:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()
