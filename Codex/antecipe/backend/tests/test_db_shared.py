"""
Configuração compartilhada e isolada de banco de dados para testes automatizados.
Usa um único engine em memória com StaticPool para todas as suítes de teste de integração.
"""
import os
from decimal import Decimal
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.infrastructure.database.session import Base
from backend.application.importer import inicializar_fundos_e_regras
from backend.infrastructure.database.models import ReceivableModel, FundModel

shared_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

SharedTestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=shared_test_engine)

Base.metadata.create_all(bind=shared_test_engine)


def init_shared_test_db():
    Base.metadata.create_all(bind=shared_test_engine)
    db = SharedTestingSessionLocal()
    json_path = os.path.abspath("validadores_antecipe.json")
    fundo = inicializar_fundos_e_regras(db, json_path)

    # Popula carteira base se vazia
    if db.query(ReceivableModel).filter(ReceivableModel.fund_id == fundo.id).count() == 0:
        sacados_iniciais = [
            ("04252011000110", "COMERCIAL ALPHA LTDA", Decimal("30000.00")),
            ("73410326000122", "SERVICOS BETA LTDA", Decimal("20000.00")),
            ("11222333000181", "INDUSTRIA GAMA SA", Decimal("50000.00")),
            ("22333444000192", "DISTRIBUIDORA DELTA", Decimal("400000.00")),
        ]
        for idx, (doc, nome, val) in enumerate(sacados_iniciais, start=1):
            rec = ReceivableModel(
                fund_id=fundo.id,
                chave_duplicidade=f"11222333000181:{doc}:DUPLICATA:NF-BASE-{idx}:2027-01-20",
                nome_cedente="INDUSTRIA BRASIL SA",
                doc_cedente="11222333000181",
                nome_sacado=nome,
                doc_sacado=doc,
                raiz_cnpj_sacado=doc[:8],
                nu_documento=f"NF-BASE-{idx}",
                tipo_recebivel="Duplicata",
                valor_nominal_centavos=int(val * 100),
                valor_nominal=val,
                data_vencimento=date(2027, 1, 20)
            )
            db.add(rec)

        rec_hist = ReceivableModel(
            fund_id=fundo.id,
            chave_duplicidade="11222333000181:04252011000110:DUPLICATA:NF-HIST-01:2027-01-20",
            nome_cedente="INDUSTRIA BRASIL SA",
            doc_cedente="11222333000181",
            nome_sacado="COMERCIAL ALPHA LTDA",
            doc_sacado="04252011000110",
            raiz_cnpj_sacado="04252011",
            nu_documento="NF-HIST-01",
            tipo_recebivel="Duplicata",
            valor_nominal_centavos=100000,
            valor_nominal=Decimal("1000.00"),
            data_vencimento=date(2027, 1, 20)
        )
        db.add(rec_hist)
        db.commit()
    db.close()
