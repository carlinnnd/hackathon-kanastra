import csv
import io
import json
import os
import secrets
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile, File, Response, status as http_status
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..domain import calendar
from ..domain.ingestion import iterar_csv_recebiveis, parse_data_br, parse_decimal_br, normalizar_documento
from ..domain.engine import carregar_configuracao
from ..domain.models import ReceivelInput, ResultadoAvaliacao, MotivoRecusa
from ..infrastructure.database.session import get_db
from ..infrastructure.database.models import FundModel, RuleVersionModel
from ..infrastructure.repositories.rules_repository import RulesRepository
from ..infrastructure.repositories.receivables_repository import ReceivablesRepository
from ..infrastructure.repositories.simulations_repository import SimulationsRepository
from ..application.simulation_service import SimulationService, TotalExcedeCapacidadeError
from ..application.cadastral_service import carregar_cadastro
from ..application.result_reporting import obter_analytics, serializar_pagina
from ..application.exports import exportar
import sys as _sys
_ANTECIPE_ROOT = Path(__file__).resolve().parent.parent.parent


def _gerador_sintetico():
    """Import tardio do gerador de lotes sintéticos (opcional no deploy serverless)."""
    if str(_ANTECIPE_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ANTECIPE_ROOT))
    try:
        from scripts.generate_simulation_batches import iterar_linhas_lote_sintetico, salvar_lote_csv
    except ImportError:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "GERADOR_INDISPONIVEL", "mensagem": "Gerador de lotes sintéticos indisponível neste ambiente."}
        )
    return iterar_linhas_lote_sintetico, salvar_lote_csv


from .schemas import (
    SimulationResponseSchema,
    ReceivablesEvaluateRequestSchema,
    RuleVersionCreateSchema,
    RuleVersionItemSchema,
    WhatIfSimulationRequestSchema,
    ErrorResponseSchema,
)

router = APIRouter(prefix="/api", tags=["Antecipe API"])


def verificar_admin_token(x_admin_token: Optional[str] = Header(None)) -> str:
    if not settings.ADMIN_TOKEN or settings.ADMIN_TOKEN.strip() == "":
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "ADMIN_DESABILITADO", "mensagem": "Operações administrativas desabilitadas no servidor (ADMIN_TOKEN não configurado)."}
        )

    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.ADMIN_TOKEN):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"codigo": "ADMIN_TOKEN_INVALIDO", "mensagem": "Token administrativo inválido ou ausente."}
        )
    return x_admin_token


@router.get("/health")
def get_health(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    receivables_repo = ReceivablesRepository(db)
    rules_repo = RulesRepository(db)
    
    resumo = receivables_repo.obter_resumo_portfolio(fundo.id) if fundo else {}
    versao_ativa = rules_repo.obter_versao_ativa(fundo.id) if fundo else None
    
    total_reg = resumo.get("total_recebiveis", 0)
    health_resp = {
        "status": "ok",
        "data_base_atual": calendar.data_atual().isoformat(),
        "fuso_horario": "America/Sao_Paulo",
        "estoque_carregado": total_reg > 0,
        "fundo": fundo.nome if fundo else "ANTECIPE FIDC",
        "total_registros_estoque": total_reg,
        "rule_version": versao_ativa.version_number if versao_ativa else None,
        "cadastro_fonte": carregar_cadastro()[1],
        "upload_capabilities": {
            "http_max_bytes": settings.MAX_UPLOAD_SIZE_BYTES,
            "bulk_max_bytes": settings.MAX_STREAM_FILE_BYTES,
            "max_records": settings.MAX_STREAM_RECORDS,
            "bulk_transport": "websocket",
            "bulk_path": "/api/simulations/stream"
        }
    }
    if settings.PUBLIC_DEMO_MODE:
        health_resp["aviso_demo_publica"] = (
            "Demonstração pública efêmera: ambiente serverless isolado com carteira e cadastro sintéticos."
        )
    return health_resp


class LimitedRawIO(io.RawIOBase):
    """RawIO wrapper que limita a contagem de bytes em streaming com compatibilidade com TextIOWrapper."""
    def __init__(self, stream, max_bytes: int):
        self.stream = stream
        self.max_bytes = max_bytes
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        data = self.stream.read(len(b))
        if not data:
            return 0
        n = len(data)
        self.bytes_read += n
        if self.bytes_read > self.max_bytes:
            raise HTTPException(
                status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"codigo": "ARQUIVO_MUITO_GRANDE", "mensagem": f"O tamanho do arquivo excede o limite máximo permitido de {self.max_bytes} bytes."}
            )
        b[:n] = data
        return n


