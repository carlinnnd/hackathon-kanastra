"""
Script de Auditoria e Comparação — Gabarito 100k vs Regras Derivadas Sem Circularidade.
- Concentrações calculadas DINAMICAMENTE por DOC_FUNDO normalizado e raiz de sacado (Decimal puro).
- Tipos de recebível e valor mínimo lidos diretamente de validadores_antecipe.json.
- Verificação independente sem hardcode de raízes nem vazamento de PII.
- Assertions estritas: totalCSV == totalgabarito, unicidade de linha e integridade linha + id.
"""
import csv
import datetime
import json
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal


def carregar_parametros_validadores(json_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f, parse_float=Decimal)
    
    params = {}
    for v in data.get("validadores", []):
        cod = v.get("codigo")
        params[cod] = v.get("parametros", {})
    return params


def auditar_gabarito_independente(csv_path: str, gabarito_path: str, validadores_path: str) -> dict:
    params = carregar_parametros_validadores(validadores_path)
    
    val_min_limite = Decimal(str(params.get("VALOR_MINIMO", {}).get("valor_minimo", "100.00")))
    tipos_aceitos = tuple(params.get("TIPO_RECEBIVEL", {}).get("tipos_aceitos", ["Duplicata", "Duplicata de Serviço"]))
    prazo_max_dias = int(params.get("PRAZO_MAXIMO", {}).get("prazo_maximo_dias", 180))
    conc_max_pct = Decimal(str(params.get("CONCENTRACAO_MAXIMA_SACADO", {}).get("percentual_maximo", "10.0")))

    # 1. Carrega gabarito
    with open(gabarito_path, "r", encoding="utf-8") as f:
        gabarito_list = json.load(f)
    gabarito_map = {item["linha"]: item for item in gabarito_list}
    total_linhas_gabarito = len(gabarito_list)

    # Asserção de unicidade de linhas no gabarito
    assert len(gabarito_map) == total_linhas_gabarito, "Gabarito possui linhas duplicadas."

    # 2. Passo 1: Cálculo dinâmico das concentrações históricas por DOC_FUNDO e raiz do sacado
    totais_por_fundo = defaultdict(Decimal)
    exposicoes_por_fundo_raiz = defaultdict(lambda: defaultdict(Decimal))
    docs_sinalizados_cadastro = set()
    total_linhas_csv = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for idx, row in enumerate(reader, start=2):
            total_linhas_csv += 1
            doc_fundo = re.sub(r"\D", "", row["DOC_FUNDO"])
            doc_sacado = re.sub(r"\D", "", row["DOC_SACADO"])
            raiz_sacado = doc_sacado[:8]
            val = Decimal(row["VALOR_NOMINAL"].replace(",", "."))
            totais_por_fundo[doc_fundo] += val
            exposicoes_por_fundo_raiz[doc_fundo][raiz_sacado] += val

            # Valida paridade de ID/linha com gabarito sem vazar PII
            gab = gabarito_map.get(idx)
            assert gab is not None, f"Linha {idx} do CSV ausente no gabarito."
            assert str(gab.get("id")).strip() == row["NU_DOCUMENTO"].strip(), f"ID divergente na linha {idx}."

            if "SITUACAO_CADASTRAL_SACADO" in gab.get("barrado_por", []):
                docs_sinalizados_cadastro.add(doc_sacado)

    # Asserção estrita de paridade volumétrica
    assert total_linhas_csv == total_linhas_gabarito, f"Total CSV ({total_linhas_csv}) != Gabarito ({total_linhas_gabarito})."

    # Identifica dinamicamente as raízes que excedem conc_max_pct
    raizes_excedentes_por_fundo = defaultdict(set)
    qtd_total_raizes_excedentes = 0
    for doc_fundo, total_fundo in totais_por_fundo.items():
        for raiz, exp in exposicoes_por_fundo_raiz[doc_fundo].items():
            pct = (exp / total_fundo) * Decimal("100.0")
            if pct > conc_max_pct:
                raizes_excedentes_por_fundo[doc_fundo].add(raiz)
                qtd_total_raizes_excedentes += 1

    # Passo 2: Avaliação linha a linha
    match_status_4_regras = 0
    match_status_com_cadastro_rotulado = 0
    match_motivos_exatos = 0

    contagem_motivos_gabarito = Counter()
    contagem_motivos_reproduzidos = Counter()
    tipos_reais_barrados = Counter()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for idx, row in enumerate(reader, start=2):
            gab = gabarito_map[idx]
            for m in gab.get("barrado_por", []):
                contagem_motivos_gabarito[m] += 1

            doc_fundo = re.sub(r"\D", "", row["DOC_FUNDO"])
            doc_sacado = re.sub(r"\D", "", row["DOC_SACADO"])
            raiz_sacado = doc_sacado[:8]
            tipo = row["TIPO_RECEBIVEL"].strip()
            val = Decimal(row["VALOR_NOMINAL"].replace(",", "."))
            dv = datetime.datetime.strptime(row["DATA_VENCIMENTO_ORIGINAL"], "%d/%m/%Y").date()
            da = datetime.datetime.strptime(row["DATA_AQUISICAO"], "%d/%m/%Y").date()

            motivos_4_regras = []
            if val < val_min_limite:
                motivos_4_regras.append("VALOR_MINIMO")
            if tipo not in tipos_aceitos:
                motivos_4_regras.append("TIPO_RECEBIVEL")
                tipos_reais_barrados[tipo] += 1
            if (dv - da).days > prazo_max_dias:
                motivos_4_regras.append("PRAZO_MAXIMO")
            if raiz_sacado in raizes_excedentes_por_fundo.get(doc_fundo, set()):
                motivos_4_regras.append("CONCENTRACAO_MAXIMA_SACADO")

            motivos_com_cadastro = list(motivos_4_regras)
            if doc_sacado in docs_sinalizados_cadastro:
                motivos_com_cadastro.append("SITUACAO_CADASTRAL_SACADO")

            for m in motivos_com_cadastro:
                contagem_motivos_reproduzidos[m] += 1

            status_gab = gab["status"]
            if ("BARRADO" if motivos_4_regras else "APROVADO") == status_gab:
                match_status_4_regras += 1

            if ("BARRADO" if motivos_com_cadastro else "APROVADO") == status_gab:
                match_status_com_cadastro_rotulado += 1

            if sorted(motivos_com_cadastro) == sorted(gab.get("barrado_por", [])):
                match_motivos_exatos += 1

    return {
        "total_registros": total_linhas_csv,
        "gabarito_status": {
            "aprovados": sum(1 for x in gabarito_list if x["status"] == "APROVADO"),
            "barrados": sum(1 for x in gabarito_list if x["status"] == "BARRADO"),
        },
        "validacao_independente_4_regras_sem_cadastro": {
            "match_status": match_status_4_regras,
            "match_status_pct": f"{(match_status_4_regras / total_linhas_csv) * 100:.4f}%",
            "comentario": "Avaliação estritamente derivada de parâmetros de validadores_antecipe.json e dados do estoque, sem vetor cadastral externo."
        },
        "analise_exploratoria_com_cadastro_rotulado": {
            "documentos_sinalizados_gabarito": len(docs_sinalizados_cadastro),
            "match_status": match_status_com_cadastro_rotulado,
            "match_status_pct": f"{(match_status_com_cadastro_rotulado / total_linhas_csv) * 100:.4f}%",
            "match_motivos_exatos": match_motivos_exatos,
            "match_motivos_exatos_pct": f"{(match_motivos_exatos / total_linhas_csv) * 100:.4f}%",
        },
        "motivos_gabarito": dict(contagem_motivos_gabarito),
        "motivos_reproduzidos": dict(contagem_motivos_reproduzidos),
        "tipos_reais_barrados": dict(tipos_reais_barrados),
        "agregado_concentracao_dinamica": {
            "total_fundos_avaliados": len(totais_por_fundo),
            "total_fundos_com_raizes_acima_limite": len(raizes_excedentes_por_fundo),
            "total_raizes_acima_limite": qtd_total_raizes_excedentes
        }
    }


if __name__ == "__main__":
    res = auditar_gabarito_independente(
        csv_path="estoque_antecipe_100k/estoque_antecipe.csv",
        gabarito_path="resultado_esperado_100k.json",
        validadores_path="validadores_antecipe.json"
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
