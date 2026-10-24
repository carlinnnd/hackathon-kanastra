"""
Harness de Benchmark de Streaming WebSocket (100k, 500k e 1.000.000 linhas).
Escopo Exclusivo de QA (Rubrica 5.2.1 Escalabilidade até 1 Milhão).
Contrato de Transporte v1 implementado conforme ticket antecipe-bulk-upload.

Correções Metodológicas e de Auditoria Incorporadas:
1. Baseline Seed Público Harmonizado:
   - Carteira inicial total: R$ 501.000,00
   - Seed 1: ALPHA (04252011000110) R$ 30.000,00 + HIST R$ 1.000,00 = R$ 31.000,00
   - Seed 2: BETA (73410326000122) R$ 20.000,00 (CNPJ real com DV inválido -> recusado por CNPJ_SACADO_VALIDO)
   - Seed 3: GAMA (11222333000181) R$ 50.000,00
   - Seed 4: DELTA (22333444000192) R$ 400.000,00 (não consta no cadastro DEMO -> recusado por SITUACAO_CADASTRAL_SACADO)
   Total: R$ 501.000,00 exato.
2. Parâmetros Reais Lidos do JSON:
   - Lê dinamicamente `validadores_antecipe.json` (taxa_mensal, base_dias, valor_minimo, prazo_maximo, percentual_maximo).
   - `NAO_VENCIDA`: vencimento < data_base (não <=).
   - Arredondamento financeiro: quantização direta do VALOR LÍQUIDO com ROUND_HALF_UP, e desconto = nominal - líquido.
3. Duplicidade Intra-Lote Real (Clone Completo da Identidade):
   - Clona exatamente cedente + sacado + tipo + nu_documento + data_vencimento e recalcula valor.
4. Resiliência do Client WebSocket:
   - Evento de sincronização (`window_available_event`) acorda o loop de envio sem polling cego.
   - Detecção imediata de exceção ou encerramento da task receptora (`recv_future`), abortando sem hang infinito.
   - Deadline total de 300 segundos com propagação limpa de erro.
5. Memória Transparente:
   - Em conexões remotas/hospedadas (sem `--server-pid`), RSS do servidor é reportado como `None` (não mensurado).
   - RSS cliente Win32 mede PeakWorkingSetSize do processo.
"""
import argparse
import asyncio
import copy
import csv
import hashlib
import json
import os
import platform
import sys
import time
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import websockets

DIRETORIO_BENCHMARKS = os.path.dirname(os.path.abspath(__file__))
CODEX_ANTECIPE_DIR = os.path.abspath(os.path.join(DIRETORIO_BENCHMARKS, ".."))
if CODEX_ANTECIPE_DIR not in sys.path:
    sys.path.insert(0, CODEX_ANTECIPE_DIR)

from backend.domain.cnpj import validar_cnpj


def calcular_hash_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def obter_hashes_fontes() -> Dict[str, str]:
    """
    Coleta hash SHA-256 de TODOS os arquivos de código do runtime e deploy com chaves
    estritamente relativas à RAIZ DO REPOSITÓRIO para evitar colisões e garantir rastreabilidade exaustiva.
    """
    hashes = {}
    repo_root = Path(CODEX_ANTECIPE_DIR).parent.parent
    backend_path = Path(CODEX_ANTECIPE_DIR) / "backend"

    # 1. Todos os arquivos .py sob Codex/antecipe/backend/ exceto testes e cache
    for p in sorted(backend_path.rglob("*.py")):
        partes = [part.lower() for part in p.parts]
        if "tests" in partes or "__pycache__" in partes or ".pytest_cache" in partes:
            continue
        rel_path = p.relative_to(repo_root).as_posix()
        hashes[rel_path] = calcular_hash_arquivo(str(p))

    # 2. Arquivos de configuração, manifesto e entrypoints adicionais na raiz e no projeto
    arquivos_extras = [
        repo_root / "app.py",
        repo_root / "requirements.txt",
        repo_root / "vercel.json",
        repo_root / ".python-version",
        repo_root / "validadores_antecipe.json",
        repo_root / ".vercelignore",
        Path(CODEX_ANTECIPE_DIR) / "backend" / "vercel_app.py",
        Path(CODEX_ANTECIPE_DIR) / "requirements.txt",
        Path(__file__),
    ]

    for p in arquivos_extras:
        if p.exists() and p.is_file():
            rel_path = p.relative_to(repo_root).as_posix()
            hashes[rel_path] = calcular_hash_arquivo(str(p))

    return dict(sorted(hashes.items()))


