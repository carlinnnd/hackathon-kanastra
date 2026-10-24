"""
Rotas de Upload Massivo via WebSocket (Streaming Transacional até 1 Milhão de Linhas).
Contrato rigoroso definido em antecipe-bulk-upload:
- Endpoint: wss://<host>/api/simulations/stream
- Mensagens de controle: start, ready, ack, finish, progress, complete, query, page, audit, error.
- Controle de concorrência: semáforo de no máximo 1 conexão de ingestão pesada simultânea por instância.
- Em PUBLIC_DEMO_MODE=True: isola em SQLite :memory: efêmero exclusivo por conexão e descarta com engine.dispose() ao encerrar.
- Hash de auditoria canônico decisions_sha256: linha|aprovado|primeiro_codigo|nominal|liquido via SQL Core streaming (sem OOM).
- Monitor de desconexão ativa durante await worker após FINISH.
- Fila assíncrona serializada para mensagens de progresso com drenagem antes do COMPLETE.
- Agregação de auditoria em centavos exatos: SUM(CAST(ROUND(valor * 100, 0) AS BigInteger)).
"""
import asyncio
import base64
import codecs
import hashlib
import json
import os
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import create_engine, select, func, case, cast, BigInteger, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ..config import settings
from ..domain.ingestion import iterar_csv_recebiveis
from ..infrastructure.database.session import Base, SessionLocal
from ..infrastructure.database.models import FundModel, ReceivableModel, SimulationModel, SimulationItemModel
from ..infrastructure.repositories.simulations_repository import SimulationsRepository
from ..application.simulation_service import SimulationService, TotalExcedeCapacidadeError
from ..application.result_reporting import serializar_pagina
from ..application.exports import exportar
from ..application.stream_upload import BoundedStreamTextIO
from ..logger import logger

bulk_router = APIRouter(tags=["Bulk Upload Stream"])

# Semáforo global por processo para limitar a 1 carga pesada concorrente durante toda a sessão (proteção 2GB RAM)
_CONCURRENT_STREAM_LOCK = asyncio.Semaphore(1)


def calcular_decisions_sha256_core(db, simulation_id: str) -> str:
    """
    Calcula decisions_sha256 via SQL Core streaming em chunks (yield_per/fetchmany),
    evitando OOM ao auditar até 1 milhão de registros:
    linha|1-ou-0|primeiro_codigo_ou_vazio|nominal_2_casas_ou_vazio|liquido_2_casas_ou_vazio\n
    """
    stmt = (
        select(
            SimulationItemModel.linha,
            SimulationItemModel.aprovado,
            SimulationItemModel.motivos_json,
            SimulationItemModel.valor_nominal,
            SimulationItemModel.valor_liquido,
        )
        .where(SimulationItemModel.simulation_id == simulation_id)
        .order_by(SimulationItemModel.linha.asc())
        .execution_options(stream_results=True, max_row_buffer=1000)
    )

    hasher = hashlib.sha256()
    result = db.execute(stmt)

    while chunk := result.fetchmany(1000):
        for linha, aprovado, motivos_json, val_nom, val_liq in chunk:
            aprov_digit = "1" if aprovado else "0"

            primeiro_codigo = ""
            if motivos_json:
                try:
                    motivos = json.loads(motivos_json)
                    if motivos:
                        primeiro_codigo = motivos[0].get("codigo", "")
                except Exception:
                    pass

            nom_str = f"{Decimal(str(val_nom)):.2f}" if val_nom is not None else ""
            liq_str = f"{Decimal(str(val_liq)):.2f}" if val_liq is not None else ""

            line_str = f"{linha}|{aprov_digit}|{primeiro_codigo}|{nom_str}|{liq_str}\n"
            hasher.update(line_str.encode("utf-8"))

    return hasher.hexdigest()