@router.post("/simulations", response_model=SimulationResponseSchema)
async def post_simulation_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tipo_analise: str = Query("novas_operacoes", pattern="^(novas_operacoes|carteira)$"),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "FORMATO_ARQUIVO_INVALIDO", "mensagem": "O arquivo deve ser um CSV válido com codificação UTF-8."}
        )

    try:
        limited_raw = LimitedRawIO(file.file, max_bytes=settings.MAX_UPLOAD_SIZE_BYTES)
        buffered = io.BufferedReader(limited_raw)
        text_stream = io.TextIOWrapper(buffered, encoding="utf-8-sig", errors="strict")
        itens_iter = iterar_csv_recebiveis(text_stream, delimitador=";")
        
        service = SimulationService(db)
        sim_id, envelope = service.executar_simulacao_lote(itens_iter, tipo_analise=tipo_analise)
        return envelope
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "CODIFICACAO_INVALIDA", "mensagem": "O arquivo deve estar codificado em UTF-8 válido."}
        )
    except TotalExcedeCapacidadeError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"codigo": "TOTAL_EXCEDE_CAPACIDADE", "mensagem": str(e)}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"codigo": "ERRO_PROCESSAMENTO", "mensagem": str(e)}
        )


@router.get("/simulations/{simulation_id}", response_model=SimulationResponseSchema)
@router.get("/simulations/{simulation_id}/items", response_model=SimulationResponseSchema)
def get_simulation(
    simulation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status_filtro: Optional[str] = Query(None, alias="status", pattern="^(aprovado|recusado|APROVADA|RECUSADA|CARTEIRA_HISTORICA)$"),
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    sim_repo = SimulationsRepository(db)
    sim = sim_repo.obter_simulacao(simulation_id)
    if not sim:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"codigo": "SIMULACAO_NAO_ENCONTRADA", "mensagem": "Simulação não encontrada com o ID fornecido."}
        )

    itens_db, total_itens_filtrados = sim_repo.listar_itens_paginados(
        simulation_id=simulation_id,
        page=page,
        page_size=page_size,
        status=status_filtro,
        reason=reason
    )

    total_pages = (total_itens_filtrados + page_size - 1) // page_size if total_itens_filtrados else 1

    resultados = serializar_pagina(db, simulation_id, itens_db)
    analytics = obter_analytics(db, simulation_id)

    avisos = json.loads(sim.avisos_json) if hasattr(sim, "avisos_json") and sim.avisos_json else []

    return {
        "analytics": analytics,
        "resumo_motivos": {
            m["codigo"]: m["quantidade"] for m in (analytics.get("motivos", []) if analytics else [])
        },
        "tipo_analise": analytics["tipo_analise"] if analytics else "novas_operacoes",
        "simulation_id": sim.id,
        "rule_version": sim.rule_version.version_number,
        "rule_version_id": sim.rule_version_id,
        "data_base": sim.data_base.isoformat(),
        "status": sim.status,
        "total_itens": sim.total_itens,
        "aprovados": sim.aprovados,
        "recusados": sim.recusados,
        "total_nominal": f"{Decimal(str(sim.total_nominal)):.2f}",
        "total_liquido": f"{Decimal(str(sim.total_liquido)):.2f}",
        "resultados": resultados,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total_itens_filtrados,
            "total_pages": total_pages,
        },
        "auditoria": {
            "cadastro_fonte": sim.cadastro_fonte,
            "carteira_referencia": sim.carteira_referencia,
            "configuration_hash": sim.configuration_hash,
        },
        "avisos": avisos
    }


