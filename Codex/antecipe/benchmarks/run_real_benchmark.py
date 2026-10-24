"""
Benchmark Oficial de Performance e Escalabilidade (100k e 500k linhas).
Executa pipelines de processamento de ponta a ponta com ORÁCULO SEMÂNTICO INDEPENDENTE.
Atende estritamente às diretrizes de auditoria (AGENTS.md):
- Comando exato de execução registrado.
- Número de repetições configurado e documentado.
- Hash SHA-256 das fontes antes e depois da execução para garantir que nada foi alterado.
- Horário UTC por cenário.
- Rótulos transparentes de memória: `memoria_rss_amostrado_pico_mb` e `memoria_rss_so_pico_mb` via GetProcessMemoryInfo (PeakWorkingSetSize).
- Alcance semântico explicitado: comparação linha a linha contra o oráculo independente confrontando aprovação, primeiro motivo de recusa e valor financeiro exato.
"""
import csv
import hashlib
import json
import os
import platform
import sys
import time
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Iterator, List, Tuple

try:
    import psutil
except ImportError:
    psutil = None

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
CODEX_ANTECIPE_DIR = os.path.abspath(os.path.join(DIRETORIO_ATUAL, ".."))
if CODEX_ANTECIPE_DIR not in sys.path:
    sys.path.insert(0, CODEX_ANTECIPE_DIR)

from backend.domain.models import ReceivelInput, SituacaoCadastral, SnapshotCarteira
from backend.domain.engine import carregar_configuracao, MotorAvaliacao
from backend.domain.ingestion import iterar_csv_recebiveis


def calcular_hash_arquivo(caminho: str) -> str:
    """Calcula hash SHA-256 de um arquivo em disco."""
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def obter_hashes_fontes() -> Dict[str, str]:
    """Coleta hash SHA-256 de todos os módulos de domínio do motor e do benchmark."""
    arquivos = [
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "engine.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "ingestion.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "models.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "rules.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "pricing.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "limits.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "cnpj.py"),
        os.path.join(CODEX_ANTECIPE_DIR, "backend", "domain", "__init__.py"),
        os.path.abspath(__file__),
    ]
    hashes = {}
    for arq in arquivos:
        if os.path.exists(arq):
            nome_rel = os.path.relpath(arq, CODEX_ANTECIPE_DIR).replace("\\", "/")
            hashes[nome_rel] = calcular_hash_arquivo(arq)
    return hashes


def get_memory_info() -> Tuple[float, float]:
    """
    Retorna (working_set_size_mb, peak_working_set_size_mb)
    usando Win32 GetProcessMemoryInfo no Windows ou psutil.
    """
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
            psapi = ctypes.WinDLL('psapi.dll')
            kernel32 = ctypes.WinDLL('kernel32.dll')
            GetProcessMemoryInfo = psapi.GetProcessMemoryInfo
            GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
            GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                rss = counters.WorkingSetSize / (1024 * 1024)
                peak_rss = counters.PeakWorkingSetSize / (1024 * 1024)
                return rss, peak_rss
        except Exception:
            pass
    if psutil:
        p = psutil.Process(os.getpid())
        mem = p.memory_info().rss / (1024 * 1024)
        return mem, mem
    return 0.0, 0.0


def gerar_csv_e_oraculo(caminho_csv: str, total_linhas: int, data_base: date = date(2026, 10, 22)) -> Tuple[str, Dict]:
    os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)
    
    headers = [
        "NOME_FUNDO", "DOC_FUNDO", "NOME_CEDENTE", "DOC_CEDENTE",
        "NOME_SACADO", "DOC_SACADO", "NU_DOCUMENTO", "TIPO_RECEBIVEL",
        "VALOR_NOMINAL", "DATA_VENCIMENTO_ORIGINAL", "DATA_AQUISICAO"
    ]
    
    doc_fundo = "92.234.400/0001-80"
    nome_fundo = "ANTECIPE FIDC"
    doc_cedente = "00.111.222/0001-33"
    nome_cedente = "CEDENTE PADRAO S/A"
    
    sacados = [
        ("SACADO ATIVO A", "11.222.333/0001-81", "ATIVA", "11222333"),
        ("SACADO ATIVO B", "11.222.333/0002-62", "ATIVA", "11222333"),
        ("SACADO ATIVO C", "00.000.000/0001-91", "ATIVA", "00000000"),
        ("SACADO INATIVO", "99.888.777/0001-00", "INATIVA", "99888777"),
    ]
    
    carteira_total = Decimal("10000000.00")
    exposicoes_raiz = {"00000000": Decimal("500000.00")}
    
    oraculo_aprovados = 0
    oraculo_recusados = 0
    oraculo_total_nominal = Decimal("0.00")
    oraculo_total_liquido = Decimal("0.00")
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
            
            if i % 25 == 0:
                venc_str = "20/10/2026"
                venc_date = date(2026, 10, 20)
            elif i % 27 == 0:
                venc_str = "25/05/2027"
                venc_date = date(2027, 5, 25)
            else:
                venc_str = "20/11/2026"
                venc_date = date(2026, 11, 20)
                
            linha_data = [
                nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                s_nome, s_doc, f"DOC-{i:07d}", tipo,
                valor_str, venc_str, ""
            ]
            writer.writerow(linha_data)
            
            aprovado = True
            motivo = "APROVADO"
            
            if tipo not in ["Duplicata", "Duplicata de Serviço"]:
                aprovado = False
                motivo = "TIPO_RECEBIVEL"
            elif s_sit != "ATIVA":
                aprovado = False
                motivo = "SITUACAO_CADASTRAL_SACADO"
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
                    
            if aprovado:
                oraculo_aprovados += 1
                oraculo_total_nominal += valor_dec
                dias = (venc_date - data_base).days
                fator_diario = (Decimal("0.02") / Decimal("30")) * Decimal(dias)
                desc = (valor_dec * fator_diario).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                liq = valor_dec - desc
                oraculo_total_liquido += liq
                hasher_decisoes.update(f"{i}:1:{valor_dec}:{liq}\n".encode("utf-8"))
            else:
                oraculo_recusados += 1
                hasher_decisoes.update(f"{i}:0:{motivo}\n".encode("utf-8"))

    hasher_file = hashlib.sha256()
    with open(caminho_csv, "rb") as f:
        while chunk := f.read(65536):
            hasher_file.update(chunk)
            
    oraculo = {
        "total_linhas": total_linhas,
        "aprovados": oraculo_aprovados,
        "recusados": oraculo_recusados,
        "total_nominal": oraculo_total_nominal,
        "total_liquido": oraculo_total_liquido,
        "hash_decisoes": hasher_decisoes.hexdigest(),
        "csv_sha256": hasher_file.hexdigest()
    }
    return hasher_file.hexdigest(), oraculo


