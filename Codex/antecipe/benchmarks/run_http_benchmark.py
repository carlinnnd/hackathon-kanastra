"""
Harness Completo de Benchmark HTTP de Ponta a Ponta (100k e 500k linhas).
Executa pipelines de processamento HTTP completos cobrindo:
1. Setup de banco de dados SQLite isolado em `Codex/antecipe/.data/benchmarks/http_bench.db`.
2. Importação do estoque original oficial (`estoque_antecipe_100k/estoque_antecipe.csv`).
3. Inicialização e controle de ciclo de vida de processo Uvicorn dedicado em porta loopback exclusiva (8088),
   com `ENABLE_DEMO_CADASTRO=true`, `ADMIN_TOKEN` seguro e `--no-access-log`.
4. Rastreamento rigoroso de PID real do worker Python (gravado via bootstrap em arquivo) para medição
   exata de RSS via Win32 API (`WorkingSetSize` e `PeakWorkingSetSize`), segregando PID do launcher vs worker.
5. Fechamento garantido do servidor com verificação de porta 8088 livre (evitando processos órfãos).
6. Geração de dataset sintético determinístico com prefixo único `BENCH-HTTP-`, contendo
   mix controlado de aprovação/recusa.
7. Oráculo semântico independente adaptado ao snapshot real do estoque importado e ao mapa demo efetivo:
   - Projeta por linha: aprovação vs recusa, primeiro motivo exato e valor financeiro Decimal HALF_UP.
   - Projeta `total_nominal_submetido` (soma de todas as notas do lote) e `total_liquido_aprovado`.
8. Envio de multipart/form-data via streaming HTTP (`POST /api/simulations`).
9. Asserções estritas no envelope:
   - `assert envelope["status"] == "concluida"`
   - `assert envelope["total_itens"] == oraculo["total_linhas"]`
   - `assert envelope["aprovados"] == oraculo["aprovados"]`
   - `assert envelope["recusados"] == oraculo["recusados"]`
   - `assert Decimal(envelope["total_nominal"]) == oraculo["total_nominal_submetido"]`
   - `assert Decimal(envelope["total_liquido"]) == oraculo["total_liquido"]`
10. Auditoria de paginação (primeira e última páginas) e 100% dos itens persistidos no SQLite lidos em streaming SQL.
"""
import copy
import csv
import hashlib
import json
import os
import platform
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import httpx

DIRETORIO_BENCHMARKS = os.path.dirname(os.path.abspath(__file__))
CODEX_ANTECIPE_DIR = os.path.abspath(os.path.join(DIRETORIO_BENCHMARKS, ".."))
if CODEX_ANTECIPE_DIR not in sys.path:
    sys.path.insert(0, CODEX_ANTECIPE_DIR)

from backend.domain.models import SituacaoCadastral
from backend.application.cadastral_service import DEMO_CADASTRO_SINTETICO
from backend.infrastructure.database.session import Base, SessionLocal
from backend.infrastructure.database.models import FundModel, ReceivableModel, RuleVersionModel
from backend.application.importer import inicializar_fundos_e_regras, importar_estoque_csv
from backend.domain.cnpj import normalizar_cnpj, validar_cnpj


def calcular_hash_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def obter_hashes_fontes() -> Dict[str, str]:
    arquivos = [
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "main.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "config.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "logger.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "api", "routes.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "api", "schemas.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "application", "simulation_service.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "application", "importer.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "application", "cadastral_service.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "engine.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "ingestion.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "models.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "pricing.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "rules.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "cnpj.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "limits.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "__init__.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "infrastructure", "database", "models.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "infrastructure", "database", "session.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "infrastructure", "repositories", "rules_repository.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "infrastructure", "repositories", "receivables_repository.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "infrastructure", "repositories", "simulations_repository.py"),
        os.path.abspath(__file__),
    ]
    hashes = {}
    for arq in arquivos:
        if os.path.exists(arq):
            nome_rel = os.path.relpath(arq, CODEX_ANTECIPE_DIR).replace("\\", "/")
            hashes[nome_rel] = calcular_hash_arquivo(arq)
    return hashes


