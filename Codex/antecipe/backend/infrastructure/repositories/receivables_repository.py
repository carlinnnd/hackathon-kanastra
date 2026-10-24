from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Set, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.domain.models import SnapshotCarteira
from backend.infrastructure.database.models import ReceivableModel, FundModel


class ReceivablesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def carregar_snapshot_carteira(
        self,
        fundo_id: int,
        chaves_candidatas: Optional[Iterable[str]] = None
    ) -> SnapshotCarteira:
        total_centavos = (
            self.db.query(func.coalesce(func.sum(ReceivableModel.valor_nominal_centavos), 0))
            .filter(ReceivableModel.fund_id == fundo_id)
            .scalar()
        )
        total_nominal_decimal = Decimal(total_centavos) / Decimal(100)

        res_sacados = (
            self.db.query(
                ReceivableModel.raiz_cnpj_sacado,
                func.sum(ReceivableModel.valor_nominal_centavos)
            )
            .filter(ReceivableModel.fund_id == fundo_id)
            .group_by(ReceivableModel.raiz_cnpj_sacado)
            .all()
        )
        exposicoes_sacado_raiz = {
            r[0]: (Decimal(r[1]) / Decimal(100)) for r in res_sacados if r[0]
        }

        res_cedentes = (
            self.db.query(
                ReceivableModel.doc_cedente,
                func.sum(ReceivableModel.valor_nominal_centavos)
            )
            .filter(ReceivableModel.fund_id == fundo_id)
            .group_by(ReceivableModel.doc_cedente)
            .all()
        )
        exposicoes_cedente = {
            r[0]: (Decimal(r[1]) / Decimal(100)) for r in res_cedentes if r[0]
        }

        chaves_duplicidade: Set[str] = set()
        if chaves_candidatas is not None:
            cand_list = list(chaves_candidatas)
            chunk_size = 900
            for i in range(0, len(cand_list), chunk_size):
                chunk = cand_list[i:i + chunk_size]
                if chunk:
                    rows = (
                        self.db.query(ReceivableModel.chave_duplicidade)
                        .filter(ReceivableModel.chave_duplicidade.in_(chunk))
                        .all()
                    )
                    chaves_duplicidade.update(r[0] for r in rows)
        else:
            chaves_query = self.db.query(ReceivableModel.chave_duplicidade).all()
            chaves_duplicidade = {row[0] for row in chaves_query}

        return SnapshotCarteira(
            total_nominal=total_nominal_decimal,
            exposicoes_sacado_raiz=exposicoes_sacado_raiz,
            exposicoes_cedente=exposicoes_cedente,
            chaves_duplicidade_existentes=chaves_duplicidade,
        )

    def obter_resumo_portfolio(self, fundo_id: int) -> dict:
        fundo = self.db.query(FundModel).filter(FundModel.id == fundo_id).first()
        if not fundo:
            return {}

        total_centavos, count = (
            self.db.query(
                func.coalesce(func.sum(ReceivableModel.valor_nominal_centavos), 0),
                func.count(ReceivableModel.id)
            )
            .filter(ReceivableModel.fund_id == fundo_id)
            .first()
        )
        total_nom = Decimal(total_centavos) / Decimal(100)

        maior_exposicao = (
            self.db.query(
                ReceivableModel.raiz_cnpj_sacado,
                func.sum(ReceivableModel.valor_nominal_centavos).label("total_centavos")
            )
            .filter(ReceivableModel.fund_id == fundo_id)
            .group_by(ReceivableModel.raiz_cnpj_sacado)
            .order_by(func.sum(ReceivableModel.valor_nominal_centavos).desc())
            .first()
        )

        maior_pct = "0.00"
        avisos = []
        if maior_exposicao and total_nom > 0:
            exp_dec = Decimal(maior_exposicao.total_centavos) / Decimal(100)
            pct = (exp_dec / total_nom) * Decimal(100)
            maior_pct = f"{pct:.2f}"
            if pct > Decimal("10.00"):
                avisos.append(
                    f"Aviso de governança: Sacado raiz {maior_exposicao.raiz_cnpj_sacado} possui exposição histórica de {maior_pct}%, acima do limite regulamentar de 10.00%."
                )

        return {
            "nome_fundo": fundo.nome,
            "cnpj_fundo": fundo.cnpj,
            "total_nominal": f"{total_nom:.2f}",
            "total_recebiveis": count,
            "maior_concentracao_raiz_pct": maior_pct,
            "avisos": avisos
        }
