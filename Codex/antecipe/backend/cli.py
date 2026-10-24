"""
CLI Operacional do Antecipe.
Fornece entrypoints auditáveis e sem copiar código imperativo:
- python -m backend.cli init
- python -m backend.cli import-stock --file <path>
- python -m backend.cli status
"""
import argparse
import os
import sys
from pathlib import Path
from decimal import Decimal

# Garante raiz do backend no path
current_dir = Path(__file__).resolve().parent
if str(current_dir.parent) not in sys.path:
    sys.path.insert(0, str(current_dir.parent))

from backend.infrastructure.database.session import Base, engine, SessionLocal
from backend.infrastructure.database.models import FundModel, ReceivableModel, CargaEstoqueModel
from backend.application.importer import inicializar_fundos_e_regras, importar_estoque_csv
from backend.config import settings
from backend.logger import logger


def cmd_init(args):
    """Inicializa banco e garante FIDC e V1 de regras carregadas."""
    print("[CLI] Inicializando banco de dados e regras...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        fundo = inicializar_fundos_e_regras(db, settings.VALIDADORES_JSON_PATH)
        print(f"[CLI] Fundo configurado: {fundo.nome} (CNPJ: {fundo.cnpj})")
        print(f"[CLI] Versão de regras ativa ID: {fundo.active_rule_version_id}")
    finally:
        db.close()


def cmd_import_stock(args):
    """Importa arquivo CSV de estoque de forma idempotente e transacional."""
    caminho = args.file or settings.ESTOQUE_CSV_PATH
    print(f"[CLI] Importando estoque a partir de: {caminho}...")
    db = SessionLocal()
    try:
        # Garante fundo e regras criados
        inicializar_fundos_e_regras(db, settings.VALIDADORES_JSON_PATH)
        
        total, antecipe_total, antecipe_nom, f_hash = importar_estoque_csv(
            db=db,
            csv_path=caminho,
            batch_size=args.batch_size
        )
        print(f"[CLI] Carga de estoque concluída com sucesso!")
        print(f"      Hash SHA-256: {f_hash}")
        print(f"      Total de registros importados (18 fundos): {total}")
        print(f"      Total ANTECIPE FIDC: {antecipe_total}")
        print(f"      Valor Nominal ANTECIPE: R$ {antecipe_nom:,.2f}")
    except Exception as exc:
        print(f"[CLI] ERRO na importação do estoque: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_status(args):
    """Verifica estado do sistema e do estoque."""
    db = SessionLocal()
    try:
        fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
        if not fundo:
            print("[CLI] Sistema não inicializado. Execute: python -m backend.cli init")
            return
        
        total_rec = db.query(ReceivableModel).filter(ReceivableModel.fund_id == fundo.id).count()
        carga = db.query(CargaEstoqueModel).order_by(CargaEstoqueModel.id.desc()).first()
        
        print(f"[CLI] Status do Sistema:")
        print(f"      Fundo: {fundo.nome}")
        print(f"      Regra Ativa ID: {fundo.active_rule_version_id}")
        print(f"      Recebíveis do fundo no banco: {total_rec}")
        if carga:
            print(f"      Última carga de estoque: {carga.file_name} (Hash: {carga.file_hash[:8]}...)")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="CLI de Operações e Carga do Antecipe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando init
    parser_init = subparsers.add_parser("init", help="Inicializa banco e regras ativas")
    parser_init.set_defaults(func=cmd_init)

    # Subcomando import-stock
    parser_import = subparsers.add_parser("import-stock", help="Importa CSV de estoque histórico")
    parser_import.add_argument("--file", type=str, default=None, help="Caminho do arquivo CSV de estoque")
    parser_import.add_argument("--batch-size", type=int, default=5000, help="Tamanho do lote de inserção")
    parser_import.set_defaults(func=cmd_import_stock)

    # Subcomando status
    parser_status = subparsers.add_parser("status", help="Exibe status do banco e estoque")
    parser_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
