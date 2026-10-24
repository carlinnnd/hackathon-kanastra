"""
Gerador determinístico de lotes CSV sintéticos realistas para simulação no ANTECIPE FIDC.
Gera arquivos inéditos de 100, 1.000, 10.000 e 100.000 linhas no layout oficial de 11 colunas:
NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO

Cobre de forma balanceada e auditável:
- Casos APROVADOS (elegíveis com cálculo exato de Desconto Simples a 2,0% a.m.);
- CONCENTRACAO_MAXIMA_SACADO (Raiz 58206002 - Serralheria Violeta S.A. Matriz e Filiais 0001-11, 0002-00, 0003-83);
- SITUACAO_CADASTRAL_SACADO (Sacado INATIVA 33.000.167/0001-01 e NAO_VERIFICADA 88.888.888/0001-88);
- TIPO_RECEBIVEL (Cheque, CCB e Nota Comercial);
- VALOR_MINIMO (< R$ 100,00);
- NAO_VENCIDA (vencimento anterior à data-base 22/10/2026);
- PRAZO_MAXIMO (vencimento > 180 dias após 22/10/2026);
- DUPLICIDADE_HISTORICA (título já presente no estoque histórico);
- DUPLICIDADE_LOTE (repetição intra-lote da mesma chave global);
- CNPJ_SACADO_VALIDO (dígitos verificadores inválidos).
"""
import argparse
import io
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

CABECALHO_CSV = (
    "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;"
    "NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
)

FUNDO_NOME = "ANTECIPE FIDC"
FUNDO_DOC = "92.234.400/0001-80"
DATA_BASE = date(2026, 10, 22)

CEDENTES_VALIDOS: List[Tuple[str, str]] = [
    ("INDUSTRIA BRASIL SA", "11.222.333/0001-81"),
    ("MANUFATURA PAULISTA LTDA", "04.252.011/0001-10"),
    ("TEXTIL NORDESTE S.A.", "60.701.190/0001-04"),
    ("QUIMICA INDUSTRIAL SUL LTDA", "90.400.888/0001-42"),
]

SACADOS_ATIVOS_APROVAVEIS: List[Tuple[str, str]] = [
    ("COMERCIAL ALPHA LTDA", "04.252.011/0001-10"),
    ("INDUSTRIA BRASIL SA", "11.222.333/0001-81"),
    ("COMPANHIA NACIONAL DE SUPRIMENTOS", "00.000.000/0001-91"),
    ("METALURGICA VANGUARDA LTDA", "60.701.190/0001-04"),
    ("AGROPECUARIA VALE VERDE S.A.", "90.400.888/0001-42"),
    ("TECNOLOGIA INTEGRADA BRASIL LTDA", "34.028.316/0001-03"),
    ("ATACADISTA CENTRAL DO BRASIL S.A.", "60.746.948/0001-12"),
    ("BEBIDAS E ALIMENTOS SUL LTDA", "07.526.557/0001-00"),
]

# Raiz 58206002: Serralheria Violeta S.A. (Matriz + 2 Filiais) -> 12,50% no estoque histórico (> 10%)
FILIAIS_CONCENTRACAO_58206002: List[Tuple[str, str]] = [
    ("SERRALHERIA VIOLETA S.A. - MATRIZ", "58.206.002/0001-11"),
    ("SERRALHERIA VIOLETA S.A. - FILIAL SP", "58.206.002/0002-00"),
    ("SERRALHERIA VIOLETA S.A. - FILIAL MG", "58.206.002/0003-83"),
]


