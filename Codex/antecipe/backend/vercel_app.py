"""
Wrapper Vercel Serverless / Demonstração Pública Efêmera.
Encapsula a aplicação FastAPI Antecipe para execução em ambientes serverless:
- Define banco SQLite temporário efêmero em tempfile.gettempdir() (/tmp/antecipe-vercel-demo.db) caso não informado.
- Validação estrita de isolamento: se PUBLIC_DEMO_MODE=True, recusa startup com RuntimeError
  caso o banco não seja estritamente efêmero (deve estar dentro de tempfile.gettempdir() ou ser :memory:).
  NUNCA toca em banco real, banco local ou PostgreSQL externo.
- Se PUBLIC_DEMO_MODE=True e o banco for validado como efêmero, inicializa schema e realiza seed
  exclusivamente com 5 títulos sintéticos públicos de demonstração (4 base + 1 histórico).
"""
import os
import tempfile
from decimal import Decimal
from datetime import date
from pathlib import Path

# Apenas define fallback temporário de DATABASE_URL se não fornecido pelo ambiente
temp_db_path = Path(tempfile.gettempdir()) / "antecipe-vercel-demo.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{temp_db_path.as_posix()}")

from backend.config import settings
from backend.infrastructure.database.session import Base, engine, SessionLocal
from backend.infrastructure.database.models import FundModel, ReceivableModel, RuleVersionModel
from backend.application.importer import inicializar_fundos_e_regras
from backend.main import app as fastapi_app


def validar_banco_efemero_seguro(engine_instance) -> bool:
    """
    Garante que sob PUBLIC_DEMO_MODE o banco de dados seja estritamente efêmero
    (em memória ou arquivo estritamente contido dentro de tempfile.gettempdir()).
    """
    url = engine_instance.url
    if not url.drivername.startswith("sqlite"):
        return False

    db_name = url.database
    if not db_name or db_name == ":memory:":
        return True

    try:
        resolved_db = Path(db_name).resolve()
        temp_dir = Path(tempfile.gettempdir()).resolve()
        # Verifica se o arquivo está estritamente dentro do diretório temporário do sistema
        return temp_dir in resolved_db.parents or resolved_db.parent == temp_dir
    except Exception:
        return False


def seed_carteira_sintetica_publica(db):
    """
    Realiza o seed de 5 títulos sintéticos públicos e documentados
    para demonstração efêmera (sem utilizar nenhuma linha do estoque real de 100k).
    """
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    if not fundo:
        json_path = os.path.abspath(settings.VALIDADORES_JSON_PATH)
        if not os.path.isfile(json_path):
            json_path = str(Path(__file__).resolve().parent.parent.parent.parent / "validadores_antecipe.json")
        fundo = inicializar_fundos_e_regras(db, json_path)

    if db.query(ReceivableModel).filter(ReceivableModel.fund_id == fundo.id).count() == 0:
        titulos_sinteticos_base = [
            ("04252011000110", "COMERCIAL ALPHA LTDA", Decimal("30000.00"), "1"),
            ("73410326000122", "SERVICOS BETA LTDA", Decimal("20000.00"), "2"),
            ("11222333000181", "INDUSTRIA GAMA SA", Decimal("50000.00"), "3"),
            ("22333444000192", "DISTRIBUIDORA DELTA", Decimal("400000.00"), "4"),
        ]
        for doc, nome, val, idx in titulos_sinteticos_base:
            rec = ReceivableModel(
                fund_id=fundo.id,
                chave_duplicidade=f"11222333000181:{doc}:DUPLICATA:NF-DEMO-SINTETICA-{idx}:2027-01-20",
                nome_cedente="INDUSTRIA BRASIL SA",
                doc_cedente="11222333000181",
                nome_sacado=nome,
                doc_sacado=doc,
                raiz_cnpj_sacado=doc[:8],
                nu_documento=f"NF-DEMO-SINTETICA-{idx}",
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


# Validação e inicialização sob PUBLIC_DEMO_MODE
if settings.PUBLIC_DEMO_MODE:
    if not validar_banco_efemero_seguro(engine):
        raise RuntimeError(
            "Segurança: PUBLIC_DEMO_MODE ativado mas DATABASE_URL não aponta para banco efêmero "
            f"em tempfile.gettempdir() ou :memory:. Operação abortada para proteger dados reais."
        )

    Base.metadata.create_all(bind=engine)
    _db = SessionLocal()
    try:
        seed_carteira_sintetica_publica(_db)
    finally:
        _db.close()

app = fastapi_app
