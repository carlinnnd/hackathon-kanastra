#!/usr/bin/env python3
"""Verifica esquema JSON e vazamentos de sentinelas sintéticas em arquivos de log."""

import argparse
import json
import re
import sys
from pathlib import Path


DEFAULT_FIELDS = {
    "timestamp", "level", "event", "job_id", "stage", "duration_ms",
    "rows_read", "rows_accepted", "rows_rejected", "error_code", "trace_id",
    "span_id", "service", "status", "batch_id",
}


def inspect(paths, sentinels, strict=True):
    errors = []
    checked = 0
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                checked += 1
                if any(marker in line for marker in sentinels):
                    errors.append(f"{path.name}:{line_number}: sentinela de dado vazou")
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"{path.name}:{line_number}: não é JSON válido")
                    continue
                if not isinstance(record, dict):
                    errors.append(f"{path.name}:{line_number}: registro não é objeto")
                    continue
                if strict:
                    unexpected = set(record) - DEFAULT_FIELDS
                    if unexpected:
                        errors.append(f"{path.name}:{line_number}: campos fora da allowlist: {', '.join(sorted(unexpected))}")
                if not all(key in record for key in ("timestamp", "level", "event")):
                    errors.append(f"{path.name}:{line_number}: faltam timestamp, level ou event")
                serialized = json.dumps(record, ensure_ascii=False)
                if re.search(r'(?i)"(?:password|senha|access_token|api_key|secret|csv_row|raw_row|email|cpf)"\s*:', serialized):
                    errors.append(f"{path.name}:{line_number}: campo sensível no log")
    return checked, errors


def main():
    parser = argparse.ArgumentParser(description="Audita arquivos JSONL de logs usando sentinelas de CSV sintético")
    parser.add_argument("paths", nargs="+", type=Path, help="Arquivos de logs JSONL a inspecionar")
    parser.add_argument("--sentinel", action="append", default=[], help="Sentinela FAKE_ONLY_... que foi colocada no CSV sintético")
    parser.add_argument("--allow-extra-fields", action="store_true", help="Desabilita allowlist de campos, mantém os outros checks")
    args = parser.parse_args()
    if any(not path.is_file() for path in args.paths):
        parser.error("Todos os caminhos devem apontar para arquivos existentes")
    checked, errors = inspect(args.paths, args.sentinel, not args.allow_extra_fields)
    print(f"Entradas JSONL verificadas: {checked}; erros: {len(errors)}")
    for item in errors[:40]:
        print(f"ERRO: {item}")
    if len(errors) > 40:
        print(f"Outros {len(errors)-40} erros foram omitidos")
    if not args.sentinel:
        print("AVISO: Sem --sentinel; ausência de dados do CSV NÃO foi comprovada.")
    return 1 if errors or checked == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