def get_process_memory_mb_by_pid(pid: int) -> Tuple[Optional[float], Optional[float]]:
    """Retorna (WorkingSetSize_MB, PeakWorkingSetSize_MB) via Win32 API. Retorna (None, None) se inacessível."""
    if not pid:
        return None, None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD),
                    ('PageFaultCount', wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if h_process:
                try:
                    counters = PROCESS_MEMORY_COUNTERS()
                    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                    if ctypes.windll.psapi.GetProcessMemoryInfo(h_process, ctypes.byref(counters), counters.cb):
                        rss = counters.WorkingSetSize / (1024 * 1024)
                        peak_rss = counters.PeakWorkingSetSize / (1024 * 1024)
                        return rss, peak_rss
                finally:
                    ctypes.windll.kernel32.CloseHandle(h_process)
        except Exception:
            pass
    return None, None


def carregar_parametros_validadores_reais() -> Dict:
    caminho = os.path.abspath(os.path.join(CODEX_ANTECIPE_DIR, "..", "..", "validadores_antecipe.json"))
    if not os.path.exists(caminho):
        caminho = "validadores_antecipe.json"
    with open(caminho, "r", encoding="utf-8") as f:
        data = json.load(f, parse_float=Decimal)

    params = {}
    for v in data.get("validadores", []):
        params[v["codigo"]] = v.get("parametros", {})
    params["precificacao"] = data.get("precificacao", {})
    return params


def gerar_csv_e_oraculo_stream(
    caminho_csv: str,
    total_linhas: int,
    data_base: date = date(2026, 10, 22)
) -> Tuple[str, int, Dict]:
    """
    Gera dataset sintético determinístico com clone integral para duplicatas intra-lote
    e calcula o oráculo semântico contra os parâmetros dinâmicos de validadores_antecipe.json.
    """
    params = carregar_parametros_validadores_reais()
    val_min_limite = Decimal(str(params.get("VALOR_MINIMO", {}).get("valor_minimo", "100.00")))
    tipos_aceitos = tuple(params.get("TIPO_RECEBIVEL", {}).get("tipos_aceitos", ["Duplicata", "Duplicata de Serviço"]))
    prazo_max_dias = int(params.get("PRAZO_MAXIMO", {}).get("prazo_maximo_dias", 180))
    conc_max_pct = Decimal(str(params.get("CONCENTRACAO_MAXIMA_SACADO", {}).get("percentual_maximo", "10.0")))

    prec = params.get("precificacao", {})
    taxa_mensal = Decimal(str(prec.get("taxa_mensal_percentual", "2.0"))) / Decimal("100")
    base_dias = int(prec.get("base_dias", 30))

    os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)
    headers = [
        "NOME_FUNDO", "DOC_FUNDO", "NOME_CEDENTE", "DOC_CEDENTE",
        "NOME_SACADO", "DOC_SACADO", "NU_DOCUMENTO", "TIPO_RECEBIVEL",
        "VALOR_NOMINAL", "DATA_VENCIMENTO_ORIGINAL", "DATA_AQUISICAO"
    ]

    doc_fundo = "92.234.400/0001-80"
    nome_fundo = "ANTECIPE FIDC"
    doc_cedente = "00.111.222/0001-33"
    nome_cedente = "CEDENTE STREAM S/A"

    # Mapeamento do cadastro demo efetivo (DEMO_CADASTRO_SINTETICO):
    # - 04252011000110 -> ATIVA
    # - 73410326000122 -> ATIVA (porém CNPJ matematicamente inválido -> barrado por CNPJ_SACADO_VALIDO)
    # - 11222333000181 -> ATIVA
    # - 22333444000192 -> NÃO CONSTA no mapa demo -> NAO_VERIFICADA -> barrado por SITUACAO_CADASTRAL_SACADO
    sacados = [
        ("COMERCIAL ALPHA LTDA", "04.252.011/0001-10", "ATIVA", "04252011"),
        ("SERVICOS BETA LTDA", "73.410.326/0001-22", "ATIVA", "73410326"),
        ("INDUSTRIA GAMA SA", "11.222.333/0001-81", "ATIVA", "11222333"),
        ("DISTRIBUIDORA DELTA", "22.333.444/0001-92", "NAO_VERIFICADA", "22333444"),
    ]

    # Baseline seed público exato: R$ 501.000,00
    carteira_total = Decimal("501000.00")
    exposicoes_raiz = {
        "04252011": Decimal("31000.00"),  # 30.000 + 1.000 hist
        "73410326": Decimal("20000.00"),
        "11222333": Decimal("50000.00"),
        "22333444": Decimal("400000.00"),
    }

    chaves_duplicidade_lote = set()

    oraculo_aprovados = 0
    oraculo_recusados = 0
    oraculo_total_nominal_submetido = Decimal("0.00")
    oraculo_total_nominal_aprovado = Decimal("0.00")
    oraculo_total_liquido_aprovado = Decimal("0.00")
    hasher_audit = hashlib.sha256()

    with open(caminho_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)

        # Buffer para duplicatas legítimas
        linha_anterior_identidade = None

        for i in range(1, total_linhas + 1):
            s_idx = i % len(sacados)
            s_nome, s_doc, s_sit, s_raiz = sacados[s_idx]

            tipo = "Duplicata" if i % 10 != 0 else "Boleto"
            doc_numero = f"BENCH-STREAM-{i:07d}"

            if i % 25 == 0:
                venc_str = "20/10/2026"
                venc_date = date(2026, 10, 20)
            elif i % 27 == 0:
                venc_str = "25/05/2027"
                venc_date = date(2027, 5, 25)
            else:
                venc_str = "20/11/2026"
                venc_date = date(2026, 11, 20)

            # Injeção de 1% de duplicatas intra-lote clonando integralmente todos os campos da identidade
            if i % 100 == 0 and linha_anterior_identidade is not None:
                doc_cedente_efetivo, s_doc, s_nome, s_sit, s_raiz, tipo, doc_numero, venc_str, venc_date = linha_anterior_identidade
            else:
                doc_cedente_efetivo = doc_cedente
                linha_anterior_identidade = (doc_cedente_efetivo, s_doc, s_nome, s_sit, s_raiz, tipo, doc_numero, venc_str, venc_date)

            valor_num = 150 + (i % 2000)
            valor_dec = Decimal(f"{valor_num:.2f}")
            valor_str = f"{valor_num:.2f}".replace(".", ",")
            oraculo_total_nominal_submetido += valor_dec

            linha_data = [
                nome_fundo, doc_fundo, nome_cedente, doc_cedente_efetivo,
                s_nome, s_doc, doc_numero, tipo,
                valor_str, venc_str, ""
            ]
            writer.writerow(linha_data)

            chave_dupl = f"{doc_cedente_efetivo}:{s_doc}:{tipo.upper()}:{doc_numero.strip().upper()}:{venc_date.isoformat()}"

            aprovado = True
            primeiro_motivo = ""

            # 1. Duplicidade intra-lote
            if chave_dupl in chaves_duplicidade_lote:
                aprovado = False
                primeiro_motivo = "DUPLICIDADE_LOTE"
            else:
                chaves_duplicidade_lote.add(chave_dupl)
                # 2. CNPJ Sacado Válido
                if not validar_cnpj(s_doc):
                    aprovado = False
                    primeiro_motivo = "CNPJ_SACADO_VALIDO"
                # 3. Situação Cadastral
                elif s_sit != "ATIVA":
                    aprovado = False
                    primeiro_motivo = "SITUACAO_CADASTRAL_SACADO"
                # 4. Tipo Recebível
                elif tipo not in tipos_aceitos:
                    aprovado = False
                    primeiro_motivo = "TIPO_RECEBIVEL"
                # 5. Valor Mínimo
                elif valor_dec < val_min_limite:
                    aprovado = False
                    primeiro_motivo = "VALOR_MINIMO"
                # 6. Não Vencida: data_vencimento < data_base
                elif venc_date < data_base:
                    aprovado = False
                    primeiro_motivo = "NAO_VENCIDA"
                # 7. Prazo Máximo
                elif (venc_date - data_base).days > prazo_max_dias:
                    aprovado = False
                    primeiro_motivo = "PRAZO_MAXIMO"
                else:
                    # 8. Concentração Máxima Sacado
                    nova_carteira = carteira_total + valor_dec
                    nova_exp = exposicoes_raiz.get(s_raiz, Decimal("0.00")) + valor_dec
                    if (nova_exp / nova_carteira) * Decimal("100") > conc_max_pct:
                        aprovado = False
                        primeiro_motivo = "CONCENTRACAO_MAXIMA_SACADO"
                    else:
                        carteira_total = nova_carteira
                        exposicoes_raiz[s_raiz] = nova_exp

            linha_csv = i + 1
            if aprovado:
                oraculo_aprovados += 1
                oraculo_total_nominal_aprovado += valor_dec
                dias = (venc_date - data_base).days
                fator_prazo = Decimal(dias) / Decimal(base_dias)
                fator_liquido = Decimal("1") - (taxa_mensal * fator_prazo)
                liquido_bruto = valor_dec * fator_liquido
                # Quantização direta do líquido com ROUND_HALF_UP conforme domain.pricing
                liq = liquido_bruto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if liq > valor_dec:
                    liq = valor_dec
                oraculo_total_liquido_aprovado += liq
                audit_line = f"{linha_csv}|1||{valor_dec:.2f}|{liq:.2f}\n"
            else:
                oraculo_recusados += 1
                audit_line = f"{linha_csv}|0|{primeiro_motivo}|{valor_dec:.2f}|\n"

            hasher_audit.update(audit_line.encode("utf-8"))

    hasher_file = hashlib.sha256()
    size_bytes = os.path.getsize(caminho_csv)
    with open(caminho_csv, "rb") as f:
        while chunk := f.read(65536):
            hasher_file.update(chunk)

    oraculo = {
        "total_linhas": total_linhas,
        "aprovados": oraculo_aprovados,
        "recusados": oraculo_recusados,
        "total_nominal_submetido": oraculo_total_nominal_submetido,
        "total_nominal_aprovado": oraculo_total_nominal_aprovado,
        "total_liquido": oraculo_total_liquido_aprovado,
        "decisions_sha256": hasher_audit.hexdigest(),
        "csv_sha256": hasher_file.hexdigest(),
        "size_bytes": size_bytes
    }
    return hasher_file.hexdigest(), size_bytes, oraculo