@router.get("/simulations/{simulation_id}/analytics")
def get_simulation_analytics(simulation_id: str, db: Session = Depends(get_db)):
    if not SimulationsRepository(db).obter_simulacao(simulation_id):
        raise HTTPException(404, detail={"codigo": "SIMULACAO_NAO_ENCONTRADA", "mensagem": "Simulação não encontrada."})
    analytics = obter_analytics(db, simulation_id)
    if not analytics:
        raise HTTPException(409, detail={"codigo": "REPROCESSAMENTO_NECESSARIO", "mensagem": "Reprocesse a simulação para gerar as novas análises."})
    return analytics


@router.get("/simulations/{simulation_id}/export")
def get_simulation_export(simulation_id: str, format: str = Query("csv", pattern="^(csv|pdf|violacoes)$"), db: Session = Depends(get_db)):
    get_simulation_analytics(simulation_id, db)
    bind = db.get_bind()
    def body():
        # Sessão própria: compatível com cleanup de Depends antes do StreamingResponse.
        with Session(bind=bind) as session:
            sim = SimulationsRepository(session).obter_simulacao(simulation_id)
            chunks, _ = exportar(session, sim, format)
            yield from chunks
    ext = "pdf" if format == "pdf" else "csv"
    return StreamingResponse(body(), media_type="application/pdf" if ext == "pdf" else "text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="antecipe-{simulation_id}-{format}.{ext}"',
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/receivables/evaluate", response_model=SimulationResponseSchema)
def post_receivables_evaluate(
    payload: ReceivablesEvaluateRequestSchema,
    db: Session = Depends(get_db)
):
    if not payload.recebiveis:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "PAYLOAD_VAZIO", "mensagem": "A lista de recebíveis não pode estar vazia."}
        )

    hoje = calendar.data_atual()
    dt_base = hoje
    if payload.data_base:
        dt_base = parse_data_br(payload.data_base)
        if not dt_base:
            try:
                dt_base = datetime.fromisoformat(payload.data_base).date()
            except Exception:
                raise HTTPException(
                    status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"codigo": "DATA_BASE_INVALIDA", "mensagem": f"Data-base '{payload.data_base}' informada no payload é inválida."}
                )
        if dt_base != hoje:
            raise HTTPException(status_code=422, detail={
                "codigo": "DATA_BASE_INVALIDA",
                "mensagem": "Novas simulações usam a data atual de Brasília. Omita data_base para atualização automática."
            })

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "NOME_FUNDO", "DOC_FUNDO", "NOME_CEDENTE", "DOC_CEDENTE",
        "NOME_SACADO", "DOC_SACADO", "NU_DOCUMENTO", "TIPO_RECEBIVEL",
        "VALOR_NOMINAL", "DATA_VENCIMENTO_ORIGINAL", "DATA_AQUISICAO"
    ])
    for r in payload.recebiveis:
        writer.writerow([
            r.NOME_FUNDO or "ANTECIPE FIDC",
            r.DOC_FUNDO or "92.234.400/0001-80",
            r.NOME_CEDENTE,
            r.DOC_CEDENTE,
            r.NOME_SACADO,
            r.DOC_SACADO,
            r.NU_DOCUMENTO,
            r.TIPO_RECEBIVEL,
            r.VALOR_NOMINAL,
            r.DATA_VENCIMENTO_ORIGINAL,
            r.DATA_AQUISICAO or ""
        ])

    output.seek(0)
    itens_iter = iterar_csv_recebiveis(output, delimitador=";")

    service = SimulationService(db)
    try:
        sim_id, envelope = service.executar_simulacao_lote(
            itens_iter,
            data_base_override=dt_base
        )
        return envelope
    except TotalExcedeCapacidadeError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"codigo": "TOTAL_EXCEDE_CAPACIDADE", "mensagem": str(e)}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"codigo": "ERRO_PROCESSAMENTO", "mensagem": str(e)}
        )


