#!/usr/bin/env python3
"""Runner independente de benchmark da futura CLI do projeto."""

import argparse
import csv
import datetime as dt
import json
import platform
import shlex
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from generate_fixture import generate
from prompt_ledger import scrub


ROOT = Path(__file__).resolve().parents[1]


def count_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def run_single(template, source, output, timeout, expected_rows):
    posix_mode = sys.platform != "win32"
    command = [part.format(input=str(source), output=str(output)) for part in shlex.split(template, posix=posix_mode)]
    started = time.perf_counter()
    try:
        proc = subprocess.run(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        code = None
        timed_out = True
    seconds = time.perf_counter() - started
    exists = output.is_file()
    size = output.stat().st_size if exists else 0
    observed_rows = count_csv(output) if expected_rows and exists and size else None
    passed = code == 0 and exists and size > 0 and not timed_out
    if expected_rows:
        passed = passed and observed_rows == expected_rows
    return {
        "seconds": round(seconds, 4),
        "exit_code": code,
        "timed_out": timed_out,
        "output_exists": exists,
        "output_bytes": size,
        "output_csv_rows": observed_rows,
        "basic_checks_passed": passed,
    }


def main():
    parser = argparse.ArgumentParser(description="Executa CLI do projeto sobre massas sintéticas para medir desempenho")
    parser.add_argument("--rows", type=int, nargs="+", default=[100000, 500000])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--command", required=True, help="Comando real contendo {input} e {output}; não executa shell")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--expect-one-output-row-per-input", action="store_true", help="Use somente se a semântica exigir exatamente 1 registro de saída por entrada")
    args = parser.parse_args()
    if args.runs < 1 or args.runs > 20 or any(r < 1 or r > 5_000_000 for r in args.rows):
        parser.error("Runs deve estar entre 1-20 e rows entre 1-5.000.000")
    if "{input}" not in args.command or "{output}" not in args.command:
        parser.error("O comando deve conter {input} e {output}")
    if args.timeout < 1:
        parser.error("Timeout deve ser positivo")
    base = ROOT / ".hackathon" / "benchmarks"
    base.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "command_template_sanitized": scrub(args.command),
        "semantic_correctness_verified": False,
        "note": "Checks básicos são insuficientes para validar regras de negócio; referencie testes independentes.",
        "runs": {},
    }
    all_ok = True
    with tempfile.TemporaryDirectory(prefix="bench-", dir=base) as temporary:
        temp = Path(temporary)
        for rows in args.rows:
            source = generate(temp / f"input-{rows}.csv", rows)
            attempts = []
            for number in range(args.runs):
                output = temp / f"output-{rows}-{number}.csv"
                result = run_single(args.command, source, output, args.timeout, rows if args.expect_one_output_row_per_input else 0)
                result["throughput_input_rows_per_second"] = round(rows / result["seconds"], 2) if result["seconds"] else None
                attempts.append(result)
                all_ok = all_ok and result["basic_checks_passed"]
            durations = [entry["seconds"] for entry in attempts]
            record["runs"][str(rows)] = {
                "attempts": attempts,
                "median_seconds": round(statistics.median(durations), 4),
                "min_seconds": min(durations),
                "max_seconds": max(durations),
                "median_input_rows_per_second": round(rows / statistics.median(durations), 2),
            }
    report_path = base / f"report-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Relatório: {report_path}")
    for rows, measurements in record["runs"].items():
        print(f"{rows} linhas: mediana {measurements['median_seconds']}s; {measurements['median_input_rows_per_second']} linhas/s (entrada)")
    print("Correção semântica: NÃO verificada pelo benchmark; execute testes próprios.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileExistsError, ValueError, OSError) as exc:
        print(f"Benchmark interrompido ({type(exc).__name__}). Confira argumentos e saídas.", file=sys.stderr)
        sys.exit(2)