def get_process_memory_mb_by_pid(pid: int) -> Tuple[float, float]:
    """Retorna (WorkingSetSize_MB, PeakWorkingSetSize_MB) para um determinado PID no Windows via Win32 API."""
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
    return 0.0, 0.0


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def setup_banco_isolado(db_path: str) -> Tuple[Decimal, Dict[str, Decimal]]:
    if os.path.exists(db_path):
        os.remove(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{Path(db_path).as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    caminho_rules = os.path.abspath(os.path.join(CODEX_ANTECIPE_DIR, "..", "..", "validadores_antecipe.json"))
    if not os.path.exists(caminho_rules):
        caminho_rules = "validadores_antecipe.json"
    fundo = inicializar_fundos_e_regras(db, caminho_rules)

    caminho_estoque = os.path.abspath(os.path.join(CODEX_ANTECIPE_DIR, "..", "..", "estoque_antecipe_100k", "estoque_antecipe.csv"))
    print(f"      Importando estoque original ({caminho_estoque})...")
    tot_linhas, tot_antecipe, nom_antecipe, sha_carga = importar_estoque_csv(db, caminho_estoque)
    print(f"      Estoque importado com sucesso: {tot_linhas} registros totais ({tot_antecipe} para ANTECIPE FIDC - R$ {nom_antecipe:,.2f}).")

    from backend.infrastructure.repositories.receivables_repository import ReceivablesRepository
    repo = ReceivablesRepository(db)
    snap = repo.carregar_snapshot_carteira(fundo.id)
    db.close()
    engine.dispose()
    return snap.total_nominal, snap.exposicoes_sacado_raiz


def gerar_csv_e_oraculo_http(
    caminho_csv: str,
    total_linhas: int,
    carteira_inicial_nominal: Decimal,
    exposicoes_iniciais_sacados: Dict[str, Decimal],
    data_base: date = date(2026, 10, 22)
) -> Tuple[str, Dict]:
    os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)
    headers = [
        "NOME_FUNDO", "DOC_FUNDO", "NOME_CEDENTE", "DOC_CEDENTE",
        "NOME_SACADO", "DOC_SACADO", "NU_DOCUMENTO", "TIPO_RECEBIVEL",
        "VALOR_NOMINAL", "DATA_VENCIMENTO_ORIGINAL", "DATA_AQUISICAO"
    ]
    
    doc_fundo = "92.234.400/0001-80"
    nome_fundo = "ANTECIPE FIDC"
    doc_cedente = "00.111.222/0001-33"
    nome_cedente = "CEDENTE BENCH S/A"

    sacados = [
        ("COMERCIAL ALPHA LTDA", "04.252.011/0001-10", "ATIVA", "04252011"),
        ("SERVICOS BETA LTDA", "73.410.326/0001-22", "ATIVA", "73410326"),
        ("INDUSTRIA BRASIL SA", "11.222.333/0001-81", "ATIVA", "11222333"),
        ("EMPRESA INATIVA SA", "33.000.167/0001-01", "INATIVA", "33000167"),
    ]

    carteira_total = carteira_inicial_nominal
    exposicoes_raiz = copy.deepcopy(exposicoes_iniciais_sacados)

    oraculo_aprovados = 0
    oraculo_recusados = 0
    oraculo_total_nominal_submetido = Decimal("0.00")
    oraculo_total_nominal_aprovado = Decimal("0.00")
    oraculo_total_liquido_aprovado = Decimal("0.00")
    hasher_decisoes = hashlib.sha256()

    with open(caminho_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)

        for i in range(1, total_linhas + 1):
            s_idx = i % 4
            s_nome, s_doc, s_sit, s_raiz = sacados[s_idx]

            tipo = "Duplicata" if i % 10 != 0 else "Boleto"
            valor_num = 150 + (i % 2000)
            valor_dec = Decimal(f"{valor_num:.2f}")
            valor_str = f"{valor_num:.2f}".replace(".", ",")
            oraculo_total_nominal_submetido += valor_dec

            if i % 25 == 0:
                venc_str = "20/10/2026"
                venc_date = date(2026, 10, 20)
            elif i % 27 == 0:
                venc_str = "25/05/2027"
                venc_date = date(2027, 5, 25)
            else:
                venc_str = "20/11/2026"
                venc_date = date(2026, 11, 20)

            doc_numero = f"BENCH-HTTP-{i:07d}"
            linha_data = [
                nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                s_nome, s_doc, doc_numero, tipo,
                valor_str, venc_str, ""
            ]
            writer.writerow(linha_data)

            aprovado = True
            motivo = "APROVADO"

            # Validações estritas na ordem do contrato oficial
            if not validar_cnpj(s_doc):
                aprovado = False
                motivo = "CNPJ_SACADO_VALIDO"
            elif s_sit != "ATIVA":
                aprovado = False
                motivo = "SITUACAO_CADASTRAL_SACADO"
            elif tipo not in ["Duplicata", "Duplicata de Serviço"]:
                aprovado = False
                motivo = "TIPO_RECEBIVEL"
            elif valor_dec < Decimal("100.00"):
                aprovado = False
                motivo = "VALOR_MINIMO"
            elif venc_date <= data_base:
                aprovado = False
                motivo = "NAO_VENCIDA"
            elif (venc_date - data_base).days > 180:
                aprovado = False
                motivo = "PRAZO_MAXIMO"
            else:
                nova_carteira = carteira_total + valor_dec
                nova_exp = exposicoes_raiz.get(s_raiz, Decimal("0.00")) + valor_dec
                if (nova_exp / nova_carteira) * Decimal("100") > Decimal("10.0"):
                    aprovado = False
                    motivo = "CONCENTRACAO_MAXIMA_SACADO"
                else:
                    carteira_total = nova_carteira
                    exposicoes_raiz[s_raiz] = nova_exp

            linha_csv = i + 1
            if aprovado:
                oraculo_aprovados += 1
                oraculo_total_nominal_aprovado += valor_dec
                dias = (venc_date - data_base).days
                fator_diario = (Decimal("0.02") / Decimal("30")) * Decimal(dias)
                desc = (valor_dec * fator_diario).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                liq = valor_dec - desc
                oraculo_total_liquido_aprovado += liq
                hasher_decisoes.update(f"{linha_csv}:1:{valor_dec:.2f}:{liq:.2f}\n".encode("utf-8"))
            else:
                oraculo_recusados += 1
                hasher_decisoes.update(f"{linha_csv}:0:{motivo}\n".encode("utf-8"))

    hasher_file = hashlib.sha256()
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
        "hash_decisoes": hasher_decisoes.hexdigest(),
        "csv_sha256": hasher_file.hexdigest()
    }
    return hasher_file.hexdigest(), oraculo