@router.get("/rules")
def get_active_rules(db: Session = Depends(get_db)):
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    rules_repo = RulesRepository(db)
    versao = rules_repo.obter_versao_ativa(fundo.id) if fundo else None
    if not versao:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"codigo": "REGRA_NAO_ENCONTRADA", "mensagem": "Nenhuma regra ativa configurada."}
        )
    return json.loads(versao.configuration_json)


@router.get("/rules/versions")
def get_rule_versions(db: Session = Depends(get_db)):
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    rules_repo = RulesRepository(db)
    versoes = rules_repo.listar_versoes(fundo.id) if fundo else []

    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "created_at": v.created_at.isoformat(),
            "created_by": v.created_by,
            "change_reason": v.change_reason,
            "is_active": is_act,
            "configuration_hash": v.configuration_hash,
        }
        for v, is_act in versoes
    ]


@router.post("/rules/versions")
def post_create_rule_version(
    payload: RuleVersionCreateSchema,
    admin_token: str = Depends(verificar_admin_token),
    db: Session = Depends(get_db)
):
    cfg = payload.configuration
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    if not fundo:
        raise HTTPException(status_code=404, detail="Fundo principal não encontrado.")

    try:
        carregar_configuracao(cfg, calendar.data_atual())
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"codigo": "CONFIGURACAO_INVALIDA", "mensagem": f"Configuração de regras rejeitada: {exc}"}
        )

    cfg_fundo = cfg.get("fundo", {})
    if isinstance(cfg_fundo, dict):
        cnpj_cfg = normalizar_documento(cfg_fundo.get("cnpj", ""))
        if cnpj_cfg and cnpj_cfg != fundo.cnpj:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"codigo": "FUNDO_INCOMPATIVEL", "mensagem": f"O CNPJ do fundo na configuração ({cnpj_cfg}) não corresponde ao fundo ativo ({fundo.cnpj})."}
            )

    rules_repo = RulesRepository(db)
    try:
        nova_versao = rules_repo.criar_versao(
            fundo_id=fundo.id,
            config_dict=cfg,
            created_by="admin",
            change_reason=payload.change_reason
        )
        return {
            "id": nova_versao.id,
            "version_number": nova_versao.version_number,
            "configuration_hash": nova_versao.configuration_hash,
            "created_at": nova_versao.created_at.isoformat(),
            "change_reason": nova_versao.change_reason,
        }
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"codigo": "CONFLITO_CONCORRENCIA_VERSAO", "mensagem": "Conflito ao criar versão: uma nova versão já foi publicada simultaneamente. Tente novamente."}
        )


@router.post("/rules/versions/{version_id}/activate")
def post_activate_rule_version(
    version_id: int,
    expected_active_version_id: Optional[int] = Query(None),
    admin_token: str = Depends(verificar_admin_token),
    db: Session = Depends(get_db)
):
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    if not fundo:
        raise HTTPException(status_code=404, detail="Fundo principal não encontrado.")

    rules_repo = RulesRepository(db)
    sucesso, msg_erro = rules_repo.ativar_versao(
        fundo_id=fundo.id,
        version_id=version_id,
        actor="admin",
        versao_esperada_anterior_id=expected_active_version_id
    )
    if not sucesso:
        if "Conflito" in (msg_erro or ""):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={"codigo": "CONFLITO_CONCORRENCIA_ATIVACAO", "mensagem": msg_erro}
            )
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"codigo": "VERSAO_NAO_ENCONTRADA", "mensagem": msg_erro or "Versão não encontrada."}
        )
    return {"status": "activated", "version_id": version_id}


