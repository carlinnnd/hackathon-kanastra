import os
import sys
import pytest

# Adiciona Codex/antecipe ao PYTHONPATH para testes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


@pytest.fixture(autouse=True)
def cadastro_fixture_explicito(monkeypatch):
    """Casos legados usam quatro CNPJs sintéticos, sem depender do CSV real do usuário."""
    from backend.config import settings
    monkeypatch.setattr(settings, "CADASTRO_MOCK_PATH", "")
    # Casos historicos continuam reproduziveis; testes de virada substituem este relogio.
    from backend.domain import calendar
    from datetime import date
    monkeypatch.setattr(calendar, "data_atual", lambda: date(2026, 10, 22))
