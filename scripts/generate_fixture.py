#!/usr/bin/env python3
"""Gera massas CSV 100% sintéticas, sem serviços ou bibliotecas externas."""

import argparse
import csv
from pathlib import Path


def generate(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record_id", "category", "amount_cents", "status", "synthetic_marker"])
        for index in range(1, rows + 1):
            writer.writerow([index, f"CAT_{index % 13}", (index * 37) % 100000, "ok" if index % 23 else "review", f"FAKE_ONLY_{index:08d}"])
    return path


def main():
    parser = argparse.ArgumentParser(description="Gera CSV sintético por quantidade de registros")
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rows <= 5_000_000:
        parser.error("--rows deve estar entre 1 e 5.000.000")
    try:
        path = generate(args.output, args.rows)
    except FileExistsError:
        parser.error("Arquivo já existe; escolha outro caminho em vez de sobrescrever")
    print(f"Gerado arquivo sintético: {path} ({args.rows} registros)")


if __name__ == "__main__":
    main()