@router.get("/demo.csv")
def get_demo_csv():
    demo_path = Path(__file__).resolve().parent.parent.parent / "samples" / "demo.csv"
    if not demo_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo demo.csv não localizado.")
    cadastro, fonte = carregar_cadastro()
    if fonte.startswith("SIMULADO_CSV"):
        # O exemplo de aprovação também precisa existir na fonte cadastral selecionada.
        active = next((doc for doc, situacao in cadastro.items() if situacao == "ATIVA" and doc[:8] not in {"04252011", "11222333", "22333444", "73410326"}), None)
        if active:
            with demo_path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream, delimiter=";")
                output = io.StringIO(newline="")
                writer = csv.DictWriter(output, fieldnames=reader.fieldnames, delimiter=";")
                writer.writeheader()
                for row in reader:
                    if normalizar_documento(row["DOC_SACADO"]) == "04252011000110" and row["NU_DOCUMENTO"] != "NF-HIST-01":
                        row["DOC_SACADO"] = active
                    writer.writerow(row)
            return PlainTextResponse("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="demo.csv"', "Cache-Control": "no-store"})
    return FileResponse(
        path=str(demo_path),
        filename="demo.csv",
        media_type="text/csv"
    )


@router.get("/portfolio/summary")
def get_portfolio_summary(db: Session = Depends(get_db)):
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    receivables_repo = ReceivablesRepository(db)
    resumo = receivables_repo.obter_resumo_portfolio(fundo.id) if fundo else {}
    
    if settings.PUBLIC_DEMO_MODE:
        avisos = resumo.get("avisos", [])
        avisos.append(
            "Demonstração pública: carteira e cadastro sintéticos. "
            "Resultados temporários por instância e podem desaparecer. Não envie dados reais."
        )
        resumo["avisos"] = avisos
        
    return resumo


@router.put("/rules/active")
def put_update_active_rules_from_ui(
    payload: RuleVersionCreateSchema,
    db: Session = Depends(get_db)
):
    """
    Permite ao cliente configurar e ativar os parâmetros de regras diretamente pelo Frontend,
    sem precisar editar o arquivo JSON manualmente no servidor.
    Valida estritamente todos os parâmetros, registra nova versão auditável e a ativa.
    """
    cfg = payload.configuration
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    if not fundo:
        raise HTTPException(status_code=404, detail="Fundo principal não encontrado.")

    try:
        carregar_configuracao(cfg, date(2026, 10, 22))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"codigo": "CONFIGURACAO_INVALIDA", "mensagem": f"Configuração de regras rejeitada: {exc}"}
        )

    cfg_fundo = cfg.get("fundo", {})
    if isinstance(cfg_fundo, dict):
        cnpj_cfg = normalizar_documento(cfg_fundo.get("cnpj", ""))
        if cnpj_cfg and cnpj_cfg != fundo.cnpj:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"codigo": "FUNDO_INCOMPATIVEL", "mensagem": f"O CNPJ do fundo na configuração ({cnpj_cfg}) não corresponde ao fundo ativo ({fundo.cnpj})."}
            )

    rules_repo = RulesRepository(db)
    nova_versao = rules_repo.criar_versao(
        fundo_id=fundo.id,
        config_dict=cfg,
        created_by="portal_front",
        change_reason=payload.change_reason or "Atualização de parâmetros via Frontend"
    )
    rules_repo.ativar_versao(
        fundo_id=fundo.id,
        version_id=nova_versao.id,
        actor="portal_front",
    )
    return {
        "status": "activated",
        "id": nova_versao.id,
        "version_number": nova_versao.version_number,
        "configuration_hash": nova_versao.configuration_hash,
        "created_at": nova_versao.created_at.isoformat(),
        "change_reason": nova_versao.change_reason,
        "configuration": json.loads(nova_versao.configuration_json),
    }