class ServerProcessContext:
    def __init__(self, port: int, db_path: str):
        self.port = port
        self.db_path = db_path
        self.launcher_process: Optional[subprocess.Popen] = None
        self.worker_pid: Optional[int] = None
        self.pid_file = os.path.join(CODEX_ANTECIPE_DIR, ".data", "benchmarks", "uvicorn_worker.pid")

    def start(self):
        if is_port_in_use(self.port):
            raise RuntimeError(f"Porta {self.port} já está em uso antes do início do benchmark.")

        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)

        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{Path(self.db_path).as_posix()}"
        env["ADMIN_TOKEN"] = "bench-admin-secret-token-xyz"
        env["ENABLE_DEMO_CADASTRO"] = "true"
        env["PYTHONPATH"] = CODEX_ANTECIPE_DIR

        python_exe = os.path.join(CODEX_ANTECIPE_DIR, ".venv", "Scripts", "python.exe")
        
        # Script bootstrap inline que grava o PID real do worker Python
        bootstrap_code = f"""
import os, uvicorn
with open(r'{self.pid_file}', 'w') as f:
    f.write(str(os.getpid()))
uvicorn.run('backend.main:app', host='127.0.0.1', port={self.port}, log_level='warning', access_log=False)
"""
        cmd = [python_exe, "-c", bootstrap_code]
        self.launcher_process = subprocess.Popen(
            cmd,
            cwd=CODEX_ANTECIPE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        url_health = f"http://127.0.0.1:{self.port}/api/health"
        server_ready = False
        for _ in range(50):
            try:
                r = httpx.get(url_health, timeout=1.0)
                if r.status_code == 200:
                    server_ready = True
                    break
            except Exception:
                pass
            time.sleep(0.5)

        if not server_ready:
            raise RuntimeError(f"Servidor Uvicorn na porta {self.port} não iniciou a tempo.")

        # Lê PID real do worker gravado
        for _ in range(10):
            if os.path.exists(self.pid_file):
                try:
                    with open(self.pid_file, "r") as f:
                        self.worker_pid = int(f.read().strip())
                        break
                except Exception:
                    pass
            time.sleep(0.2)

        if not self.worker_pid:
            self.worker_pid = self.launcher_process.pid

    def stop(self):
        # 1. Encerra worker real se existir
        if self.worker_pid and self.worker_pid != (self.launcher_process.pid if self.launcher_process else None):
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(self.worker_pid)], capture_output=True)
                else:
                    os.kill(self.worker_pid, 9)
            except Exception:
                pass

        # 2. Encerra processo launcher
        if self.launcher_process:
            self.launcher_process.terminate()
            try:
                self.launcher_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.launcher_process.kill()
                self.launcher_process.wait()
            self.launcher_process = None

        if os.path.exists(self.pid_file):
            try:
                os.remove(self.pid_file)
            except Exception:
                pass

        # 3. Comprova que a porta 8088 está liberada
        for _ in range(20):
            if not is_port_in_use(self.port):
                return
            time.sleep(0.5)
        raise RuntimeError(f"Porta {self.port} permaneceu ocupada após parada do servidor Uvicorn!")


