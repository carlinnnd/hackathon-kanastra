"""
Modelos de domínio puros para o motor Antecipe.
Nenhuma dependência de banco de dados, ORM ou HTTP.
"""
import copy
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class SituacaoCadastral(str, Enum):
    ATIVA = "ATIVA"
    INATIVA = "INATIVA"
    NAO_VERIFICADA = "NAO_VERIFICADA"


@dataclass(frozen=True)
class ReceivelInput:
    """Dados brutos normalizados recebidos de cada linha do lote ou requisição."""
    linha: int
    nome_fundo: str
    doc_fundo: str
    nome_cedente: str
    doc_cedente: str
    nome_sacado: str
    doc_sacado: str
    nu_documento: str
    tipo_recebivel: str
    valor_nominal: Decimal
    data_vencimento: date
    data_aquisicao: Optional[date] = None

    @property
    def raiz_cnpj_sacado(self) -> str:
        """Primeiros 8 dígitos do CNPJ do sacado normalizado."""
        return self.doc_sacado[:8] if len(self.doc_sacado) >= 8 else self.doc_sacado

    @property
    def chave_duplicidade(self) -> str:
        """
        Chave global de unicidade (independente de fundo comprador):
        DOC_CEDENTE + DOC_SACADO + TIPO_RECEBIVEL + NU_DOCUMENTO + DATA_VENCIMENTO_ORIGINAL
        """
        tipo_clean = self.tipo_recebivel.strip().upper()
        doc_clean = self.nu_documento.strip().upper()
        return f"{self.doc_cedente}:{self.doc_sacado}:{tipo_clean}:{doc_clean}:{self.data_vencimento.isoformat()}"


@dataclass(frozen=True)
class MotivoRecusa:
    codigo: str
    mensagem: str
    dados: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultadoAvaliacao:
    linha: int
    documento: str
    sacado: str
    aprovado: bool
    valor_nominal: Optional[Decimal]
    valor_liquido: Optional[Decimal]
    motivos: List[MotivoRecusa] = field(default_factory=list)
    dias_vencimento: Optional[int] = None
    desconto: Optional[Decimal] = None


@dataclass
class SnapshotCarteira:
    """
    Estado consolidado e agregado da carteira histórica para permitir avaliação sem queries N+1.
    Garante proteção contra mutação externa.
    """
    total_nominal: Decimal = Decimal("0.00")
    exposicoes_sacado_raiz: Dict[str, Decimal] = field(default_factory=dict)
    exposicoes_cedente: Dict[str, Decimal] = field(default_factory=dict)
    chaves_duplicidade_existentes: Set[str] = field(default_factory=set)

    def criar_copia_isolada(self) -> "SnapshotCarteira":
        """Gera cópia profunda para garantir isolamento contra mutação concorrente."""
        return SnapshotCarteira(
            total_nominal=self.total_nominal,
            exposicoes_sacado_raiz=dict(self.exposicoes_sacado_raiz),
            exposicoes_cedente=dict(self.exposicoes_cedente),
            chaves_duplicidade_existentes=set(self.chaves_duplicidade_existentes)
        )


@dataclass
class EstadoProjetadoLote:
    """
    Acumulador mutável que mantém o estado projetado ao longo da iteração determinística do lote.
    Apenas recebíveis aprovados incrementam as exposições e o total da carteira projetada.
    """
    total_nominal: Decimal
    exposicoes_sacado_raiz: Dict[str, Decimal]
    exposicoes_cedente: Dict[str, Decimal]
    chaves_vistas_no_lote: Set[str] = field(default_factory=set)
