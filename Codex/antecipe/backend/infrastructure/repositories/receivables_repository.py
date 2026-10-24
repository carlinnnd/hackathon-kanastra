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

    def obter_raio_x_grupo_economico(self, fundo_id: int, raiz_cnpj: str) -> dict:
        raiz_limpa = "".join(ch for ch in (raiz_cnpj or "") if ch.isdigit())[:8]
        total_centavos = (
            self.db.query(func.coalesce(func.sum(ReceivableModel.valor_nominal_centavos), 0))
            .filter(ReceivableModel.fund_id == fundo_id)
            .scalar()
        )
        total_carteira = Decimal(total_centavos) / Decimal(100)

        rows = (
            self.db.query(
                ReceivableModel.doc_sacado,
                ReceivableModel.nome_sacado,
                func.count(ReceivableModel.id).label("qtd"),
                func.coalesce(func.sum(ReceivableModel.valor_nominal_centavos), 0).label("soma_centavos"),
            )
            .filter(
                ReceivableModel.fund_id == fundo_id,
                ReceivableModel.raiz_cnpj_sacado == raiz_limpa,
            )
            .group_by(ReceivableModel.doc_sacado, ReceivableModel.nome_sacado)
            .order_by(func.sum(ReceivableModel.valor_nominal_centavos).desc())
            .all()
        )

        filiais = []
        exposicao_grupo_cent = 0
        nome_grupo = f"Grupo Econômico Raiz {raiz_limpa}"

        for idx, r in enumerate(rows):
            doc = r.doc_sacado or ""
            nome = r.nome_sacado or f"Unidade {doc}"
            if idx == 0 and nome:
                nome_grupo = nome.split(" - ")[0].strip()
            val_dec = Decimal(r.soma_centavos) / Decimal(100)
            exposicao_grupo_cent += int(r.soma_centavos)
            pct_unid = (val_dec / total_carteira * Decimal(100)) if total_carteira > 0 else Decimal("0.00")
            ordem = doc[8:12] if len(doc) == 14 else "0001"
            tipo_unidade = "MATRIZ (0001)" if ordem == "0001" else f"FILIAL ({ordem})"
            filiais.append({
                "doc_sacado": doc,
                "nome_sacado": nome,
                "tipo_unidade": tipo_unidade,
                "qtd_titulos": int(r.qtd),
                "valor_nominal": f"{val_dec:.2f}",
                "percentual_carteira": f"{pct_unid:.2f}",
            })

        exposicao_grupo = Decimal(exposicao_grupo_cent) / Decimal(100)
        conc_pct = (exposicao_grupo / total_carteira * Decimal(100)) if total_carteira > 0 else Decimal("0.00")
        limite_pct = Decimal("10.00")
        limite_brl = (total_carteira * limite_pct) / Decimal(100)
        excesso_brl = max(Decimal("0.00"), exposicao_grupo - limite_brl)

        return {
            "raiz_cnpj": raiz_limpa,
            "grupo_economico": nome_grupo,
            "total_carteira_fundo": f"{total_carteira:.2f}",
            "exposicao_atual_grupo": f"{exposicao_grupo:.2f}",
            "concentracao_atual_pct": f"{conc_pct:.2f}",
            "limite_regulamentar_pct": f"{limite_pct:.2f}",
            "excesso_atual_brl": f"{excesso_brl:.2f}",
            "bloqueado_novas_aquisicoes": conc_pct >= limite_pct,
            "filiais": filiais,
        }