def obter_audit_agregado_core(db, simulation_id: str) -> Tuple[int, int, int, str, str]:
    """
    Consulta contagens e somas reais persistidas no banco via SQL Core.
    Soma em centavos inteiros via CAST(ROUND(valor * 100, 0) AS BigInteger) para eliminar float em SQLite.
    """
    nom_cent_expr = cast(func.round(SimulationItemModel.valor_nominal * 100, 0), BigInteger)
    liq_cent_expr = cast(func.round(SimulationItemModel.valor_liquido * 100, 0), BigInteger)

    stmt = (
        select(
            func.count(SimulationItemModel.id),
            func.coalesce(func.sum(case((SimulationItemModel.aprovado == True, 1), else_=0)), 0),
            func.coalesce(func.sum(case((SimulationItemModel.aprovado == False, 1), else_=0)), 0),
            func.coalesce(func.sum(nom_cent_expr), 0),
            func.coalesce(func.sum(liq_cent_expr), 0),
        )
        .where(SimulationItemModel.simulation_id == simulation_id)
    )
    count, approved, rejected, tot_nom_cents, tot_liq_cents = db.execute(stmt).first()
    tot_nom = Decimal(int(tot_nom_cents)) / Decimal(100)
    tot_liq = Decimal(int(tot_liq_cents)) / Decimal(100)
    return (
        int(count),
        int(approved),
        int(rejected),
        f"{tot_nom:.2f}",
        f"{tot_liq:.2f}",
    )


def criar_sessao_isolada_para_conexao():
    """
    Cria sessão de banco de dados para a conexão:
    - Se PUBLIC_DEMO_MODE=True: cria SQLite :memory: exclusivo com StaticPool e seed sintético.
    - Se modo normal/local: usa SessionLocal() padrão do banco configurado.
    """
    if settings.PUBLIC_DEMO_MODE:
        eng = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=eng)
        SessionCls = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = SessionCls()

        from ..application.importer import inicializar_fundos_e_regras
        fundo = inicializar_fundos_e_regras(db, settings.VALIDADORES_JSON_PATH)
        titulos_sinteticos = [
            ("04252011000110", "COMERCIAL ALPHA LTDA", Decimal("30000.00"), "1"),
            ("73410326000122", "SERVICOS BETA LTDA", Decimal("20000.00"), "2"),
            ("11222333000181", "INDUSTRIA GAMA SA", Decimal("50000.00"), "3"),
            ("22333444000192", "DISTRIBUIDORA DELTA", Decimal("400000.00"), "4"),
        ]
        for doc, nome, val, idx in titulos_sinteticos:
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
        return db, eng
    else:
        db = SessionLocal()
        return db, None


