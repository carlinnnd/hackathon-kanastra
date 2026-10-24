"""
Serviço de aplicação para orquestração de simulações e avaliações de recebíveis.
Transacionalidade rigorosa e alta performance:
- Cria simulação pai ANTES dos itens filhos (integridade com PRAGMA foreign_keys=ON).
- Persiste em chunks com flush sem commit parcial via INSERT Core em lote.
- Suporta callback de progresso opcional (progress_callback(rows_processed)).
- Suporta gate de cancelamento opcional (cancel_check()) verificado imediatamente antes do commit atômico.
- Suporta teto de registros (max_records) para blindagem de stream.
- Checa capacidade máxima cumulativa de totais nominais/líquidos (TOTAL_MAXIMO_PERMITIDO) ANTES do commit,
  abortando o lote inteiro atomicamente com ValueError("TOTAL_EXCEDE_CAPACIDADE") e rollback completo.
- UMA única transação (commit no final; rollback completo em caso de falha).
"""
import io
import json
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from ..config import settings
from ..domain.engine import MotorAvaliacao, carregar_configuracao
from ..domain import calendar
from dataclasses import replace
from ..domain.ingestion import iterar_csv_recebiveis, parse_data_br, parse_decimal_br, normalizar_documento
from ..domain.limits import VALOR_MAXIMO_PERMITIDO, TOTAL_MAXIMO_PERMITIDO
from ..domain.models import ReceivelInput, ResultadoAvaliacao, SnapshotCarteira, EstadoProjetadoLote
from ..infrastructure.database.models import FundModel, RuleVersionModel, CargaEstoqueModel, SimulationReportModel
from ..infrastructure.repositories.receivables_repository import ReceivablesRepository
from ..infrastructure.repositories.rules_repository import RulesRepository
from ..infrastructure.repositories.simulations_repository import SimulationsRepository
from .cadastral_service import carregar_cadastro, obter_mapa_cadastral_para_lote
from .result_reporting import AgregadorResultados, serializar_resultado
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
        fundo_cnpj: Optional[str] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        max_records: Optional[int] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        tipo_analise: str = "novas_operacoes",
    ) -> Tuple[str, dict]:
        if tipo_analise not in {"novas_operacoes", "carteira"}:
            raise ValueError("Tipo de análise inválido. Use novas_operacoes ou carteira.")
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
        dt_base = data_base_override or calendar.data_atual()
        # A data operacional nao pode ficar congelada numa versao antiga do JSON.
        config_motor = replace(carregar_configuracao(raw_cfg, dt_base), data_base=dt_base)
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
        mapa_cadastral, fonte_cad = carregar_cadastro()
        agregador = AgregadorResultados(tipo_analise, config_motor)

        avisos = ["Cadastro simulado; não equivale a consulta oficial à Receita Federal."] if fonte_cad.startswith("SIMULADO") else []
        if tipo_analise == "carteira":
            avisos.append("Análise descritiva de estoque histórico. Títulos não são submetidos como novas operações e não há aquisição nem importação permanente.")
        limite_concentracao = next((Decimal(str(r.parametros["percentual_maximo"])) for r in config_motor.regras if r.codigo == "CONCENTRACAO_MAXIMA_SACADO" and r.ativo), None)
        for raiz, exp in snapshot_carteira.exposicoes_sacado_raiz.items():
            if snapshot_carteira.total_nominal > 0:
                pct = (exp / snapshot_carteira.total_nominal) * Decimal(100)
                if tipo_analise == "novas_operacoes" and limite_concentracao is not None and pct > limite_concentracao:
                    avisos.append(
                        f"Aviso de governança: Sacado raiz {raiz} possui exposição histórica de {pct:.2f}%, "
                        f"acima do limite configurado de {limite_concentracao:.2f}%. Histórico preservado; novas operações acima do limite são recusadas."
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
                if cancel_check and cancel_check():
                    raise RuntimeError("Cancelamento solicitado durante a ingestão do lote.")

                total_itens += 1

                if max_records and total_itens > max_records:
                    raise ValueError(f"Limite máximo de registros excedido: o lote ultrapassa {max_records} linhas.")

                if erro:
                    res = erro
                elif item:
                    exp = motor_estado_lote.exposicoes_sacado_raiz.get(item.raiz_cnpj_sacado, Decimal("0"))
                    total = motor_estado_lote.total_nominal
                    pct_atual = exp * 100 / total if total else Decimal("0")
                    pct_projetada = (exp + item.valor_nominal) * 100 / (total + item.valor_nominal) if total + item.valor_nominal > 0 else Decimal("0")
                    if tipo_analise == "carteira":
                        res = ResultadoAvaliacao(item.linha, item.nu_documento, item.nome_sacado, False,
                            item.valor_nominal, None, dias_vencimento=(item.data_vencimento - data_base_efetiva).days)
                    else:
                        res = motor.avaliar_recebivel(
                            recebivel=item, contexto_cadastral=mapa_cadastral,
                            estado_lote=motor_estado_lote, snapshot_historico=snapshot_carteira)
                    res.detalhes.update({
                        "originais": item.originais, "doc_fundo": item.doc_fundo,
                        "doc_cedente": item.doc_cedente, "doc_sacado": item.doc_sacado,
                        "nu_documento": item.nu_documento, "tipo_recebivel": item.tipo_recebivel,
                        "data_vencimento": item.data_vencimento.strftime("%d/%m/%Y"),
                        "raiz_cnpj_sacado": item.raiz_cnpj_sacado,
                        "situacao_cadastral": mapa_cadastral.get(item.doc_sacado, "NAO_VERIFICADA"),
                        "concentracao_atual_pct": f"{pct_atual:.4f}" if tipo_analise != "carteira" else None,
                        "concentracao_projetada_pct": f"{pct_projetada:.4f}" if tipo_analise != "carteira" else None,
                        "taxa_mensal": str(config_motor.precificacao.taxa_mensal),
                    })
                else:
                    continue

                res.detalhes["tipo_analise"] = tipo_analise
                res.detalhes["duplicado"] = any(m.codigo.startswith("DUPLICIDADE") for m in res.motivos)
                agregador.adicionar(res)

                if res.valor_nominal:
                    total_nominal_centavos += int((res.valor_nominal * 100).to_integral_value())

                if res.aprovado:
                    aprovados_count += 1
                    if res.valor_liquido:
                        total_liquido_centavos += int((res.valor_liquido * 100).to_integral_value())
                elif res.status != "CARTEIRA_HISTORICA":
                    recusados_count += 1

                total_nom_corrente = Decimal(total_nominal_centavos) / Decimal(100)
                total_liq_corrente = Decimal(total_liquido_centavos) / Decimal(100)
                if total_nom_corrente > TOTAL_MAXIMO_PERMITIDO or total_liq_corrente > TOTAL_MAXIMO_PERMITIDO:
                    raise TotalExcedeCapacidadeError(
                        "Total cumulativo do lote excede a capacidade técnica do sistema (teto R$ 9.999.999.999.999,99)."
                    )

                if len(primeira_pagina_resultados) < page_size:
                    primeira_pagina_resultados.append(serializar_resultado(res))

                buffer_resultados.append(res)

                if len(buffer_resultados) >= batch_size:
                    self.simulations_repo.salvar_itens_em_lote_transacional(sim_id, buffer_resultados)
                    buffer_resultados.clear()
                    if progress_callback:
                        progress_callback(total_itens)

            if buffer_resultados:
                self.simulations_repo.salvar_itens_em_lote_transacional(sim_id, buffer_resultados)
                buffer_resultados.clear()
                if progress_callback:
                    progress_callback(total_itens)

            # Gate de cancelamento checado imediatamente antes do commit
            if cancel_check and cancel_check():
                raise RuntimeError("Cancelamento solicitado imediatamente antes da consolidação do lote.")

            total_nominal_dec = Decimal(total_nominal_centavos) / Decimal(100)
            total_liquido_dec = Decimal(total_liquido_centavos) / Decimal(100)

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
            analytics = json.loads(json.dumps(agregador.finalizar(motor_estado_lote), default=str, ensure_ascii=False))
            self.db.add(SimulationReportModel(simulation_id=sim_id, tipo_analise=tipo_analise,
                analytics_json=json.dumps(analytics, ensure_ascii=False)))
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
            "tipo_analise": tipo_analise,
            "analytics": analytics,
            "resumo_motivos": {
                m["codigo"]: m["quantidade"] for m in (analytics.get("motivos", []) if analytics else [])
            },
            "nao_aprovados": total_itens - aprovados_count if tipo_analise == "novas_operacoes" else agregador.status["RECUSADA"],
            "recusas_confirmadas": agregador.status["RECUSADA"],
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

    def executar_simulacao_what_if(
        self,
        custom_config: dict,
        itens_lista: List[Tuple[int, Optional[ReceivelInput], Optional[ResultadoAvaliacao]]],
    ) -> dict:
        """
        Executa simulação comparativa 'What-If' puramente em memória (sem mutar o banco),
        confrontando a versão ativa de regras com a configuração hipotética fornecida.
        """
        fundo = self.db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
        if not fundo:
            raise ValueError("Fundo principal não encontrado.")

        versao_ativa = self.rules_repo.obter_versao_ativa(fundo.id)
        if not versao_ativa:
            raise ValueError("Nenhuma regra ativa configurada.")

        raw_ativa = json.loads(versao_ativa.configuration_json, parse_float=Decimal)
        dt_base = parse_data_br(settings.DATA_BASE) or date(2026, 10, 22)

        cfg_baseline = carregar_configuracao(raw_ativa, dt_base)
        cfg_what_if = carregar_configuracao(custom_config, dt_base)

        snapshot_base = self.receivables_repo.carregar_snapshot_carteira(fundo.id, chaves_candidatas=None)

        docs_unicos = {it.doc_sacado for _, it, _ in itens_lista if it is not None}
        mapa_cadastral = obter_mapa_cadastral_para_lote(docs_unicos)

        def _avaliar_cenario(cfg_motor) -> dict:
            motor = MotorAvaliacao(cfg_motor)
            snap_copia = snapshot_base.criar_copia_isolada()
            estado = EstadoProjetadoLote(
                total_nominal=snap_copia.total_nominal,
                exposicoes_sacado_raiz=dict(snap_copia.exposicoes_sacado_raiz),
                exposicoes_cedente=dict(snap_copia.exposicoes_cedente),
                chaves_vistas_no_lote=set(),
            )
            total = 0
            aprov = 0
            recus = 0
            nom_cent = 0
            liq_cent = 0
            motivos_map: Dict[str, int] = {}

            for _, item, erro in itens_lista:
                total += 1
                if erro:
                    res = erro
                elif item:
                    res = motor.avaliar_recebivel(
                        recebivel=item,
                        contexto_cadastral=mapa_cadastral,
                        estado_lote=estado,
                        snapshot_historico=snap_copia,
                    )
                else:
                    continue

                if res.valor_nominal:
                    nom_cent += int((res.valor_nominal * 100).to_integral_value())
                if res.aprovado:
                    aprov += 1
                    if res.valor_liquido:
                        liq_cent += int((res.valor_liquido * 100).to_integral_value())
                else:
                    recus += 1
                    for m in res.motivos:
                        motivos_map[m.codigo] = motivos_map.get(m.codigo, 0) + 1

            nom_dec = Decimal(nom_cent) / Decimal(100)
            liq_dec = Decimal(liq_cent) / Decimal(100)
            taxa_aprov = (Decimal(aprov) / Decimal(total) * Decimal(100)) if total > 0 else Decimal("0.0")
            return {
                "total_itens": total,
                "aprovados": aprov,
                "recusados": recus,
                "total_nominal": f"{nom_dec:.2f}",
                "total_liquido": f"{liq_dec:.2f}",
                "taxa_aprovacao_pct": f"{taxa_aprov:.1f}",
                "resumo_motivos": motivos_map,
                "_liq_dec": liq_dec,
            }

        res_base = _avaliar_cenario(cfg_baseline)
        res_what = _avaliar_cenario(cfg_what_if)

        liq_delta = res_what.pop("_liq_dec") - res_base.pop("_liq_dec")
        aprov_delta = res_what["aprovados"] - res_base["aprovados"]

        return {
            "baseline_version": versao_ativa.version_number,
            "data_base": cfg_what_if.data_base.isoformat(),
            "baseline": res_base,
            "what_if": res_what,
            "delta": {
                "aprovados_delta": aprov_delta,
                "liquido_delta_brl": f"{liq_delta:.2f}",
            },
        }