@router.post("/rules/reset-default")
def post_reset_default_rules_from_ui(db: Session = Depends(get_db)):
    """
    Restaura os parâmetros originais do regulamento ANTECIPE FIDC (validadores_antecipe.json)
    como a versão ativa no banco de dados.
    """
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    if not fundo:
        raise HTTPException(status_code=404, detail="Fundo principal não encontrado.")

    json_path = Path(settings.VALIDADORES_JSON_PATH)
    if not json_path.is_file():
        # Mesmo fallback de importer.inicializar_fundos_e_regras: JSON oficial na raiz do repositório.
        json_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "validadores_antecipe.json"
    if not json_path.is_file():
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"codigo": "REGRA_PADRAO_NAO_ENCONTRADA", "mensagem": "Arquivo de regras padrão do fundo não localizado no servidor."}
        )
    cfg_default = json.loads(json_path.read_text(encoding="utf-8"), parse_float=Decimal)

    rules_repo = RulesRepository(db)
    nova_versao = rules_repo.criar_versao(
        fundo_id=fundo.id,
        config_dict=cfg_default,
        created_by="portal_front",
        change_reason="Restauração dos parâmetros padrão do regulamento ANTECIPE FIDC"
    )
    rules_repo.ativar_versao(
        fundo_id=fundo.id,
        version_id=nova_versao.id,
        actor="portal_front",
    )
    return {
        "status": "activated",
        "id": nova_versao.id,
        "version_number": nova_versao.version_number,
        "configuration_hash": nova_versao.configuration_hash,
        "created_at": nova_versao.created_at.isoformat(),
        "change_reason": nova_versao.change_reason,
        "configuration": json.loads(nova_versao.configuration_json),
    }


@router.get("/portfolio/economic-group/{raiz_cnpj}")
def get_economic_group_xray(raiz_cnpj: str, db: Session = Depends(get_db)):
    fundo = db.query(FundModel).filter(FundModel.nome.ilike("%ANTECIPE%")).first()
    if not fundo:
        raise HTTPException(status_code=404, detail="Fundo principal não encontrado.")
    receivables_repo = ReceivablesRepository(db)
    return receivables_repo.obter_raio_x_grupo_economico(fundo.id, raiz_cnpj)


@router.get("/samples/{rows}")
def get_sample_batch_csv(rows: int):
    if rows not in (100, 1000, 10000, 100000):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "TAMANHO_LOTE_INVALIDO", "mensagem": "Tamanho de lote suportado: 100, 1000, 10000 ou 100000."}
        )
    lote_path = Path(__file__).resolve().parent.parent.parent / "samples" / "lotes" / f"lote_simulacao_{rows}.csv"
    if not lote_path.is_file():
        _, salvar_lote_csv = _gerador_sintetico()
        salvar_lote_csv(lote_path, rows, seed_tag=f"L{rows}")
    return FileResponse(
        path=str(lote_path),
        filename=f"lote_simulacao_{rows}.csv",
        media_type="text/csv"
    )


@router.post("/simulations/sample/{rows}", response_model=SimulationResponseSchema)
def post_simulate_sample_batch(rows: int, db: Session = Depends(get_db)):
    if rows not in (100, 1000, 10000, 100000):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"codigo": "TAMANHO_LOTE_INVALIDO", "mensagem": "Tamanho de lote suportado: 100, 1000, 10000 ou 100000."}
        )
    iterar_linhas_lote_sintetico, _ = _gerador_sintetico()
    buf = io.StringIO("".join(iterar_linhas_lote_sintetico(rows, seed_tag=f"L{rows}")))
    itens_iter = iterar_csv_recebiveis(buf, delimitador=";")
    service = SimulationService(db)
    _, envelope = service.executar_simulacao_lote(itens_iter)
    return envelope


@router.post("/simulations/what-if")
def post_simulation_what_if(
    payload: WhatIfSimulationRequestSchema,
    db: Session = Depends(get_db)
):
    try:
        iterar_linhas_lote_sintetico, _ = _gerador_sintetico()
        buf = io.StringIO("".join(iterar_linhas_lote_sintetico(payload.sample_rows, seed_tag=f"WHATIF{payload.sample_rows}")))
        itens_lista = list(iterar_csv_recebiveis(buf, delimitador=";"))
        service = SimulationService(db)
        return service.executar_simulacao_what_if(payload.configuration, itens_lista)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"codigo": "CONFIGURACAO_INVALIDA", "mensagem": f"Parâmetros 'What-If' inválidos: {exc}"}
        )