@bulk_router.websocket("/api/simulations/stream")
async def websocket_simulation_stream(websocket: WebSocket):
    await websocket.accept()

    try:
        msg_init = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
    except asyncio.TimeoutError:
        await websocket.send_json({
            "type": "error",
            "codigo": "TIMEOUT_START",
            "mensagem": "Tempo limite de 10 segundos excedido aguardando handshake inicial."
        })
        await websocket.close()
        return
    except Exception:
        await websocket.send_json({
            "type": "error",
            "codigo": "MENSAGEM_INVALIDA",
            "mensagem": "Payload de handshake inválido ou malformado."
        })
        await websocket.close()
        return

    if not isinstance(msg_init, dict) or msg_init.get("type") != "start":
        await websocket.send_json({
            "type": "error",
            "codigo": "MENSAGEM_INVALIDA",
            "mensagem": "Primeira mensagem deve ser um objeto JSON do tipo 'start'."
        })
        await websocket.close()
        return

    tipo_analise = msg_init.get("tipo_analise", "novas_operacoes")
    if tipo_analise not in {"novas_operacoes", "carteira"}:
        await websocket.send_json({"type": "error", "codigo": "TIPO_ANALISE_INVALIDO", "mensagem": "Selecione novas operações ou carteira histórica."})
        await websocket.close()
        return
    declared_size = msg_init.get("size_bytes")
    if isinstance(declared_size, bool) or not isinstance(declared_size, int) or declared_size <= 0:
        await websocket.send_json({
            "type": "error",
            "codigo": "TAMANHO_ARQUIVO_INVALIDO",
            "mensagem": "Campo size_bytes deve ser um número inteiro positivo."
        })
        await websocket.close()
        return

    filename = str(msg_init.get("filename", "")).lower()
    protocol_version = msg_init.get("protocol_version")
    if isinstance(protocol_version, bool) or protocol_version != 1:
        await websocket.send_json({
            "type": "error",
            "codigo": "PROTOCOLO_INCOMPATIVEL",
            "mensagem": "Versão de protocolo inválida. Esperado: 1."
        })
        await websocket.close()
        return

    if not filename.endswith(".csv"):
        await websocket.send_json({
            "type": "error",
            "codigo": "FORMATO_ARQUIVO_INVALIDO",
            "mensagem": "O arquivo deve possuir extensão .csv."
        })
        await websocket.close()
        return

    if declared_size > settings.MAX_STREAM_FILE_BYTES:
        await websocket.send_json({
            "type": "error",
            "codigo": "TAMANHO_ARQUIVO_INVALIDO",
            "mensagem": f"Tamanho do arquivo excede o limite máximo permitido de {settings.MAX_STREAM_FILE_BYTES} bytes."
        })
        await websocket.close()
        return

    # Limita concorrência pesada mantendo o semáforo durante toda a sessão (protege 2GB RAM de banco em memória)
    if _CONCURRENT_STREAM_LOCK.locked():
        await websocket.send_json({
            "type": "error",
            "codigo": "CONCORRENCIA_EXCEDIDA",
            "mensagem": "Outra carga massiva está em processamento nesta instância. Tente novamente em instantes."
        })
        await websocket.close()
        return

    async with _CONCURRENT_STREAM_LOCK:
        db, custom_engine = criar_sessao_isolada_para_conexao()
        sim_id_sessao: Optional[str] = None
        envelope_sessao: Optional[dict] = None

        # Lock do sender para serializar envios de ACK, progress e responses sem corridas
        ws_sender_lock = asyncio.Lock()

        # 2. Responde com READY
        async with ws_sender_lock:
            await websocket.send_json({
                "type": "ready",
                "chunk_bytes": settings.STREAM_CHUNK_BYTES,
                "window_bytes": settings.STREAM_WINDOW_BYTES,
                "max_file_bytes": settings.MAX_STREAM_FILE_BYTES,
                "max_records": settings.MAX_STREAM_RECORDS,
            })

        queue = asyncio.Queue(maxsize=16)
        loop = asyncio.get_running_loop()
        stream_adapter = BoundedStreamTextIO(queue=queue, loop=loop)
        utf8_decoder = codecs.getincrementaldecoder("utf-8-sig")(errors="strict")

        received_bytes_total = 0
        finish_received = False
        client_disconnected = False

        # Fila assíncrona para serializar mensagens de progresso
        progress_queue = asyncio.Queue()

        async def progress_sender_loop():
            while True:
                rows = await progress_queue.get()
                if rows is None:
                    break
                try:
                    async with ws_sender_lock:
                        await websocket.send_json({
                            "type": "progress",
                            "rows_processed": rows
                        })
                except Exception:
                    break

        progress_sender_task = asyncio.create_task(progress_sender_loop())

        def progress_cb(rows_processed: int):
            if not client_disconnected and not stream_adapter.aborted:
                loop.call_soon_threadsafe(progress_queue.put_nowait, rows_processed)

        def cancel_check_fn() -> bool:
            return client_disconnected or stream_adapter.aborted

        def gerador_controlado():
            raw_iter = iterar_csv_recebiveis(stream_adapter, delimitador=";")
            for item in raw_iter:
                if client_disconnected or stream_adapter.aborted:
                    raise RuntimeError("Conexão interrompida pelo cliente durante o streaming.")
                yield item

            if not finish_received or client_disconnected or stream_adapter.aborted:
                raise ValueError("Fluxo CSV encerrado antes da mensagem finish de confirmação ou com cliente desconectado.")

        def run_worker():
            service = SimulationService(db)
            return service.executar_simulacao_lote(
                gerador_controlado(),
                progress_callback=progress_cb,
                max_records=settings.MAX_STREAM_RECORDS,
                cancel_check=cancel_check_fn,
                tipo_analise=tipo_analise,
            )

        worker_task = asyncio.create_task(asyncio.to_thread(run_worker))

        async def receiver_loop():
            nonlocal received_bytes_total, finish_received, client_disconnected
            while True:
                data = await websocket.receive()
                if data.get("type") == "websocket.receive":
                    if "bytes" in data and data["bytes"]:
                        chunk_b = data["bytes"]
                        if len(chunk_b) > settings.STREAM_CHUNK_BYTES:
                            raise ValueError("Chunk excede chunk_bytes permitido.")

                        received_bytes_total += len(chunk_b)
                        if received_bytes_total > declared_size:
                            raise ValueError("Bytes recebidos excedem o total declarado no handshake inicial.")

                        text_chunk = utf8_decoder.decode(chunk_b, final=False)
                        if text_chunk:
                            await queue.put(text_chunk)

                        async with ws_sender_lock:
                            await websocket.send_json({
                                "type": "ack",
                                "received_bytes": received_bytes_total
                            })

                    elif "text" in data and data["text"]:
                        payload = json.loads(data["text"])
                        if payload.get("type") == "finish":
                            if received_bytes_total != declared_size:
                                raise ValueError(
                                    f"Contagem de bytes incompleta: recebido {received_bytes_total} de {declared_size} declarados."
                                )
                            finish_received = True
                            tail = utf8_decoder.decode(b"", final=True)
                            if tail:
                                await queue.put(tail)
                            await queue.put(None)  # Sinal de EOF
                            break
                elif data.get("type") == "websocket.disconnect":
                    client_disconnected = True
                    raise WebSocketDisconnect()

        receiver_task = asyncio.create_task(receiver_loop())

        async def post_finish_disconnect_monitor():
            """Monitora ativamente desconexão do cliente durante o await worker_task após FINISH."""
            nonlocal client_disconnected
            while not worker_task.done():
                try:
                    data = await websocket.receive()
                    if data.get("type") == "websocket.disconnect":
                        client_disconnected = True
                        stream_adapter.abort()
                        break
                    elif data.get("type") == "websocket.receive":
                        # Comandos enviados antes do COMPLETE são rejeitados
                        async with ws_sender_lock:
                            await websocket.send_json({
                                "type": "error",
                                "codigo": "ORDEM_COMANDO_INVALIDA",
                                "mensagem": "Comandos não podem ser enviados enquanto a simulação está em consolidação."
                            })
                except WebSocketDisconnect:
                    client_disconnected = True
                    stream_adapter.abort()
                    break
                except Exception:
                    break

        post_finish_monitor_task: Optional[asyncio.Task] = None

        try:
            # Fase 1: ingestão e recepção até o FINISH
            done, pending = await asyncio.wait(
                [receiver_task, worker_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            if worker_task in done and worker_task.exception():
                stream_adapter.abort()
                receiver_task.cancel()
                try:
                    await receiver_task
                except (asyncio.CancelledError, Exception):
                    pass
                raise worker_task.exception()

            if receiver_task in done and receiver_task.exception():
                client_disconnected = True
                stream_adapter.abort()
                try:
                    await worker_task
                except Exception:
                    pass
                raise receiver_task.exception()

            # Fase 2: receiver concluiu com FINISH válido; monitora desconexão até worker_task encerrar
            if not worker_task.done():
                post_finish_monitor_task = asyncio.create_task(post_finish_disconnect_monitor())
                done_w, _ = await asyncio.wait(
                    [worker_task, post_finish_monitor_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                if post_finish_monitor_task in done_w and client_disconnected:
                    stream_adapter.abort()
                    try:
                        await worker_task
                    except Exception:
                        pass
                    raise WebSocketDisconnect()

            if post_finish_monitor_task and not post_finish_monitor_task.done():
                post_finish_monitor_task.cancel()
                try:
                    await post_finish_monitor_task
                except (asyncio.CancelledError, Exception):
                    pass

            # Aguarda worker concluir
            sim_id_sessao, envelope_sessao = await worker_task

            # Encerra e drena fila de progresso antes de emitir COMPLETE para evitar que progress ultrapasse o complete
            await progress_queue.put(None)
            await progress_sender_task

            # Envia mensagem COMPLETE
            async with ws_sender_lock:
                await websocket.send_json({
                    "type": "complete",
                    "simulation": envelope_sessao
                })

            # Loop de query e audit pós-conclusão
            while True:
                msg = await websocket.receive_json()
                msg_type = msg.get("type")

                if msg_type == "query":
                    req_id = msg.get("request_id", "")
                    try:
                        page = int(msg.get("page", 1))
                        page_size = int(msg.get("page_size", 50))
                    except (ValueError, TypeError):
                        page, page_size = 1, 50

                    page = max(1, page)
                    page_size = max(1, min(500, page_size))

                    status_filtro = msg.get("status")
                    if status_filtro == "todos":
                        status_filtro = None
                    reason_filtro = msg.get("reason")
                    if reason_filtro == "todos":
                        reason_filtro = None

                    sim_repo = SimulationsRepository(db)
                    itens_db, total_filtrados = sim_repo.listar_itens_paginados(
                        simulation_id=sim_id_sessao,
                        page=page,
                        page_size=page_size,
                        status=status_filtro,
                        reason=reason_filtro
                    )
                    total_pages = (total_filtrados + page_size - 1) // page_size if total_filtrados else 1

                    page_resultados = serializar_pagina(db, sim_id_sessao, itens_db)

                    envelope_page = dict(envelope_sessao)
                    envelope_page["resultados"] = page_resultados
                    envelope_page["pagination"] = {
                        "page": page,
                        "page_size": page_size,
                        "total": total_filtrados,
                        "total_pages": total_pages,
                    }

                    async with ws_sender_lock:
                        await websocket.send_json({
                            "type": "page",
                            "request_id": req_id,
                            "simulation": envelope_page
                        })

                elif msg_type == "export":
                    req_id = msg.get("request_id", "")
                    try:
                        sim = SimulationsRepository(db).obter_simulacao(sim_id_sessao)
                        chunks, media_type = exportar(db, sim, msg.get("format"))
                        # A sessão só exporta o ID que ela mesma processou. Nunca aceita ID do cliente.
                        async with ws_sender_lock:
                            for chunk in chunks:
                                for offset in range(0, len(chunk), 32768):
                                    await websocket.send_json({"type": "export_chunk", "request_id": req_id,
                                        "data": base64.b64encode(chunk[offset:offset + 32768]).decode("ascii")})
                            await websocket.send_json({"type": "export_complete", "request_id": req_id, "media_type": media_type})
                    except ValueError:
                        async with ws_sender_lock:
                            await websocket.send_json({"type": "error", "request_id": req_id,
                                "codigo": "EXPORTACAO_INVALIDA", "mensagem": "Use csv, violacoes ou pdf para exportar uma simulação concluída."})

                elif msg_type == "audit":
                    req_id = msg.get("request_id", "")
                    decisions_hash = calcular_decisions_sha256_core(db, sim_id_sessao)
                    count, approved, rejected, tot_nom, tot_liq = obter_audit_agregado_core(db, sim_id_sessao)

                    async with ws_sender_lock:
                        await websocket.send_json({
                            "type": "audit",
                            "request_id": req_id,
                            "count": count,
                            "approved": approved,
                            "rejected": rejected,
                            "total_nominal": tot_nom,
                            "total_liquido": tot_liq,
                            "decisions_sha256": decisions_hash
                        })

                elif msg_type == "close":
                    await websocket.close()
                    break

        except WebSocketDisconnect:
            client_disconnected = True
            stream_adapter.abort()
        except TotalExcedeCapacidadeError as exc:
            stream_adapter.abort()
            async with ws_sender_lock:
                await websocket.send_json({
                    "type": "error",
                    "codigo": "TOTAL_EXCEDE_CAPACIDADE",
                    "mensagem": str(exc)
                })
            await websocket.close()
        except ValueError as exc:
            stream_adapter.abort()
            async with ws_sender_lock:
                await websocket.send_json({
                    "type": "error",
                    "codigo": "ERRO_PROCESSAMENTO",
                    "mensagem": str(exc)
                })
            await websocket.close()
        except Exception as exc:
            stream_adapter.abort()
            logger.error("Erro no processamento do WebSocket stream", extra={"event": "STREAM_ERROR", "error_code": "STREAM_FAILED"})
            try:
                async with ws_sender_lock:
                    await websocket.send_json({
                        "type": "error",
                        "codigo": "ERRO_INTERNO",
                        "mensagem": "Falha interna durante o streaming de simulação."
                    })
                await websocket.close()
            except Exception:
                pass
        finally:
            stream_adapter.abort()
            if not receiver_task.done():
                receiver_task.cancel()
                try:
                    await receiver_task
                except (asyncio.CancelledError, Exception):
                    pass
            if post_finish_monitor_task and not post_finish_monitor_task.done():
                post_finish_monitor_task.cancel()
                try:
                    await post_finish_monitor_task
                except (asyncio.CancelledError, Exception):
                    pass
            if not progress_sender_task.done():
                progress_sender_task.cancel()
                try:
                    await progress_sender_task
                except (asyncio.CancelledError, Exception):
                    pass

            # Garante que worker finalizou rollback completamente antes de fechar a sessão e o engine
            try:
                await worker_task
            except Exception:
                pass

            db.close()
            if custom_engine:
                custom_engine.dispose()
