import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.application.sample_batches import iterar_linhas_lote_sintetico, salvar_lote_csv, gerar_arquivos_lotes_padrao

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gerador de lotes CSV sintéticos realistas para o ANTECIPE FIDC."
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=1000,
        help="Quantidade de linhas a gerar (ex: 100, 1000, 10000, 100000).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Caminho do arquivo CSV de saída.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Gera os 4 lotes padrão (100, 1.000, 10.000 e 100.000 linhas) em Codex/antecipe/samples/lotes/.",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent / "samples" / "lotes"
    if args.all:
        arquivos = gerar_arquivos_lotes_padrao(base_dir)
        for tam, caminho in arquivos.items():
            print(f"[OK] Lote {tam:>7} linhas gerado em: {caminho}")
        return

    out_path = Path(args.output) if args.output else (base_dir / f"lote_simulacao_{args.rows}.csv")
    salvar_lote_csv(out_path, args.rows, seed_tag=f"L{args.rows}")
    print(f"[OK] Lote de {args.rows} linhas gerado em: {out_path}")


if __name__ == "__main__":
    main()
