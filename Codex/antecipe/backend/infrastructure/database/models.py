"""
Modelos ORM SQLAlchemy do Antecipe.
Armazenamento monetário com exatidão:
- valor_nominal_centavos (BigInteger) no banco evita inconsistências de float em SQLite/PostgreSQL SUM.
- Converte para/de Decimal centavos no domínio.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from .session import Base


class FundModel(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(255), nullable=False)
    cnpj = Column(String(20), nullable=False, unique=True, index=True)
    active_rule_version_id = Column(Integer, ForeignKey("rule_versions.id", use_alter=True, name="fk_active_rule_version"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    rule_versions = relationship("RuleVersionModel", back_populates="fund", foreign_keys="RuleVersionModel.fund_id")
    receivables = relationship("ReceivableModel", back_populates="fund")
    simulations = relationship("SimulationModel", back_populates="fund")


class RuleVersionModel(Base):
    __tablename__ = "rule_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    configuration_json = Column(Text, nullable=False)
    configuration_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(100), default="system", nullable=False)
    change_reason = Column(Text, nullable=True)

    fund = relationship("FundModel", back_populates="rule_versions", foreign_keys=[fund_id])
    simulations = relationship("SimulationModel", back_populates="rule_version")

    __table_args__ = (
        UniqueConstraint("fund_id", "version_number", name="uq_fund_version_number"),
    )


class ReceivableModel(Base):
    """Carteira histórica de títulos adquiridos do estoque."""
    __tablename__ = "receivables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    
    # Identidade composta global (18 fundos)
    chave_duplicidade = Column(String(255), nullable=False, index=True)
    
    nome_cedente = Column(String(255), nullable=False)
    doc_cedente = Column(String(20), nullable=False, index=True)
    
    nome_sacado = Column(String(255), nullable=False)
    doc_sacado = Column(String(20), nullable=False, index=True)
    raiz_cnpj_sacado = Column(String(8), nullable=False, index=True)
    
    nu_documento = Column(String(100), nullable=False)
    tipo_recebivel = Column(String(100), nullable=False)
    
    # Inteiro de centavos para garantir exatidão absoluta em SQLite e Postgres SUM
    valor_nominal_centavos = Column(BigInteger, nullable=False)
    valor_nominal = Column(Numeric(15, 2), nullable=False)
    
    data_vencimento = Column(Date, nullable=False)
    data_aquisicao = Column(Date, nullable=True)

    fund = relationship("FundModel", back_populates="receivables")

    __table_args__ = (
        Index("idx_receivables_doc_sacado_raiz", "raiz_cnpj_sacado"),
        Index("idx_receivables_chave_duplicidade", "chave_duplicidade"),
        Index("idx_receivables_fund_raiz", "fund_id", "raiz_cnpj_sacado"),
    )


class SimulationModel(Base):
    """Execução de uma simulação de lote (upload CSV ou payload JSON)."""
    __tablename__ = "simulations"

    id = Column(String(36), primary_key=True)  # UUID4
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False, index=True)
    rule_version_id = Column(Integer, ForeignKey("rule_versions.id"), nullable=False, index=True)
    data_base = Column(Date, nullable=False)
    status = Column(String(50), default="concluida", nullable=False)
    
    total_itens = Column(Integer, nullable=False, default=0)
    aprovados = Column(Integer, nullable=False, default=0)
    recusados = Column(Integer, nullable=False, default=0)
    
    total_nominal_centavos = Column(BigInteger, nullable=False, default=0)
    total_liquido_centavos = Column(BigInteger, nullable=False, default=0)
    total_nominal = Column(Numeric(15, 2), nullable=False, default=0)
    total_liquido = Column(Numeric(15, 2), nullable=False, default=0)

    # Auditoria snapshot estrito
    cadastro_fonte = Column(String(100), nullable=False, default="SIMULADO_DEMO")
    carteira_referencia = Column(String(255), nullable=False)
    configuration_hash = Column(String(64), nullable=False)
    avisos_json = Column(Text, nullable=False, default="[]")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    fund = relationship("FundModel", back_populates="simulations")
    rule_version = relationship("RuleVersionModel", back_populates="simulations")
    items = relationship("SimulationItemModel", back_populates="simulation", cascade="all, delete-orphan")


class SimulationItemModel(Base):
    """Resultado individual de cada nota fiscal avaliada dentro da simulação."""
    __tablename__ = "simulation_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(String(36), ForeignKey("simulations.id"), nullable=False, index=True)
    linha = Column(Integer, nullable=False)
    documento = Column(String(100), nullable=False)
    sacado = Column(String(255), nullable=False)
    aprovado = Column(Boolean, nullable=False, index=True)
    
    valor_nominal = Column(Numeric(15, 2), nullable=True)
    valor_liquido = Column(Numeric(15, 2), nullable=True)
    motivos_json = Column(Text, nullable=False, default="[]")

    simulation = relationship("SimulationModel", back_populates="items")

    __table_args__ = (
        Index("idx_simulation_items_sim_aprovado", "simulation_id", "aprovado"),
    )


class AuditEventModel(Base):
    """Auditoria de eventos do sistema (ex: ativação de regras)."""
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), nullable=False, index=True)
    actor = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class CargaEstoqueModel(Base):
    """Registro idempotente de carga de arquivos de estoque."""
    __tablename__ = "cargas_estoque"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_hash = Column(String(64), nullable=False, unique=True, index=True)
    file_name = Column(String(255), nullable=False)
    total_linhas = Column(Integer, nullable=False)
    total_antecipe = Column(Integer, nullable=False)
    nominal_antecipe_centavos = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