def executar_cenario_http(caminho_csv: str, oraculo: Dict, port: int, db_path: str, launcher_pid: int, worker_pid: int) -> Dict:
    url_simulacao = f"http://127.0.0.1:{port}/api/simulations"

    rss_cli_inicio, _ = get_process_memory_mb_by_pid(os.getpid())
    rss_worker_inicio, _ = get_process_memory_mb_by_pid(worker_pid)

    t0_http = time.perf_counter()
    with open(caminho_csv, "rb") as f:
        files = {"file": (os.path.basename(caminho_csv), f, "text/csv")}
        with httpx.Client(timeout=600.0) as client:
            resp = client.post(url_simulacao, files=files)
    t1_http = time.perf_counter()
    duracao_http = t1_http - t0_http

    rss_cli_fim, peak_cli = get_process_memory_mb_by_pid(os.getpid())
    rss_worker_fim, peak_worker = get_process_memory_mb_by_pid(worker_pid)
    _, peak_launcher = get_process_memory_mb_by_pid(launcher_pid)

    assert resp.status_code == 200, f"HTTP Error {resp.status_code}: {resp.text}"
    envelope = resp.json()

    # 1. Validação estrita do envelope retornado e totais Decimal
    assert envelope["status"] == "concluida"
    assert envelope["total_itens"] == oraculo["total_linhas"]
    assert envelope["aprovados"] == oraculo["aprovados"]
    assert envelope["recusados"] == oraculo["recusados"]
    
    # Asserções de total Decimal com semântica correta
    obs_total_nominal = Decimal(envelope["total_nominal"])
    obs_total_liquido = Decimal(envelope["total_liquido"])
    assert obs_total_nominal == oraculo["total_nominal_submetido"], (
        f"Total nominal ({obs_total_nominal}) != oraculo ({oraculo['total_nominal_submetido']})"
    )
    assert obs_total_liquido == oraculo["total_liquido"], (
        f"Total líquido ({obs_total_liquido}) != oraculo ({oraculo['total_liquido']})"
    )
    sim_id = envelope["simulation_id"]

    # 2. Validação da primeira página (50 itens)
    assert envelope["pagination"]["page"] == 1
    assert envelope["pagination"]["page_size"] == 50
    assert len(envelope["resultados"]) == min(50, oraculo["total_linhas"])
    total_pages = envelope["pagination"]["total_pages"]

    # 3. Validação da última página via GET /api/simulations/{id}
    t0_pag = time.perf_counter()
    with httpx.Client(timeout=60.0) as client:
        resp_last = client.get(f"{url_simulacao}/{sim_id}?page={total_pages}&page_size=50")
        assert resp_last.status_code == 200
        env_last = resp_last.json()
        assert env_last["pagination"]["page"] == total_pages
        assert len(env_last["resultados"]) > 0
    t1_pag = time.perf_counter()
    duracao_paginacao = t1_pag - t0_pag

    # 4. Auditoria de 100% dos registros persistidos no SQLite via streaming SQL
    t0_sql = time.perf_counter()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT linha, aprovado, valor_nominal, valor_liquido, motivos_json
        FROM simulation_items
        WHERE simulation_id = ?
        ORDER BY id ASC
    """, (sim_id,))

    hasher_db = hashlib.sha256()
    count_db = 0
    while rows := cursor.fetchmany(5000):
        for linha, aprov, v_nom, v_liq, motivos_json in rows:
            count_db += 1
            if aprov:
                hasher_db.update(f"{linha}:1:{Decimal(str(v_nom)):.2f}:{Decimal(str(v_liq)):.2f}\n".encode("utf-8"))
            else:
                motivos = json.loads(motivos_json) if motivos_json else []
                cod = motivos[0]["codigo"] if motivos else "DESCONHECIDO"
                hasher_db.update(f"{linha}:0:{cod}\n".encode("utf-8"))
    conn.close()
    t1_sql = time.perf_counter()
    duracao_sql = t1_sql - t0_sql

    assert count_db == oraculo["total_linhas"], f"Registros persistidos ({count_db}) != esperado ({oraculo['total_linhas']})"
    hash_db_calculado = hasher_db.hexdigest()
    assert hash_db_calculado == oraculo["hash_decisoes"], "Hash das decisões persistidas no banco divergiu do oráculo!"

    return {
        "validacao_semantica_oraculo": "APROVADA_COM_SUCESSO",
        "duracao_http_segundos": round(duracao_http, 4),
        "throughput_http_linhas_segundo": round(oraculo["total_linhas"] / duracao_http, 2),
        "duracao_auditoria_sql_segundos": round(duracao_sql, 4),
        "duracao_teste_paginacao_segundos": round(duracao_paginacao, 4),
        "total_itens": count_db,
        "aprovados": envelope["aprovados"],
        "recusados": envelope["recusados"],
        "total_nominal_observado": str(obs_total_nominal),
        "total_nominal_esperado": str(oraculo["total_nominal_submetido"]),
        "total_liquido_observado": str(obs_total_liquido),
        "total_liquido_esperado": str(oraculo["total_liquido"]),
        "memoria_cliente_rss_inicio_mb": round(rss_cli_inicio, 2),
        "memoria_cliente_rss_fim_mb": round(rss_cli_fim, 2),
        "memoria_cliente_rss_pico_mb": round(peak_cli, 2),
        "memoria_servidor_worker_rss_inicio_mb": round(rss_worker_inicio, 2),
        "memoria_servidor_worker_rss_fim_mb": round(rss_worker_fim, 2),
        "memoria_servidor_worker_rss_pico_mb": round(peak_worker, 2),
        "memoria_launcher_rss_pico_mb": round(peak_launcher, 2),
        "pid_launcher": launcher_pid,
        "pid_worker_uvicorn": worker_pid,
        "hash_decisoes_db": hash_db_calculado,
    }


def main():
    print("=" * 80)
    print("BENCHMARK OFICIAL HTTP ANTECIPE — 100k e 500k linhas (Medição Real Uvicorn Worker)")
    print("=" * 80)

    hashes_antes = obter_hashes_fontes()
    porta_loopback = 8088
    db_path = os.path.join(CODEX_ANTECIPE_DIR, ".data", "benchmarks", "http_bench.db")

    info_sistema = {
        "comando_executado": "Codex/antecipe/.venv/Scripts/python Codex/antecipe/benchmarks/run_http_benchmark.py",
        "numero_repeticoes": 1,
        "porta_servidor_loopback": porta_loopback,
        "banco_temporario_isolado": db_path,
        "sistema_operacional": platform.platform(),
        "python_versao": sys.version.split()[0],
        "processador": platform.processor(),
        "timestamp_utc_inicio": datetime.utcnow().isoformat() + "Z",
        "validacao": "oraculo_independente_snapshot_real_e_auditoria_sql",
        "hashes_fontes_antes": hashes_antes,
    }

    print(f"Ambiente: {info_sistema['sistema_operacional']} | Python {info_sistema['python_versao']}")
    print(f"Porta Uvicorn Isolada: {porta_loopback} | Banco: {db_path}")
    print(f"Hashes Fontes Antes: {len(hashes_antes)} módulos auditados")
    print("-" * 80)

    # 1. Setup banco e importação inicial do estoque original oficial
    print("\n[Fase 1/3] Inicializando banco isolado e importando estoque de recebíveis oficial...")
    total_carteira_nominal, exposicoes_sacados = setup_banco_isolado(db_path)
    print(f"      Snapshot do estoque importado: Carteira Total R$ {total_carteira_nominal:,.2f}")
    print(f"      Sacados no estoque: {len(exposicoes_sacados)} raízes mapeadas.")

    # 2. Inicialização do servidor Uvicorn no processo dedicado com gravação do PID do worker
    print(f"\n[Fase 2/3] Iniciando servidor Uvicorn loopback na porta {porta_loopback}...")
    server_ctx = ServerProcessContext(porta_loopback, db_path)
    server_ctx.start()
    launcher_pid = server_ctx.launcher_process.pid
    worker_pid = server_ctx.worker_pid
    print(f"      Servidor iniciado com sucesso: Launcher PID {launcher_pid} | Worker PID {worker_pid}.")

    cenarios = [100000, 500000]
    relatorio_final = {
        "info_sistema": info_sistema,
        "evidencia_limitacao_rodada_anterior": "Rodada anterior utilizou medição de launcher Popen.pid (4.41MB) em vez de worker real. Corrigido para rastrear PID worker real via bootstrap.",
        "resultados": {}
    }

    try:
        for n in cenarios:
            ts_cenario = datetime.utcnow().isoformat() + "Z"
            caminho_csv = os.path.join(CODEX_ANTECIPE_DIR, ".data", "benchmarks", f"sintetico_http_{n}.csv")
            print(f"\n[{ts_cenario}] Gerando dataset HTTP e oráculo independente ({n:,} linhas)...")
            sha_csv, oraculo = gerar_csv_e_oraculo_http(
                caminho_csv=caminho_csv,
                total_linhas=n,
                carteira_inicial_nominal=total_carteira_nominal,
                exposicoes_iniciais_sacados=exposicoes_sacados
            )
            print(f"      Arquivo gerado: {caminho_csv}")
            print(f"      CSV SHA-256: {sha_csv}")
            print(f"      Oráculo: {oraculo['aprovados']:,} aprovados | {oraculo['recusados']:,} recusados")
            print(f"      Oráculo Total Nominal: R$ {oraculo['total_nominal_submetido']:,.2f} | Líquido Aprovado: R$ {oraculo['total_liquido']:,.2f}")

            print(f"      Enviando POST /api/simulations multipart via streaming HTTP...")
            res_c = executar_cenario_http(
                caminho_csv=caminho_csv,
                oraculo=oraculo,
                port=porta_loopback,
                db_path=db_path,
                launcher_pid=launcher_pid,
                worker_pid=worker_pid
            )
            res_c["timestamp_utc"] = ts_cenario
            res_c["csv_sha256"] = sha_csv
            relatorio_final["resultados"][f"{n}_linhas"] = res_c

            print(f"      Validação Semântica: {res_c['validacao_semantica_oraculo']}")
            print(f"      Tempo Total HTTP (upload+persistência): {res_c['duracao_http_segundos']}s")
            print(f"      Throughput HTTP: {res_c['throughput_http_linhas_segundo']:,.2f} linhas/s")
            print(f"      Tempo Auditoria SQL (streaming 100%): {res_c['duracao_auditoria_sql_segundos']}s")
            print(f"      RSS Pico Worker Uvicorn: {res_c['memoria_servidor_worker_rss_pico_mb']} MB (PID {worker_pid})")
            print(f"      RSS Pico Launcher: {res_c['memoria_launcher_rss_pico_mb']} MB (PID {launcher_pid})")
            print(f"      RSS Pico Cliente: {res_c['memoria_cliente_rss_pico_mb']} MB")
            print(f"      Total Nominal: Observado R$ {res_c['total_nominal_observado']} == Esperado R$ {res_c['total_nominal_esperado']}")
            print(f"      Total Líquido: Observado R$ {res_c['total_liquido_observado']} == Esperado R$ {res_c['total_liquido_esperado']}")
            print(f"      Hash Decisões Persistidas (Banco == Oráculo): {res_c['hash_decisoes_db']}")

    finally:
        print("\n[Fase 3/3] Encerrando servidor Uvicorn dedicado de forma limpa...")
        server_ctx.stop()
        print(f"      Servidor Uvicorn finalizado. Porta {porta_loopback} comprovadamente livre.")

    hashes_depois = obter_hashes_fontes()
    relatorio_final["info_sistema"]["hashes_fontes_depois"] = hashes_depois
    assert hashes_antes == hashes_depois, "ERRO CRÍTICO: Fontes foram alteradas durante o benchmark HTTP!"

    caminho_relatorio = os.path.join(CODEX_ANTECIPE_DIR, "benchmarks", "relatorio_benchmark_http.json")
    with open(caminho_relatorio, "w", encoding="utf-8") as f:
        json.dump(relatorio_final, f, indent=2)

    print("\n" + "=" * 80)
    print(f"Relatório auditável de benchmark HTTP salvo em: {caminho_relatorio}")
    print("=" * 80)


if __name__ == "__main__":
    main()
