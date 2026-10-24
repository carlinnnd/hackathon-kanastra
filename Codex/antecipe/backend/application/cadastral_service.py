"""
Serviço e mapa de Situação Cadastral.
Regra estrita:
- Padrão conservador absoluto: NAO_VERIFICADA.
- Apenas se ENABLE_DEMO_CADASTRO=True em variáveis de ambiente, consulta mapa restrito
  de CNPJs sintéticos conhecidos de demonstração.
- NUNCA assume 'ATIVA' para qualquer CNPJ válido ou presente no estoque.
"""
import csv
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional
from ..config import settings
from ..domain.models import SituacaoCadastral
from ..domain.cnpj import normalizar_cnpj, validar_cnpj

# Mapa sintético restrito de empresas de demonstração e testes conhecidos
DEMO_CADASTRO_SINTETICO: Dict[str, SituacaoCadastral] = {
    # CNPJ normalizado -> Situação
    "04252011000110": SituacaoCadastral.ATIVA,          # COMERCIAL ALPHA LTDA
    "73410326000122": SituacaoCadastral.ATIVA,          # SERVICOS BETA LTDA
    "11222333000181": SituacaoCadastral.ATIVA,          # INDUSTRIA BRASIL SA
    "33000167000101": SituacaoCadastral.INATIVA,        # EMPRESA INATIVA SA
}


@lru_cache(maxsize=4)
def _ler_mock(path: str, mtime: int, size: int):
    raw = Path(path).read_bytes()
    mapa = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        if reader.fieldnames != ["DOC", "SITUACAO_CADASTRAL"]:
            raise ValueError("Schema cadastral inválido")
        for row in reader:
            ok, doc = normalizar_cnpj(row.get("DOC"))
            situacao = (row.get("SITUACAO_CADASTRAL") or "").strip().upper()
            if not ok or not validar_cnpj(doc) or situacao not in {
                "ATIVA", "INATIVA", "INAPTA", "SUSPENSA", "BAIXADA", "NULA", "NAO_VERIFICADA"
            }:
                raise ValueError("Registro cadastral inválido")
            if doc in mapa and mapa[doc] != situacao:
                raise ValueError("Conflito cadastral")
            mapa[doc] = situacao
    return mapa, "SIMULADO_CSV_SHA256_" + hashlib.sha256(raw).hexdigest()


def carregar_cadastro():
    """Snapshot por simulação. Nenhuma situação é inferida por presença no estoque."""
    if not settings.ENABLE_DEMO_CADASTRO:
        return {}, "NAO_VERIFICADA_PADRAO"
    if not settings.CADASTRO_MOCK_PATH:
        # Fixture mínimo selecionado explicitamente por testes/demonstrações locais.
        return {k: v.value for k, v in DEMO_CADASTRO_SINTETICO.items()}, "SIMULADO_DEMO"
    path = Path(settings.CADASTRO_MOCK_PATH)
    try:
        stat = path.stat()
        return _ler_mock(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        return {}, "MOCK_INDISPONIVEL"
    except (OSError, UnicodeError, ValueError, csv.Error):
        return {}, "MOCK_INVALIDO_OU_INDISPONIVEL"


def obter_situacao_cadastral(doc_sacado_normalizado: str) -> str:
    """
    Retorna a situação cadastral do sacado.
    Se o modo DEMO estiver desativado ou o CNPJ não pertencer ao fixture sintético,
    retorna impreterivelmente NAO_VERIFICADA.
    """
    mapa, _ = carregar_cadastro()
    return mapa.get(doc_sacado_normalizado, SituacaoCadastral.NAO_VERIFICADA.value)


def obter_mapa_cadastral_para_lote(docs_sacados: set) -> Dict[str, str]:
    """Retorna dict com documento -> situacao.value para alimentar o motor."""
    mapa, _ = carregar_cadastro()
    return {doc: mapa.get(doc, SituacaoCadastral.NAO_VERIFICADA.value) for doc in docs_sacados}
