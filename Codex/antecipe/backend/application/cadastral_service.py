"""
Serviço e mapa de Situação Cadastral.
Regra estrita:
- Padrão conservador absoluto: NAO_VERIFICADA.
- Apenas se ENABLE_DEMO_CADASTRO=True em variáveis de ambiente, consulta mapa restrito
  de CNPJs sintéticos conhecidos de demonstração.
- NUNCA assume 'ATIVA' para qualquer CNPJ válido ou presente no estoque.
"""
from typing import Dict, Optional
from ..config import settings
from ..domain.models import SituacaoCadastral

# Mapa sintético restrito de empresas de demonstração e testes conhecidos
DEMO_CADASTRO_SINTETICO: Dict[str, SituacaoCadastral] = {
    # CNPJ normalizado -> Situação
    "04252011000110": SituacaoCadastral.ATIVA,          # COMERCIAL ALPHA LTDA
    "73410326000122": SituacaoCadastral.ATIVA,          # SERVICOS BETA LTDA
    "11222333000181": SituacaoCadastral.ATIVA,          # INDUSTRIA BRASIL SA
    "33000167000101": SituacaoCadastral.INATIVA,        # EMPRESA INATIVA SA
}


def obter_situacao_cadastral(doc_sacado_normalizado: str) -> SituacaoCadastral:
    """
    Retorna a situação cadastral do sacado.
    Se o modo DEMO estiver desativado ou o CNPJ não pertencer ao fixture sintético,
    retorna impreterivelmente NAO_VERIFICADA.
    """
    if not settings.ENABLE_DEMO_CADASTRO:
        return SituacaoCadastral.NAO_VERIFICADA

    return DEMO_CADASTRO_SINTETICO.get(
        doc_sacado_normalizado,
        SituacaoCadastral.NAO_VERIFICADA
    )


def obter_mapa_cadastral_para_lote(docs_sacados: set) -> Dict[str, str]:
    """Retorna dict com documento -> situacao.value para alimentar o motor."""
    return {
        doc: obter_situacao_cadastral(doc).value
        for doc in docs_sacados
    }