def executar_benchmark_com_oraculo(caminho_csv: str, oraculo: Dict) -> Dict:
    caminho_json = os.path.abspath(os.path.join(CODEX_ANTECIPE_DIR, "..", "..", "validadores_antecipe.json"))
    if not os.path.exists(caminho_json):
        caminho_json = "validadores_antecipe.json"
        
    with open(caminho_json, "r", encoding="utf-8") as f:
        raw_config = json.load(f, parse_float=Decimal)
        
    data_base = date(2026, 10, 22)
    config = carregar_configuracao(raw_config, data_base_default=data_base)
    
    contexto_cadastral = {
        "11222333000181": SituacaoCadastral.ATIVA.value,
        "11222333000262": SituacaoCadastral.ATIVA.value,
        "00000000000191": SituacaoCadastral.ATIVA.value,
        "99888777000100": SituacaoCadastral.INATIVA.value,
    }
    
    snapshot = SnapshotCarteira(
        total_nominal=Decimal("10000000.00"),
        exposicoes_sacado_raiz={"00000000": Decimal("500000.00")}
    )
    motor = MotorAvaliacao(config)
    
    mem_inicio, _ = get_memory_info()
    pico_amostrado = mem_inicio
    t_inicio = time.perf_counter()
    
    total_lidos = 0
    aprovados = 0
    recusados = 0
    total_nominal_aprovado = Decimal("0.00")
    total_liquido_aprovado = Decimal("0.00")
    hasher_saida = hashlib.sha256()
    
    with open(caminho_csv, "r", encoding="utf-8") as f:
        stream_itens = iterar_csv_recebiveis(f)
        
        for res in motor.avaliar_lote_stream(stream_itens, contexto_cadastral, snapshot):
            total_lidos += 1
            if res.aprovado:
                aprovados += 1
                total_nominal_aprovado += res.valor_nominal
                total_liquido_aprovado += res.valor_liquido
                hasher_saida.update(f"{total_lidos}:1:{res.valor_nominal}:{res.valor_liquido}\n".encode("utf-8"))
            else:
                recusados += 1
                cod_motivo = res.motivos[0].codigo if res.motivos else "DESCONHECIDO"
                hasher_saida.update(f"{total_lidos}:0:{cod_motivo}\n".encode("utf-8"))
                
            if total_lidos % 5000 == 0:
                atual, _ = get_memory_info()
                if atual > pico_amostrado:
                    pico_amostrado = atual
                    
    t_fim = time.perf_counter()
    mem_fim, peak_so = get_memory_info()
    duracao_total = t_fim - t_inicio
    throughput = total_lidos / duracao_total if duracao_total > 0 else 0
    hash_saida_calculado = hasher_saida.hexdigest()
    
    assert total_lidos == oraculo["total_linhas"], f"Total lidos ({total_lidos}) != esperado ({oraculo['total_linhas']})"
    assert aprovados + recusados == total_lidos, "Soma de aprovados + recusados diverge do total lido"
    assert aprovados == oraculo["aprovados"], f"Aprovados ({aprovados}) != oraculo ({oraculo['aprovados']})"
    assert recusados == oraculo["recusados"], f"Recusados ({recusados}) != oraculo ({oraculo['recusados']})"
    assert total_nominal_aprovado == oraculo["total_nominal"], f"Nominal ({total_nominal_aprovado}) != oraculo ({oraculo['total_nominal']})"
    assert total_liquido_aprovado == oraculo["total_liquido"], f"Líquido ({total_liquido_aprovado}) != oraculo ({oraculo['total_liquido']})"
    assert hash_saida_calculado == oraculo["hash_decisoes"], "Hash das decisões linha a linha divergiu do oráculo!"

    return {
        "validacao_semantica_oraculo": "APROVADA_COM_SUCESSO",
        "alcance_validacao": "confronto_linha_a_linha_aprovacao_primeiro_motivo_recusa_e_calculo_decimal",
        "total_linhas": total_lidos,
        "aprovados": aprovados,
        "recusados": recusados,
        "total_nominal_aprovado": str(total_nominal_aprovado),
        "total_liquido_aprovado": str(total_liquido_aprovado),
        "duracao_segundos": round(duracao_total, 4),
        "throughput_linhas_segundo": round(throughput, 2),
        "memoria_rss_inicio_mb": round(mem_inicio, 2),
        "memoria_rss_fim_mb": round(mem_fim, 2),
        "memoria_rss_amostrado_pico_mb": round(pico_amostrado, 2),
        "memoria_rss_so_pico_mb": round(peak_so, 2),
        "hash_decisoes_saida": hash_saida_calculado,
    }


