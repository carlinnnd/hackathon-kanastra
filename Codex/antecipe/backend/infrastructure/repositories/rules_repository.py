import hashlib
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.infrastructure.database.models import FundModel, RuleVersionModel, AuditEventModel


def serializar_config_canonica(config_dict: dict) -> str:
    def default_serializer(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Tipo não serializável: {type(obj)}")

    return json.dumps(
        config_dict,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=default_serializer
    )


def calcular_hash_config(config_dict: dict) -> str:
    canon = serializar_config_canonica(config_dict)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class RulesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def obter_versao_ativa(self, fundo_id: int) -> Optional[RuleVersionModel]:
        fundo = self.db.query(FundModel).filter(FundModel.id == fundo_id).first()
        if not fundo or not fundo.active_rule_version_id:
            return None
        return self.db.query(RuleVersionModel).filter(RuleVersionModel.id == fundo.active_rule_version_id).first()

    def listar_versoes(self, fundo_id: int) -> List[Tuple[RuleVersionModel, bool]]:
        fundo = self.db.query(FundModel).filter(FundModel.id == fundo_id).first()
        active_id = fundo.active_rule_version_id if fundo else None
        
        versoes = (
            self.db.query(RuleVersionModel)
            .filter(RuleVersionModel.fund_id == fundo_id)
            .order_by(RuleVersionModel.version_number.desc())
            .all()
        )
        return [(v, v.id == active_id) for v in versoes]

    def obter_versao_por_id(self, version_id: int) -> Optional[RuleVersionModel]:
        return self.db.query(RuleVersionModel).filter(RuleVersionModel.id == version_id).first()

    def criar_versao(
        self,
        fundo_id: int,
        config_dict: dict,
        created_by: str = "admin",
        change_reason: Optional[str] = None
    ) -> RuleVersionModel:
        ultima_versao = (
            self.db.query(RuleVersionModel)
            .filter(RuleVersionModel.fund_id == fundo_id)
            .order_by(RuleVersionModel.version_number.desc())
            .first()
        )
        novo_numero = (ultima_versao.version_number + 1) if ultima_versao else 1
        cfg_str = serializar_config_canonica(config_dict)
        cfg_hash = hashlib.sha256(cfg_str.encode("utf-8")).hexdigest()

        nova_versao = RuleVersionModel(
            fund_id=fundo_id,
            version_number=novo_numero,
            configuration_json=cfg_str,
            configuration_hash=cfg_hash,
            created_by=created_by,
            change_reason=change_reason or f"Publicação da versão {novo_numero}"
        )
        self.db.add(nova_versao)

        evento = AuditEventModel(
            event_type="RULE_VERSION_CREATED",
            actor=created_by,
            description=f"Criada versão de regras {novo_numero} para fundo {fundo_id}",
            metadata_json=json.dumps({"version_number": novo_numero, "hash": cfg_hash})
        )
        self.db.add(evento)
        self.db.commit()
        self.db.refresh(nova_versao)
        return nova_versao

    def ativar_versao(
        self,
        fundo_id: int,
        version_id: int,
        actor: str = "admin",
        versao_esperada_anterior_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        versao = self.obter_versao_por_id(version_id)
        if not versao or versao.fund_id != fundo_id:
            return False, "Versão não encontrada para o fundo especificado."

        fundo = self.db.query(FundModel).filter(FundModel.id == fundo_id).with_for_update().first()
        if not fundo:
            return False, "Fundo não encontrado."

        if versao_esperada_anterior_id is not None and fundo.active_rule_version_id != versao_esperada_anterior_id:
            return False, "Conflito de concorrência: a versão ativa já foi modificada por outro processo."

        versao_anterior_id = fundo.active_rule_version_id
        fundo.active_rule_version_id = version_id
        
        evento = AuditEventModel(
            event_type="RULE_VERSION_ACTIVATED",
            actor=actor,
            description=f"Ativada versão {versao.version_number} (ID {version_id}) para fundo {fundo_id}",
            metadata_json=json.dumps({
                "versao_anterior_id": versao_anterior_id,
                "versao_ativada_id": version_id,
                "hash": versao.configuration_hash
            })
        )
        self.db.add(evento)
        self.db.commit()
        return True, None
