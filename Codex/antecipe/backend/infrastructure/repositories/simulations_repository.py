import json
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.infrastructure.database.models import SimulationModel, SimulationItemModel, SimulationItemDetailModel
from backend.domain.models import ResultadoAvaliacao, MotivoRecusa


class SimulationsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def criar_simulacao_pai_inicial(
        self,
        simulation_id: str,
        fundo_id: int,
        rule_version_id: int,
        data_base,
        cadastro_fonte: str,
        carteira_referencia: str,
        configuration_hash: str,
    ) -> SimulationModel:
        """Cria registro da simulação pai ANTES dos itens filhos (integridade referencial estrita)."""
        sim = SimulationModel(
            id=simulation_id,
            fund_id=fundo_id,
            rule_version_id=rule_version_id,
            data_base=data_base,
            status="processando",
            total_itens=0,
            aprovados=0,
            recusados=0,
            total_nominal_centavos=0,
            total_liquido_centavos=0,
            total_nominal=Decimal("0.00"),
            total_liquido=Decimal("0.00"),
            cadastro_fonte=cadastro_fonte,
            carteira_referencia=carteira_referencia,
            configuration_hash=configuration_hash,
        )
        self.db.add(sim)
        self.db.flush()
        return sim

    def atualizar_totais_simulacao(
        self,
        simulation_id: str,
        total_itens: int,
        aprovados: int,
        recusados: int,
        total_nominal: Decimal,
        total_liquido: Decimal,
        avisos_json: str = "[]",
    ) -> None:
        """Atualiza totais e consolida status da simulação."""
        nom_centavos = int((total_nominal * 100).to_integral_value())
        liq_centavos = int((total_liquido * 100).to_integral_value())
        sim = self.obter_simulacao(simulation_id)
        if sim:
            sim.status = "concluida"
            sim.total_itens = total_itens
            sim.aprovados = aprovados
            sim.recusados = recusados
            sim.total_nominal_centavos = nom_centavos
            sim.total_liquido_centavos = liq_centavos
            sim.total_nominal = total_nominal
            sim.total_liquido = total_liquido
            sim.avisos_json = avisos_json
            self.db.flush()

    def salvar_itens_em_lote_transacional(
        self,
        simulation_id: str,
        itens: List[ResultadoAvaliacao],
    ) -> None:
        """
        Otimização de Alta Performance para até 1 Milhão de Registros:
        Utiliza INSERT Core (Session.execute com SimulationItemModel.__table__.insert())
        em vez de instanciar e rastrear objetos ORM individuais por linha.
        Preserva rigorosamente campos, motivos, valores exatos e FK na mesma transação.
        """
        if not itens:
            return

        batch_dicts = []
        for it in itens:
            motivos_dict = [
                {"codigo": m.codigo, "mensagem": m.mensagem, "dados": m.dados}
                for m in it.motivos
            ]
            batch_dicts.append({
                "simulation_id": simulation_id,
                "linha": it.linha,
                "documento": it.documento,
                "sacado": it.sacado,
                "aprovado": it.aprovado,
                "valor_nominal": it.valor_nominal,
                "valor_liquido": it.valor_liquido,
                "motivos_json": json.dumps(motivos_dict, ensure_ascii=False),
            })

        self.db.execute(SimulationItemModel.__table__.insert(), batch_dicts)
        from backend.application.result_reporting import serializar_resultado
        self.db.execute(SimulationItemDetailModel.__table__.insert(), [
            {"simulation_id": simulation_id, "linha": it.linha, "status": it.status,
             "payload_json": json.dumps(serializar_resultado(it), ensure_ascii=False)} for it in itens
        ])
        self.db.flush()

    def obter_simulacao(self, simulation_id: str) -> Optional[SimulationModel]:
        return self.db.query(SimulationModel).filter(SimulationModel.id == simulation_id).first()

    def listar_itens_paginados(
        self,
        simulation_id: str,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Tuple[List[SimulationItemModel], int]:
        query = self.db.query(SimulationItemModel).filter(SimulationItemModel.simulation_id == simulation_id)

        if status == "aprovado":
            query = query.filter(SimulationItemModel.aprovado == True)
        elif status == "recusado":
            query = query.filter(SimulationItemModel.aprovado == False)
        elif status in {"APROVADA", "RECUSADA", "PENDENTE_VERIFICACAO", "ERRO_DADOS", "CARTEIRA_HISTORICA"}:
            query = query.join(SimulationItemDetailModel,
                (SimulationItemDetailModel.simulation_id == SimulationItemModel.simulation_id) &
                (SimulationItemDetailModel.linha == SimulationItemModel.linha)
            ).filter(SimulationItemDetailModel.status == status)

        if reason:
            query = query.filter(SimulationItemModel.motivos_json.like(f"%{reason}%"))

        total = query.count()
        offset = (page - 1) * page_size
        itens = query.order_by(SimulationItemModel.linha.asc()).offset(offset).limit(page_size).all()
        return itens, total