async def executar_benchmark_stream_ws(
    ws_url: str,
    caminho_csv: str,
    oraculo: Dict,
    server_pid: Optional[int] = None
) -> Dict:
    size_bytes = oraculo["size_bytes"]
    filename = os.path.basename(caminho_csv)

    rss_cli_inicio, _ = get_process_memory_mb_by_pid(os.getpid())
    rss_srv_inicio, _ = get_process_memory_mb_by_pid(server_pid)

    t0_ws = time.perf_counter()

    async with websockets.connect(
        ws_url,
        max_size=536870912,  # 512 MiB
        ping_interval=20,
        ping_timeout=30,
        close_timeout=30
    ) as ws:
        # 1. Start handshake
        start_payload = {
            "type": "start",
            "size_bytes": size_bytes,
            "filename": filename,
            "protocol_version": 1
        }
        await ws.send(json.dumps(start_payload))

        resp_ready = json.loads(await ws.recv())
        assert resp_ready["type"] == "ready", f"Servidor não respondeu ready: {resp_ready}"
        chunk_bytes = resp_ready.get("chunk_bytes", 262144)
        window_bytes = resp_ready.get("window_bytes", 4194304)

        acked_bytes = 0
        sent_bytes = 0
        simulation_envelope = None

        # Evento assíncrono para acordar o transmissor assim que houver espaço na janela
        window_available_event = asyncio.Event()
        receiver_error = None

        async def receiver_task():
            nonlocal acked_bytes, simulation_envelope, receiver_error
            try:
                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    mtype = msg.get("type")
                    if mtype == "ack":
                        acked_bytes = msg.get("received_bytes", acked_bytes)
                        window_available_event.set()
                    elif mtype == "progress":
                        pass
                    elif mtype == "complete":
                        simulation_envelope = msg.get("simulation")
                        window_available_event.set()
                        break
                    elif mtype == "error":
                        err_code = msg.get("codigo", "UNKNOWN")
                        err_msg = msg.get("mensagem", "Erro desconhecido")
                        receiver_error = RuntimeError(f"WebSocket Erro: [{err_code}] {err_msg}")
                        window_available_event.set()
                        break
            except Exception as exc:
                receiver_error = exc
                window_available_event.set()

        recv_future = asyncio.create_task(receiver_task())

        with open(caminho_csv, "rb") as f:
            while sent_bytes < size_bytes:
                if receiver_error is not None:
                    raise receiver_error
                if recv_future.done():
                    break

                # Janela cheia: aguarda evento de ACK sem polling cego
                while (sent_bytes - acked_bytes) >= window_bytes:
                    if receiver_error is not None:
                        raise receiver_error
                    if recv_future.done():
                        break
                    window_available_event.clear()
                    try:
                        await asyncio.wait_for(window_available_event.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        pass

                chunk = f.read(chunk_bytes)
                if not chunk:
                    break
                await ws.send(chunk)
                sent_bytes += len(chunk)

        # 4. Envia finish após todos os bytes transmitidos
        while acked_bytes < size_bytes:
            if receiver_error is not None:
                raise receiver_error
            if recv_future.done():
                break
            window_available_event.clear()
            try:
                await asyncio.wait_for(window_available_event.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

        if receiver_error is not None:
            raise receiver_error

        await ws.send(json.dumps({"type": "finish"}))

        # Aguarda complete com deadline máximo de 300 segundos
        await asyncio.wait_for(recv_future, timeout=300.0)
        if receiver_error is not None:
            raise receiver_error

        t1_ws = time.perf_counter()
        duracao_ws_total = t1_ws - t0_ws

        rss_cli_fim, peak_cli = get_process_memory_mb_by_pid(os.getpid())
        rss_srv_fim, peak_srv = get_process_memory_mb_by_pid(server_pid)

        assert simulation_envelope is not None, "Envelope de simulação não foi retornado pelo WebSocket!"
        assert simulation_envelope["status"] == "concluida"
        assert simulation_envelope["total_itens"] == oraculo["total_linhas"]
        assert simulation_envelope["aprovados"] == oraculo["aprovados"]
        assert simulation_envelope["recusados"] == oraculo["recusados"]

        obs_nominal = Decimal(simulation_envelope["total_nominal"])
        obs_liquido = Decimal(simulation_envelope["total_liquido"])
        assert obs_nominal == oraculo["total_nominal_submetido"], (
            f"Nominal ({obs_nominal}) != esperado ({oraculo['total_nominal_submetido']})"
        )
        assert obs_liquido == oraculo["total_liquido"], (
            f"Líquido ({obs_liquido}) != esperado ({oraculo['total_liquido']})"
        )

        # 5. Queries de primeira e última página NA MESMA SESSÃO WS
        t0_pag = time.perf_counter()
        await ws.send(json.dumps({
            "type": "query",
            "request_id": "q1",
            "page": 1,
            "page_size": 50,
            "status": "todos",
            "reason": "todos"
        }))
        res_p1 = json.loads(await ws.recv())
        assert res_p1.get("type") == "page"
        assert len(res_p1["simulation"]["resultados"]) == min(50, oraculo["total_linhas"])
        total_pages = res_p1["simulation"]["pagination"]["total_pages"]

        await ws.send(json.dumps({
            "type": "query",
            "request_id": "q_last",
            "page": total_pages,
            "page_size": 50,
            "status": "todos",
            "reason": "todos"
        }))
        res_last = json.loads(await ws.recv())
        assert res_last.get("type") == "page"
        assert len(res_last["simulation"]["resultados"]) > 0
        t1_pag = time.perf_counter()
        duracao_paginacao = t1_pag - t0_pag

        # 6. Auditoria de integridade persistida NA MESMA SESSÃO WS
        t0_audit = time.perf_counter()
        await ws.send(json.dumps({"type": "audit", "request_id": "audit_1"}))
        res_audit = json.loads(await ws.recv())
        t1_audit = time.perf_counter()
        duracao_audit_hash = t1_audit - t0_audit

        assert res_audit.get("type") == "audit", f"Resposta audit inválida: {res_audit}"
        assert res_audit.get("count") == oraculo["total_linhas"]
        assert res_audit.get("approved") == oraculo["aprovados"]
        assert res_audit.get("rejected") == oraculo["recusados"]
        assert Decimal(str(res_audit.get("total_nominal"))) == oraculo["total_nominal_submetido"]
        assert Decimal(str(res_audit.get("total_liquido"))) == oraculo["total_liquido"]

        audit_hash_servidor = res_audit.get("decisions_sha256")
        assert audit_hash_servidor == oraculo["decisions_sha256"], (
            f"Audit hash servidor ({audit_hash_servidor}) != oraculo ({oraculo['decisions_sha256']})"
        )

    return {
        "validacao_semantica_oraculo": "APROVADA_COM_SUCESSO",
        "alcance_auditoria": "confronto_linha_a_linha_status_primeiro_codigo_recusa_e_valores_nominal_e_liquido",
        "duracao_stream_segundos": round(duracao_ws_total, 4),
        "throughput_linhas_segundo": round(oraculo["total_linhas"] / duracao_ws_total, 2),
        "duracao_paginacao_segundos": round(duracao_paginacao, 4),
        "duracao_audit_hash_segundos": round(duracao_audit_hash, 4),
        "deadline_timeout_segundos": 300,
        "total_itens": oraculo["total_linhas"],
        "aprovados": simulation_envelope["aprovados"],
        "recusados": simulation_envelope["recusados"],
        "total_nominal_observado": str(obs_nominal),
        "total_nominal_esperado": str(oraculo["total_nominal_submetido"]),
        "total_liquido_observado": str(obs_liquido),
        "total_liquido_esperado": str(oraculo["total_liquido"]),
        "memoria_cliente_rss_inicio_mb": round(rss_cli_inicio, 2) if rss_cli_inicio else None,
        "memoria_cliente_rss_fim_mb": round(rss_cli_fim, 2) if rss_cli_fim else None,
        "memoria_cliente_rss_pico_mb": round(peak_cli, 2) if peak_cli else None,
        "memoria_servidor_rss_inicio_mb": round(rss_srv_inicio, 2) if rss_srv_inicio else None,
        "memoria_servidor_rss_fim_mb": round(rss_srv_fim, 2) if rss_srv_fim else None,
        "memoria_servidor_rss_pico_mb": round(peak_srv, 2) if peak_srv else None,
        "decisions_sha256": audit_hash_servidor,
    }

def parse_args():
    parser = argparse.ArgumentParser(description="CLI de Benchmark de Streaming WebSocket Antecipe")
    parser.add_argument("--url", type=str, default="ws://127.0.0.1:8088/api/simulations/stream", help="URL do WebSocket")
    parser.add_argument("--rows", nargs="+", type=int, default=[100000, 500000, 1000000], help="Cenários de linhas")
    parser.add_argument("--output", type=str, default="benchmarks/relatorio_benchmark_stream.json", help="Arquivo de saída")
    parser.add_argument("--server-pid", type=int, default=None, help="PID do servidor Uvicorn para monitorar RSS local")
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("BENCHMARK OFICIAL DE STREAMING WEBSOCKET ANTECIPE (100k, 500k e 1.000.000 linhas)")
    print("=" * 80)

    hashes_antes = obter_hashes_fontes()
    info_sistema = {
        "comando_executado": f"python {' '.join(sys.argv)}",
        "url_alvo": args.url,
        "sistema_operacional": platform.platform(),
        "python_versao": sys.version.split()[0],
        "processador": platform.processor(),
        "timestamp_utc_inicio": datetime.utcnow().isoformat() + "Z",
        "validacao": "oraculo_independente_audit_hash_decisions_sha256",
        "hashes_fontes_antes": hashes_antes,
    }

    print(f"Ambiente: {info_sistema['sistema_operacional']} | Python {info_sistema['python_versao']}")
    print(f"Alvo WebSocket: {args.url}")
    print(f"Cenários configurados: {args.rows}")
    print(f"Hashes Fontes Antes: {len(hashes_antes)} módulos auditados")
    print("-" * 80)

    relatorio_final = {
        "info_sistema": info_sistema,
        "resultados": {}
    }

    for n in args.rows:
        ts_cenario = datetime.utcnow().isoformat() + "Z"
        caminho_csv = os.path.join(CODEX_ANTECIPE_DIR, ".data", "benchmarks", f"sintetico_stream_{n}.csv")
        print(f"\n[{ts_cenario}] Gerando dataset determinístico e oráculo ({n:,} linhas)...")
        sha_csv, size_bytes, oraculo = gerar_csv_e_oraculo_stream(caminho_csv, n)
        print(f"      Arquivo: {caminho_csv} ({size_bytes:,} bytes)")
        print(f"      CSV SHA-256: {sha_csv}")
        print(f"      Oráculo: {oraculo['aprovados']:,} aprovados | {oraculo['recusados']:,} recusados")
        print(f"      Oráculo Total Nominal: R$ {oraculo['total_nominal_submetido']:,.2f} | Líquido: R$ {oraculo['total_liquido']:,.2f}")
        print(f"      Audit Hash Esperado: {oraculo['decisions_sha256']}")

        print(f"      Iniciando streaming WebSocket pipelined (frames 256KiB, janela 4MiB)...")
        res_cenario = asyncio.run(executar_benchmark_stream_ws(
            ws_url=args.url,
            caminho_csv=caminho_csv,
            oraculo=oraculo,
            server_pid=args.server_pid
        ))
        res_cenario["timestamp_utc"] = ts_cenario
        res_cenario["csv_sha256"] = sha_csv
        res_cenario["size_bytes"] = size_bytes
        relatorio_final["resultados"][f"{n}_linhas"] = res_cenario

        print(f"      Validação Semântica: {res_cenario['validacao_semantica_oraculo']}")
        print(f"      Tempo Total Streaming: {res_cenario['duracao_stream_segundos']}s")
        print(f"      Throughput: {res_cenario['throughput_linhas_segundo']:,.2f} linhas/s")
        print(f"      Tempo Paginação (p1 + última): {res_cenario['duracao_paginacao_segundos']}s")
        print(f"      Tempo Auditoria Audit Hash: {res_cenario['duracao_audit_hash_segundos']}s")
        print(f"      RSS Pico Cliente: {res_cenario['memoria_cliente_rss_pico_mb']} MB")
        if res_cenario['memoria_servidor_rss_pico_mb'] is not None:
            print(f"      RSS Pico Servidor: {res_cenario['memoria_servidor_rss_pico_mb']} MB")
        else:
            print(f"      RSS Servidor: não mensurado (remoto/hospedado)")
        print(f"      Total Nominal: Observado R$ {res_cenario['total_nominal_observado']} == Esperado R$ {res_cenario['total_nominal_esperado']}")
        print(f"      Total Líquido: Observado R$ {res_cenario['total_liquido_observado']} == Esperado R$ {res_cenario['total_liquido_esperado']}")
        print(f"      Audit Hash Validador: {res_cenario['decisions_sha256']}")

    hashes_depois = obter_hashes_fontes()
    relatorio_final["info_sistema"]["hashes_fontes_depois"] = hashes_depois
    assert hashes_antes == hashes_depois, "ERRO CRÍTICO: Fontes foram alteradas durante o benchmark de streaming!"

    caminho_saida = os.path.abspath(os.path.join(CODEX_ANTECIPE_DIR, args.output))
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(relatorio_final, f, indent=2)

    print("\n" + "=" * 80)
    print(f"Relatório auditável de streaming salvo em: {caminho_saida}")
    print("=" * 80)


if __name__ == "__main__":
    main()