def main():
    print("=" * 75)
    print("BENCHMARK OFICIAL ANTECIPE COM ORÁCULO SEMÂNTICO (100k e 500k)")
    print("=" * 75)
    
    hashes_antes = obter_hashes_fontes()
    
    info_sistema = {
        "comando_executado": "Codex/antecipe/.venv/Scripts/python Codex/antecipe/benchmarks/run_real_benchmark.py",
        "numero_repeticoes": 1,
        "sistema_operacional": platform.platform(),
        "python_versao": sys.version.split()[0],
        "processador": platform.processor(),
        "timestamp_utc_inicio": datetime.utcnow().isoformat() + "Z",
        "validacao": "oraculo_independente_linha_a_linha",
        "hashes_fontes_antes": hashes_antes,
    }
    print(f"Ambiente: {info_sistema['sistema_operacional']} | Python {info_sistema['python_versao']}")
    print(f"Horário Início: {info_sistema['timestamp_utc_inicio']}")
    print(f"Hashes Fontes Antes: {json.dumps(hashes_antes, indent=2)}")
    print("-" * 75)
    
    cenarios = [100000, 500000]
    relatorio_final = {
        "info_sistema": info_sistema,
        "resultados": {}
    }
    
    for n in cenarios:
        ts_cenario = datetime.utcnow().isoformat() + "Z"
        caminho = os.path.join(CODEX_ANTECIPE_DIR, ".data", "benchmarks", f"sintetico_{n}.csv")
        print(f"\n[{ts_cenario}] Gerando dataset e oráculo independente ({n:,} linhas)...")
        sha_csv, oraculo = gerar_csv_e_oraculo(caminho, n)
        print(f"      Arquivo: {caminho}")
        print(f"      CSV SHA-256: {sha_csv}")
        print(f"      Oráculo: {oraculo['aprovados']:,} aprovados | {oraculo['recusados']:,} recusados")
        print(f"      Oráculo Nominal: R$ {oraculo['total_nominal']:,.2f} | Líquido: R$ {oraculo['total_liquido']:,.2f}")
        
        print(f"      Executando streaming oficial e confrontando com o oráculo...")
        res = executar_benchmark_com_oraculo(caminho, oraculo)
        res["timestamp_utc"] = ts_cenario
        res["csv_sha256"] = sha_csv
        relatorio_final["resultados"][f"{n}_linhas"] = res
        
        print(f"      Validação Semântica: {res['validacao_semantica_oraculo']}")
        print(f"      Total Linhas: {res['total_linhas']:,}")
        print(f"      Aprovados: {res['aprovados']:,} | Recusados: {res['recusados']:,}")
        print(f"      Tempo de Execução: {res['duracao_segundos']}s")
        print(f"      Throughput: {res['throughput_linhas_segundo']:,.2f} linhas/s")
        print(f"      RSS Amostrado Pico: {res['memoria_rss_amostrado_pico_mb']} MB")
        print(f"      RSS SO Pico (PeakWorkingSetSize): {res['memoria_rss_so_pico_mb']} MB")
        print(f"      Hash Decisões (Motor == Oráculo): {res['hash_decisoes_saida']}")
        
    hashes_depois = obter_hashes_fontes()
    relatorio_final["info_sistema"]["hashes_fontes_depois"] = hashes_depois
    assert hashes_antes == hashes_depois, "ERRO CRÍTICO: fontes foram alteradas durante a execução do benchmark!"
    
    caminho_relatorio = os.path.join(CODEX_ANTECIPE_DIR, "benchmarks", "relatorio_benchmark_real.json")
    with open(caminho_relatorio, "w", encoding="utf-8") as f:
        json.dump(relatorio_final, f, indent=2)
        
    print("\n" + "=" * 75)
    print(f"Relatório auditável com integridade de fontes salvo em: {caminho_relatorio}")
    print("=" * 75)


if __name__ == "__main__":
    main()