def iterar_linhas_lote_sintetico(total_rows: int, seed_tag: str = "SIM") -> Iterator[str]:
    """
    Gera linhas CSV em streaming (O(1) de memória) para o tamanho solicitado.
    A distribuição garante ~62% de aprovados e ~38% distribuídos entre todos os motivos de recusa.
    """
    yield CABECALHO_CSV

    ultimo_aprovado_para_duplicar: Tuple[str, str, str, str, str, str, str, str] = (
        "INDUSTRIA BRASIL SA",
        "11.222.333/0001-81",
        "COMERCIAL ALPHA LTDA",
        "04.252.011/0001-10",
        f"NF-{seed_tag}-000001",
        "Duplicata",
        "1500,00",
        "20/12/2026",
    )

    for i in range(1, total_rows + 1):
        cedente_nome, cedente_doc = CEDENTES_VALIDOS[i % len(CEDENTES_VALIDOS)]
        sacado_nome, sacado_doc = SACADOS_ATIVOS_APROVAVEIS[i % len(SACADOS_ATIVOS_APROVAVEIS)]
        tipo_rec = "Duplicata" if (i % 3 != 0) else "Duplicata de Serviço"
        dias_venc = 30 + ((i * 7) % 120)  # Entre 30 e 149 dias (dentro do limite de 180d)
        dt_venc_str = (DATA_BASE + timedelta(days=dias_venc)).strftime("%d/%m/%Y")
        valor_int = 250 + ((i * 137) % 4500)
        centavos = (i * 19) % 100
        valor_str = f"{valor_int},{centavos:02d}"
        nu_doc = f"NF-{seed_tag}-{total_rows}-{i:06d}"

        # Determina perfil da linha de forma determinística a cada 20 linhas
        slot = i % 20

        if i == 2:
            # Garante presença de Duplicidade Histórica exata do estoque real de 100k (estoque_antecipe.csv)
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};FRIGORIFICO BARRETOS LTDA ME;73.029.619/0001-00;"
                f"SERRALHERIA VIOLETA S.A.;58.206.002/0003-83;000568995;Duplicata;725,43;07/11/2026;\n"
            )
            continue

        if i == 3:
            # Garante presença de Duplicidade Histórica compatível com banco de teste/demo
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};INDUSTRIA BRASIL SA;11.222.333/0001-81;"
                f"COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-HIST-01;Duplicata;1000,00;20/01/2027;\n"
            )
            continue

        if slot in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
            # 60% APROVADOS: valores moderados para não estourar concentração das raízes ativas
            ultimo_aprovado_para_duplicar = (
                cedente_nome,
                cedente_doc,
                sacado_nome,
                sacado_doc,
                nu_doc,
                tipo_rec,
                valor_str,
                dt_venc_str,
            )
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{cedente_nome};{cedente_doc};"
                f"{sacado_nome};{sacado_doc};{nu_doc};{tipo_rec};{valor_str};{dt_venc_str};\n"
            )

        elif slot == 12:
            # CONCENTRACAO_MAXIMA_SACADO (Grupo Econômico Raiz 58206002 - Serralheria Violeta S.A.)
            filial_nome, filial_doc = FILIAIS_CONCENTRACAO_58206002[(i // 20) % len(FILIAIS_CONCENTRACAO_58206002)]
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{cedente_nome};{cedente_doc};"
                f"{filial_nome};{filial_doc};{nu_doc}-CONC;Duplicata;{valor_str};{dt_venc_str};\n"
            )

        elif slot == 13:
            # SITUACAO_CADASTRAL_SACADO (alterna entre INATIVA e NAO_VERIFICADA)
            if (i // 20) % 2 == 0:
                s_nome, s_doc = ("EMPRESA INATIVA SA", "33.000.167/0001-01")
            else:
                s_nome, s_doc = ("COMERCIO NAO VERIFICADO LTDA", "88.888.888/0001-88")
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{cedente_nome};{cedente_doc};"
                f"{s_nome};{s_doc};{nu_doc}-CAD;Duplicata;{valor_str};{dt_venc_str};\n"
            )

        elif slot == 14:
            # TIPO_RECEBIVEL não aceito (Cheque, CCB, Nota Comercial)
            tipos_invalidos = ["Cheque", "CCB", "Nota Comercial"]
            t_inv = tipos_invalidos[(i // 20) % len(tipos_invalidos)]
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{cedente_nome};{cedente_doc};"
                f"{sacado_nome};{sacado_doc};{nu_doc}-TIPO;{t_inv};{valor_str};{dt_venc_str};\n"
            )

        elif slot == 15:
            # VALOR_MINIMO (< R$ 100,00)
            val_baixo = f"{15 + (i % 84)},{(i * 7) % 100:02d}"
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{cedente_nome};{cedente_doc};"
                f"{sacado_nome};{sacado_doc};{nu_doc}-VMIN;Duplicata;{val_baixo};{dt_venc_str};\n"
            )

        elif slot == 16:
            # NAO_VENCIDA (vencimento no passado em relação a 22/10/2026)
            dias_atraso = 1 + (i % 45)
            dt_vencida = (DATA_BASE - timedelta(days=dias_atraso)).strftime("%d/%m/%Y")
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{cedente_nome};{cedente_doc};"
                f"{sacado_nome};{sacado_doc};{nu_doc}-VENC;Duplicata;{valor_str};{dt_vencida};\n"
            )

        elif slot == 17:
            # PRAZO_MAXIMO (> 180 dias após 22/10/2026)
            dias_longo = 185 + (i % 120)
            dt_longa = (DATA_BASE + timedelta(days=dias_longo)).strftime("%d/%m/%Y")
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{cedente_nome};{cedente_doc};"
                f"{sacado_nome};{sacado_doc};{nu_doc}-PMAX;Duplicata;{valor_str};{dt_longa};\n"
            )

        elif slot == 18:
            # DUPLICIDADE_LOTE (repete exatamente a última nota aprovada do lote)
            c_n, c_d, s_n, s_d, doc_rep, t_rep, v_rep, dt_rep = ultimo_aprovado_para_duplicar
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{c_n};{c_d};"
                f"{s_n};{s_d};{doc_rep};{t_rep};{v_rep};{dt_rep};\n"
            )

        else:
            # slot == 19: CNPJ_SACADO_VALIDO (dígitos verificadores inválidos)
            yield (
                f"{FUNDO_NOME};{FUNDO_DOC};{cedente_nome};{cedente_doc};"
                f"SACADO CNPJ INVALIDO LTDA;04.252.011/0001-99;{nu_doc}-CNPJ;Duplicata;{valor_str};{dt_venc_str};\n"
            )


def gerar_csv_simulacao_texto(total_rows: int, seed_tag: str = "SIM") -> str:
    """Retorna o conteúdo CSV completo em string para lotes pequenos/médios."""
    buf = io.StringIO()
    for line in iterar_linhas_lote_sintetico(total_rows, seed_tag=seed_tag):
        buf.write(line)
    return buf.getvalue()


def salvar_lote_csv(caminho: Path, total_rows: int, seed_tag: str = "SIM") -> Path:
    """Escreve um lote sintético em disco via streaming."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for line in iterar_linhas_lote_sintetico(total_rows, seed_tag=seed_tag):
            f.write(line)
    return caminho


def gerar_arquivos_lotes_padrao(diretorio_destino: Path) -> Dict[int, Path]:
    """Gera os 4 lotes padrão (100, 1.000, 10.000 e 100.000 linhas) no diretório informado."""
    tamanhos = [100, 1000, 10000, 100000]
    gerados: Dict[int, Path] = {}
    for tam in tamanhos:
        arq = diretorio_destino / f"lote_simulacao_{tam}.csv"
        salvar_lote_csv(arq, tam, seed_tag=f"L{tam}")
        gerados[tam] = arq
    return gerados


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
