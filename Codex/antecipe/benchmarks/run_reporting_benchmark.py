"""Mede análise HISTÓRICA + persistência + CSV/PDF, sem classificar estoque como nova operação."""
import argparse
import csv
import hashlib
import io
import itertools
import json
import platform
import sys
import time
import uuid
import ctypes
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT))
from backend.config import settings
from backend.infrastructure.database.session import Base
from backend.application.importer import inicializar_fundos_e_regras
from backend.application.simulation_service import SimulationService
from backend.application.exports import exportar
from backend.domain.ingestion import parse_linha_csv


def run(source, count, output):
    started = datetime.now(timezone.utc).isoformat()
    case = output / f"historico-{count}-{uuid.uuid4().hex[:8]}"
    case.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{(case / 'results.db').as_posix()}")
    Base.metadata.create_all(engine)
    expected = {"count": 0, "nominal": 0}
    def items():
        # Repete o estoque somente para formar o cenário maior; não representa novas operações.
        while expected["count"] < count:
            with source.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream, delimiter=";"):
                    idx = expected["count"] + 2
                    item, erro = parse_linha_csv(idx, row)
                    if not item or erro:
                        raise ValueError("Fixture de benchmark histórico contém dados inválidos")
                    expected["count"] += 1
                    expected["nominal"] += int(item.valor_nominal * 100)
                    yield idx, item, erro
                    if expected["count"] >= count: break
    settings.ENABLE_DEMO_CADASTRO = True
    begin = time.perf_counter()
    with Session(engine) as db:
        inicializar_fundos_e_regras(db, str(ROOT / "validadores_antecipe.json"))
        sim_id, envelope = SimulationService(db).executar_simulacao_lote(items(), tipo_analise="carteira")
        evaluated = time.perf_counter()
        assert envelope['analytics']['status_counts'] == {'CARTEIRA_HISTORICA': count}
        assert Decimal(envelope['total_nominal']) == Decimal(expected['nominal']) / 100
        from backend.infrastructure.repositories.simulations_repository import SimulationsRepository
        sim = SimulationsRepository(db).obter_simulacao(sim_id)
        chunks, _ = exportar(db, sim, 'csv')
        csv_path = case / 'resultado.csv'
        with csv_path.open('wb') as out:
            for chunk in chunks: out.write(chunk)
        exported = time.perf_counter()
        n = nominal = 0
        with csv_path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream, delimiter=';'):
                n += 1
                nominal += int(Decimal(row['valor_nominal'].replace(',', '.')) * 100)
                assert row['status'] == 'CARTEIRA_HISTORICA'
                assert row['valor_liquido'] == '' and row['valor_desconto'] == ''
        assert n == count and nominal == expected['nominal']
        pdf_chunks, _ = exportar(db, sim, 'pdf')
        pdf = b''.join(pdf_chunks)
        (case / 'executivo.pdf').write_bytes(pdf)
    duration = time.perf_counter() - begin
    engine.dispose()
    class MemoryCounters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [(n, ctypes.c_size_t) for n in [
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage"]]
    from ctypes import wintypes
    process_handle = ctypes.windll.kernel32.GetCurrentProcess
    process_handle.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    counters = MemoryCounters(); counters.cb = ctypes.sizeof(counters)
    if not get_memory(process_handle(), ctypes.byref(counters), counters.cb):
        raise RuntimeError('Medição Win32 de memória falhou; não reportar zero como memória válida')
    result = {'started_utc': started, 'rows': count, 'tipo_analise': 'carteira',
        'fixture': 'estoque histórico repetido para o cenário de 500k; sem novas operações',
        'evaluation_persistence_seconds': evaluated-begin, 'csv_seconds': exported-evaluated,
        'total_with_verification_pdf_seconds': duration, 'csv_bytes': csv_path.stat().st_size,
        'rows_per_second_evaluation_persistence': count / (evaluated - begin),
        'process_lifetime_peak_rss_mb': counters.PeakWorkingSetSize / 1024**2,
        'rss_after_mb': counters.WorkingSetSize / 1024**2,
        'rss_scope': 'Win32 WorkingSet/PeakWorkingSet do processo; pico cumulativo entre cenários',
        'expected_nominal': str(Decimal(expected['nominal'])/100), 'verified_rows': n,
        'csv_row_status_nominal_and_no_pricing_verified': True, 'case_path': str(case),
        'scope': 'local service + SQLite file + CSV integral + PDF; não mede HTTP/WebSocket nem capacidade publicada'}
    (case/'measurement.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--rows', type=int, nargs='+', default=[100000,500000])
    p.add_argument('--output', type=Path, default=PROJECT/'.data/reporting-benchmark')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    sources = list((PROJECT/'backend').rglob('*.py')) + [Path(__file__)]
    def hashes():
        return {str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources if 'tests' not in f.parts}
    before=hashes()
    result={'environment':{'python':sys.version,'platform':platform.platform(),'sqlalchemy':__import__('sqlalchemy').__version__},
        'source_sha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),'source_hashes_before':before,
        'results':[run(args.source,n,args.output) for n in args.rows]}
    result['source_hashes_after']=hashes()
    result['same_sources']=before==result['source_hashes_after']
    (args.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
