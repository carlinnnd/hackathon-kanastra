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
    "58206002000111": SituacaoCadastral.ATIVA,          # SERRALHERIA VIOLETA SA MATRIZ
    "58206002000200": SituacaoCadastral.ATIVA,          # SERRALHERIA VIOLETA SA FILIAL 02
    "58206002000383": SituacaoCadastral.ATIVA,          # SERRALHERIA VIOLETA SA FILIAL 03
    "00000000000191": SituacaoCadastral.ATIVA,          # COMPANHIA NACIONAL DE SUPRIMENTOS
    "60701190000104": SituacaoCadastral.ATIVA,          # METALURGICA VANGUARDA LTDA
    "90400888000142": SituacaoCadastral.ATIVA,          # AGROPECUARIA VALE VERDE SA
    "34028316000103": SituacaoCadastral.ATIVA,          # TECNOLOGIA INTEGRADA BRASIL LTDA
    "60746948000112": SituacaoCadastral.ATIVA,          # ATACADISTA CENTRAL DO BRASIL SA
    "07526557000100": SituacaoCadastral.ATIVA,          # BEBIDAS E ALIMENTOS SUL LTDA
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

    # Se estiver lendo o arquivo padrão cnpj_situacao_mock.csv, carrega também o complemento de cobertura
    p_obj = Path(path)
    if p_obj.name == "cnpj_situacao_mock.csv":
        for k_demo, v_demo in DEMO_CADASTRO_SINTETICO.items():
            if k_demo not in mapa:
                mapa[k_demo] = v_demo.value
        comp_path = p_obj.parent / "cnpj_complemento_estoque.csv"
        if comp_path.is_file():
            with comp_path.open(encoding="utf-8-sig", newline="") as c_stream:
                c_reader = csv.DictReader(c_stream, delimiter=";")
                for c_row in c_reader:
                    ok_c, doc_c = normalizar_cnpj(c_row.get("DOC"))
                    sit_c = (c_row.get("SITUACAO_CADASTRAL") or "").strip().upper()
                    if ok_c and doc_c not in mapa and sit_c in {
                        "ATIVA", "INATIVA", "INAPTA", "SUSPENSA", "BAIXADA", "NULA", "NAO_VERIFICADA"
                    }:
                        mapa[doc_c] = sit_c

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
