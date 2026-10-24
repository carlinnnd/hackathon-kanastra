"""
Serviço de aplicação para orquestração de simulações e avaliações de recebíveis.
Transacionalidade rigorosa:
- Cria simulação pai ANTES dos itens filhos (integridade com PRAGMA foreign_keys=ON).
- Persiste em chunks com flush sem commit parcial.
- Checa capacidade máxima cumulativa de totais nominais/líquidos (TOTAL_MAXIMO_PERMITIDO) ANTES do commit,
  abortando o lote inteiro atomicamente com ValueError("TOTAL_EXCEDE_CAPACIDADE") e rollback completo.
- UMA única transação (commit no final; rollback completo em caso de falha).
- Data-base de precificação e persistência estritamente alinhadas com config_motor.data_base.
"""
import io
import json
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Iterator, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from ..config import settings
from ..domain.engine import MotorAvaliacao, carregar_configuracao
from ..domain.ingestion import iterar_csv_recebiveis, parse_data_br, parse_decimal_br, normalizar_documento
from ..domain.limits import VALOR_MAXIMO_PERMITIDO, TOTAL_MAXIMO_PERMITIDO
from ..domain.models import ReceivelInput, ResultadoAvaliacao, SnapshotCarteira, EstadoProjetadoLote
from ..infrastructure.database.models import FundModel, RuleVersionModel, CargaEstoqueModel
from ..infrastructure.repositories.receivables_repository import ReceivablesRepository
from ..infrastructure.repositories.rules_repository import RulesRepository
from ..infrastructure.repositories.simulations_repository import SimulationsRepository
from .cadastral_service import obter_mapa_cadastral_para_lote
from ..logger import logger


class TotalExcedeCapacidadeError(ValueError):
    """Exceção dedicada para estouro de capacidade cumulativa de totais."""
    def __init__(self, mensagem: str = "Total cumulativo do lote excede a capacidade técnica do sistema."):
        super().__init__(mensagem)
        self.codigo = "TOTAL_EXCEDE_CAPACIDADE"


class SimulationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rules_repo = RulesRepository(db)
        self.receivables_repo = ReceivablesRepository(db)
        self.simulations_repo = SimulationsRepository(db)

    def executar_simulacao_lote(
        self,
        itens_stream: Iterator[Tuple[int, Optional[ReceivelInput], Optional[ResultadoAvaliacao]]],
        data_base_override: Optional[date] = None,
        fundo_cnpj: Optional[str] = None
    ) -> Tuple[str, dict]:
        cnpj_norm = normalizar_documento(fundo_cnpj or "92234400000180")
        fundo = self.db.query(FundModel).filter(FundModel.cnpj == cnpj_norm).first()
        if not fundo:
            fundo = self.db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()

        if not fundo:
            raise ValueError(f"Fundo especificado '{cnpj_norm}' não localizado no sistema.")

        versao_ativa = self.rules_repo.obter_versao_ativa(fundo.id)
        if not versao_ativa:
            raise ValueError(f"Nenhuma versão de regra ativa configurada para o fundo {fundo.nome}.")

        raw_cfg = json.loads(versao_ativa.configuration_json, parse_float=Decimal)
        dt_base = data_base_override or parse_data_br(settings.DATA_BASE) or date(2026, 10, 22)
        config_motor = carregar_configuracao(raw_cfg, dt_base)
        motor = MotorAvaliacao(config_motor)
        
        data_base_efetiva = config_motor.data_base

        snapshot_carteira = self.receivables_repo.carregar_snapshot_carteira(fundo.id, chaves_candidatas=None)

        motor_estado_lote = EstadoProjetadoLote(
            total_nominal=snapshot_carteira.total_nominal,
            exposicoes_sacado_raiz=dict(snapshot_carteira.exposicoes_sacado_raiz),
            exposicoes_cedente=dict(snapshot_carteira.exposicoes_cedente),
            chaves_vistas_no_lote=set()
        )

        sim_id = str(uuid.uuid4())
        ultima_carga = self.db.query(CargaEstoqueModel).order_by(CargaEstoqueModel.id.desc()).first()
        carteira_ref = f"ESTOQUE_{fundo.nome}_HASH_{ultima_carga.file_hash[:8]}" if ultima_carga else f"ESTOQUE_{fundo.nome}"
        fonte_cad = "SIMULADO_DEMO" if settings.ENABLE_DEMO_CADASTRO else "NAO_VERIFICADA_PADRAO"

        avisos = []
        for raiz, exp in snapshot_carteira.exposicoes_sacado_raiz.items():
            if snapshot_carteira.total_nominal > 0:
                pct = (exp / snapshot_carteira.total_nominal) * Decimal(100)
                if pct > Decimal("10.00"):
                    avisos.append(
                        f"Aviso de governança: Sacado raiz {raiz} possui exposição histórica de {pct:.2f}%, "
                        f"acima do limite regulamentar de 10.00%."
                    )

        # 1. Cria a simulação PAI no banco com flush (evita violação de FK PRAGMA foreign_keys=ON)
        self.simulations_repo.criar_simulacao_pai_inicial(
            simulation_id=sim_id,
            fundo_id=fundo.id,
            rule_version_id=versao_ativa.id,
            data_base=data_base_efetiva,
            cadastro_fonte=fonte_cad,
            carteira_referencia=carteira_ref,
            configuration_hash=versao_ativa.configuration_hash
        )

        total_itens = 0
        aprovados_count = 0
        recusados_count = 0
        total_nominal_centavos = 0
        total_liquido_centavos = 0

        page_size = 50
        primeira_pagina_resultados: List[dict] = []
        batch_size = 2000
        buffer_resultados: List[ResultadoAvaliacao] = []

        try:
            for idx, item, erro in itens_stream:
                total_itens += 1

                if erro:
                    res = erro
                elif item:
                    mapa_cadastral = obter_mapa_cadastral_para_lote({item.doc_sacado})
                    res = motor.avaliar_recebivel(
                        recebivel=item,
                        contexto_cadastral=mapa_cadastral,
                        estado_lote=motor_estado_lote,
                        snapshot_historico=snapshot_carteira
                    )
                else:
                    continue

                if res.valor_nominal:
                    total_nominal_centavos += int((res.valor_nominal * 100).to_integral_value())

                if res.aprovado:
                    aprovados_count += 1
                    if res.valor_liquido:
                        total_liquido_centavos += int((res.valor_liquido * 100).to_integral_value())
                else:
                    recusados_count += 1

                # Checagem precoce de estouro de capacidade cumulativa
                total_nom_corrente = Decimal(total_nominal_centavos) / Decimal(100)
                total_liq_corrente = Decimal(total_liquido_centavos) / Decimal(100)
                if total_nom_corrente > TOTAL_MAXIMO_PERMITIDO or total_liq_corrente > TOTAL_MAXIMO_PERMITIDO:
                    raise TotalExcedeCapacidadeError(
                        "Total cumulativo do lote excede a capacidade técnica do sistema (teto R$ 9.999.999.999.999,99)."
                    )

                if len(primeira_pagina_resultados) < page_size:
                    primeira_pagina_resultados.append({
                        "linha": res.linha,
                        "documento": res.documento,
                        "sacado": res.sacado,
                        "aprovado": res.aprovado,
                        "valor_nominal": f"{res.valor_nominal:.2f}" if res.valor_nominal is not None else None,
                        "valor_liquido": f"{res.valor_liquido:.2f}" if res.valor_liquido is not None else None,
                        "motivos": [
                            {"codigo": m.codigo, "mensagem": m.mensagem, "dados": m.dados}
                            for m in res.motivos
                        ]
                    })

                buffer_resultados.append(res)

                if len(buffer_resultados) >= batch_size:
                    self.simulations_repo.salvar_itens_em_lote_transacional(sim_id, buffer_resultados)
                    buffer_resultados.clear()

            if buffer_resultados:
                self.simulations_repo.salvar_itens_em_lote_transacional(sim_id, buffer_resultados)
                buffer_resultados.clear()

            total_nominal_dec = Decimal(total_nominal_centavos) / Decimal(100)
            total_liquido_dec = Decimal(total_liquido_centavos) / Decimal(100)

            # Validação cumulativa final antes de persistir
            if total_nominal_dec > TOTAL_MAXIMO_PERMITIDO or total_liquido_dec > TOTAL_MAXIMO_PERMITIDO:
                raise TotalExcedeCapacidadeError(
                    "Total cumulativo do lote excede a capacidade técnica do sistema (teto R$ 9.999.999.999.999,99)."
                )

            # 2. Atualiza os totais consolidados da simulação pai
            self.simulations_repo.atualizar_totais_simulacao(
                simulation_id=sim_id,
                total_itens=total_itens,
                aprovados=aprovados_count,
                recusados=recusados_count,
                total_nominal=total_nominal_dec,
                total_liquido=total_liquido_dec,
                avisos_json=json.dumps(avisos, ensure_ascii=False)
            )

            # 3. UMA ÚNICA TRANSAÇÃO: commit atômico de pai e todos os filhos
            self.db.commit()

        except Exception as exc:
            self.db.rollback()
            logger.error(
                "Falha na simulacao: transacao revertida completamente via rollback",
                extra={"event": "SIMULATION_ROLLBACK", "simulation_id": sim_id, "error_code": getattr(exc, "codigo", "SIMULATION_FAILED")}
            )
            raise exc

        total_pages = (total_itens + page_size - 1) // page_size if total_itens else 1

        envelope = {
            "simulation_id": sim_id,
            "rule_version": versao_ativa.version_number,
            "rule_version_id": versao_ativa.id,
            "data_base": data_base_efetiva.isoformat(),
            "status": "concluida",
            "total_itens": total_itens,
            "aprovados": aprovados_count,
            "recusados": recusados_count,
            "total_nominal": f"{total_nominal_dec:.2f}",
            "total_liquido": f"{total_liquido_dec:.2f}",
            "resultados": primeira_pagina_resultados,
            "pagination": {
                "page": 1,
                "page_size": page_size,
                "total": total_itens,
                "total_pages": total_pages
            },
            "auditoria": {
                "cadastro_fonte": fonte_cad,
                "carteira_referencia": carteira_ref,
                "configuration_hash": versao_ativa.configuration_hash
            },
            "avisos": avisos
        }

        logger.info(
            "Simulacao concluida com streaming e agregacao exata",
            extra={
                "event": "SIMULATION_COMPLETED",
                "simulation_id": sim_id,
                "rule_version_id": versao_ativa.id,
                "total_itens": total_itens,
                "aprovados": aprovados_count,
                "recusados": recusados_count,
            }
        )

        return sim_id, envelope
