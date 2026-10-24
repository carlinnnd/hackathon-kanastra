"""
Esquemas Pydantic para validação de contratos da API HTTP.
Garante:
- Sem cálculo float.
- Envelopes padronizados e documentados.
- Tipagem estrita.
"""
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class MotivoRecusaSchema(BaseModel):
    codigo: str
    mensagem: str
    dados: Optional[Dict[str, Any]] = None


class ItemResultadoSchema(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: Literal["APROVADA", "RECUSADA", "CARTEIRA_HISTORICA"]
    linha: int
    documento: str
    sacado: str
    aprovado: bool
    valor_nominal: Optional[str] = None
    valor_liquido: Optional[str] = None
    motivos: List[MotivoRecusaSchema] = Field(default_factory=list)


class PaginationSchema(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class AuditoriaSchema(BaseModel):
    cadastro_fonte: str
    carteira_referencia: str
    configuration_hash: str


class SimulationResponseSchema(BaseModel):
    model_config = ConfigDict(extra="allow")
    simulation_id: str
    rule_version: int
    rule_version_id: int
    data_base: str
    status: str
    total_itens: int
    aprovados: int
    recusados: int
    total_nominal: str
    total_liquido: str
    resultados: List[ItemResultadoSchema]
    pagination: PaginationSchema
    auditoria: AuditoriaSchema
    avisos: List[str] = Field(default_factory=list)


# Requisição de Avaliação Direta via JSON
class ReceivelRawInputSchema(BaseModel):
    NOME_FUNDO: Optional[str] = "ANTECIPE FIDC"
    DOC_FUNDO: Optional[str] = "92.234.400/0001-80"
    NOME_CEDENTE: str
    DOC_CEDENTE: str
    NOME_SACADO: str
    DOC_SACADO: str
    NU_DOCUMENTO: str
    TIPO_RECEBIVEL: str
    VALOR_NOMINAL: str  # String com valor monetário (ex: "5000,00" ou "5000.00")
    DATA_VENCIMENTO_ORIGINAL: str  # "dd/mm/aaaa" ou "aaaa-mm-dd"
    DATA_AQUISICAO: Optional[str] = None


class ReceivablesEvaluateRequestSchema(BaseModel):
    recebiveis: List[ReceivelRawInputSchema]
    data_base: Optional[str] = "2026-10-22"


# Versões de regras
class RuleVersionCreateSchema(BaseModel):
    configuration: Dict[str, Any]
    change_reason: Optional[str] = "Atualização de regras"


class RuleVersionItemSchema(BaseModel):
    id: int
    version_number: int
    created_at: str
    created_by: str
    change_reason: Optional[str]
    is_active: bool
    configuration_hash: str


# Erros amigáveis da API
class ErrorDetailSchema(BaseModel):
    codigo: str
    mensagem: str


class ErrorResponseSchema(BaseModel):
    detail: ErrorDetailSchema
