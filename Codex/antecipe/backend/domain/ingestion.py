"""
Módulo de parsing e normalização de CSV / dados de recebíveis.
Responsabilidade única: transformar linhas brutas em instâncias de ReceivelInput
ou registrar erros estruturados de formatação.
Sem estado global e funções puras.
"""
import csv
import io
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Iterator, List, Optional, Tuple

from .cnpj import normalizar_cnpj
from .limits import VALOR_MAXIMO_PERMITIDO
from .models import MotivoRecusa, ReceivelInput, ResultadoAvaliacao

CABECALHOS_OBRIGATORIOS = [
    "NOME_FUNDO",
    "DOC_FUNDO",
    "NOME_CEDENTE",
    "DOC_CEDENTE",
    "NOME_SACADO",
    "DOC_SACADO",
    "NU_DOCUMENTO",
    "TIPO_RECEBIVEL",
    "VALOR_NOMINAL",
    "DATA_VENCIMENTO_ORIGINAL",
    "DATA_AQUISICAO",
]

# Aceita números inteiros ou com decimais de 1 até 4 dígitos para análise
PADRAO_DECIMAL_BR = re.compile(r"^\d{1,3}(\.\d{3})*,\d{1,4}$|^\d+,\d{1,4}$")
PADRAO_DECIMAL_US = re.compile(r"^\d{1,3}(,\d{3})*\.\d{1,4}$|^\d+\.\d{1,4}$")
PADRAO_DECIMAL_INT = re.compile(r"^\d+$")
CENTS_QUANTIZE = Decimal("0.01")


def normalizar_texto(texto: Optional[str]) -> str:
    """Normaliza texto em forma NFKC e remove espaços externos."""
    if not texto:
        return ""
    return unicodedata.normalize("NFKC", str(texto)).strip()


def normalizar_documento(doc: Optional[str]) -> str:
    """
    Remove pontuação e espaços mantendo apenas dígitos.
    Para validação estrita de CNPJ com rejeição de letras, use normalizar_cnpj.
    """
    if not doc:
        return ""
    return re.sub(r"\D", "", str(doc))


def parse_data_br_estrito(data_str: Optional[str]) -> Tuple[bool, Optional[date]]:
    """
    Helper estrito: retorna (valido, date_obj).
    Se vazio, retorna (True, None).
    Se preenchido e inválido, retorna (False, None).
    """
    if not data_str:
        return True, None
    d = str(data_str).strip()
    if not d:
        return True, None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(d, fmt).date()
            return True, dt
        except ValueError:
            pass
    return False, None


def parse_data_br(data_str: Optional[str]) -> Optional[date]:
    """
    Contrato público original: retorna Optional[date].
    Converte datas em formato dd/mm/aaaa ou aaaa-mm-dd. Se inválida ou vazia, retorna None.
    """
    ok, dt = parse_data_br_estrito(data_str)
    return dt if ok else None


def parse_decimal_br(valor_str: Optional[str]) -> Optional[Decimal]:
    """
    Converte string numérica em Decimal finito válido exatamente representável em centavos.
    
    Regras estritas de armazenamento e precisão monetária:
    - Rejeita frações não nulas além de 2 casas decimais (ex: 100.005 ou 100,005 -> None)
    - Normaliza valores com zeros redundantes (ex: 100.000 ou 100,00 -> Decimal('100.00'))
    - Rejeita NaN, Infinity, notação científica e grupos de milhar malformados
    - Rejeita valores com mais de 16 dígitos inteiros (prevenção contra estouro)
    - NUNCA arredonda silenciosamente o valor de face
    """
    if not valor_str or not isinstance(valor_str, str):
        return None
    
    v = valor_str.strip()
    if not v:
        return None
    
    # Rejeição explícita de NaN, Inf e expoentes
    if any(s in v.lower() for s in ("nan", "inf", "e")):
        return None

    # Validação sintática por regex
    if PADRAO_DECIMAL_BR.match(v):
        clean = v.replace(".", "").replace(",", ".")
    elif PADRAO_DECIMAL_US.match(v):
        clean = v.replace(",", "")
    elif PADRAO_DECIMAL_INT.match(v):
        clean = v
    else:
        return None

    # Prevenção contra estouro de dígitos inteiros
    parte_inteira = clean.split(".")[0]
    if len(parte_inteira) > 16:
        return None

    try:
        dec = Decimal(clean)
        if not dec.is_finite() or dec < Decimal("0"):
            return None

        # Verificação de exatidão em centavos (2 casas decimais)
        dec_cents = dec.quantize(CENTS_QUANTIZE)
        if dec != dec_cents:
            return None

        return dec_cents
    except (InvalidOperation, TypeError, ValueError):
        return None


def validar_cabecalho(headers: List[str]) -> Tuple[bool, List[str], str]:
    """
    Valida cabeçalhos do CSV:
    - Rejeita cabeçalhos duplicados
    - Normaliza UTF-8 BOM e espaços
    - Checa presença de todas as colunas obrigatórias
    """
    headers_limpos = [normalizar_texto(h).lstrip("\ufeff").upper() for h in headers]
    
    vistos = set()
    duplicados = []
    for h in headers_limpos:
        if h in vistos:
            duplicados.append(h)
        vistos.add(h)
    
    if duplicados:
        return False, duplicados, f"Cabeçalho inválido: colunas duplicadas detectadas ({', '.join(duplicados)})."

    faltantes = [h for h in CABECALHOS_OBRIGATORIOS if h not in vistos]
    if faltantes:
        return False, faltantes, f"Cabeçalho inválido: colunas obrigatórias ausentes ({', '.join(faltantes)})."

    return True, [], ""


def parse_linha_csv(
    linha_num: int,
    row_dict: Dict[str, str]
) -> Tuple[Optional[ReceivelInput], Optional[ResultadoAvaliacao]]:
    """
    Faz parsing defensivo de uma linha já mapeada para os cabeçalhos.
    Retorna (ReceivelInput, None) em caso de sucesso.
    Retorna (None, ResultadoAvaliacao com aprovado=False) em caso de erro estrutural.
    """
    row_norm = {k.upper().strip(): normalizar_texto(v) for k, v in row_dict.items() if k}

    nu_doc = row_norm.get("NU_DOCUMENTO", f"LINHA-{linha_num}")
    nome_sacado = row_norm.get("NOME_SACADO", "DESCONHECIDO")
    nome_cedente = row_norm.get("NOME_CEDENTE", "DESCONHECIDO")
    nome_fundo = row_norm.get("NOME_FUNDO", "ANTECIPE FIDC")
    tipo_recebivel = row_norm.get("TIPO_RECEBIVEL", "")

    doc_sacado_raw = row_norm.get("DOC_SACADO", "")
    doc_cedente_raw = row_norm.get("DOC_CEDENTE", "")
    doc_fundo_raw = row_norm.get("DOC_FUNDO", "")

    # 1. Validação de preenchimento dos campos essenciais
    campos_vazios = []
    for c in ("NU_DOCUMENTO", "NOME_SACADO", "DOC_SACADO", "NOME_CEDENTE", "DOC_CEDENTE", "TIPO_RECEBIVEL", "VALOR_NOMINAL", "DATA_VENCIMENTO_ORIGINAL"):
        if not row_norm.get(c):
            campos_vazios.append(c)

    if campos_vazios:
        return None, ResultadoAvaliacao(
            linha=linha_num,
            documento=nu_doc,
            sacado=nome_sacado,
            aprovado=False,
            valor_nominal=None,
            valor_liquido=None,
            motivos=[MotivoRecusa(
                codigo="CAMPOS_OBRIGATORIOS_VAZIOS",
                mensagem=f"Linha {linha_num} possui campos essenciais em branco: {', '.join(campos_vazios)}.",
                dados={"campos": campos_vazios, "linha": linha_num}
            )]
        )

    # 2. Validação sintática estrita dos documentos do sacado e cedente
    ok_sacado, doc_sacado_norm = normalizar_cnpj(doc_sacado_raw)
    if not ok_sacado:
        return None, ResultadoAvaliacao(
            linha=linha_num,
            documento=nu_doc,
            sacado=nome_sacado,
            aprovado=False,
            valor_nominal=None,
            valor_liquido=None,
            motivos=[MotivoRecusa(
                codigo="FORMATO_INVALIDO_DOCUMENTO_SACADO",
                mensagem=f"Documento do sacado possui formato sintático inválido ou caracteres não permitidos: '{doc_sacado_raw}'.",
                dados={"campo": "DOC_SACADO", "linha": linha_num}
            )]
        )

    ok_cedente, doc_cedente_norm = normalizar_cnpj(doc_cedente_raw)
    if not ok_cedente:
        return None, ResultadoAvaliacao(
            linha=linha_num,
            documento=nu_doc,
            sacado=nome_sacado,
            aprovado=False,
            valor_nominal=None,
            valor_liquido=None,
            motivos=[MotivoRecusa(
                codigo="FORMATO_INVALIDO_DOCUMENTO_CEDENTE",
                mensagem=f"Documento do cedente possui formato sintático inválido ou caracteres não permitidos: '{doc_cedente_raw}'.",
                dados={"campo": "DOC_CEDENTE", "linha": linha_num}
            )]
        )

    _, doc_fundo_norm = normalizar_cnpj(doc_fundo_raw)

    # 3. Validação de valor nominal e teto técnico de capacidade
    valor_nominal = parse_decimal_br(row_norm.get("VALOR_NOMINAL", ""))
    if valor_nominal is None:
        return None, ResultadoAvaliacao(
            linha=linha_num,
            documento=nu_doc,
            sacado=nome_sacado,
            aprovado=False,
            valor_nominal=None,
            valor_liquido=None,
            motivos=[MotivoRecusa(
                codigo="FORMATO_INVALIDO_VALOR",
                mensagem="Valor nominal inválido, não numérico, malformado ou com frações além de centavos.",
                dados={"campo": "VALOR_NOMINAL", "linha": linha_num}
            )]
        )

    # Teto técnico estrito: Numeric(15,2) suporta até R$ 9.999.999.999.999,99
    # Acima disso, recusa com VALOR_EXCEDE_CAPACIDADE e nominal=None para NUNCA persistir truncado/float
    if valor_nominal > VALOR_MAXIMO_PERMITIDO:
        return None, ResultadoAvaliacao(
            linha=linha_num,
            documento=nu_doc,
            sacado=nome_sacado,
            aprovado=False,
            valor_nominal=None,
            valor_liquido=None,
            motivos=[MotivoRecusa(
                codigo="VALOR_EXCEDE_CAPACIDADE",
                mensagem=f"Valor nominal excede a capacidade técnica de precisão exata suportada pelo sistema (teto R$ 9.999.999.999.999,99).",
                dados={"campo": "VALOR_NOMINAL", "linha": linha_num}
            )]
        )

    # 4. Validação de data de vencimento
    ok_venc, data_venc = parse_data_br_estrito(row_norm.get("DATA_VENCIMENTO_ORIGINAL", ""))
    if not ok_venc or data_venc is None:
        return None, ResultadoAvaliacao(
            linha=linha_num,
            documento=nu_doc,
            sacado=nome_sacado,
            aprovado=False,
            valor_nominal=valor_nominal,
            valor_liquido=None,
            motivos=[MotivoRecusa(
                codigo="FORMATO_INVALIDO_DATA_VENCIMENTO",
                mensagem="Data de vencimento original inválida ou fora do padrão esperado (dd/mm/aaaa).",
                dados={"campo": "DATA_VENCIMENTO_ORIGINAL", "linha": linha_num}
            )]
        )

    # 5. Validação de data de aquisição
    raw_aq = row_norm.get("DATA_AQUISICAO", "")
    ok_aq, data_aq = parse_data_br_estrito(raw_aq)
    if not ok_aq:
        return None, ResultadoAvaliacao(
            linha=linha_num,
            documento=nu_doc,
            sacado=nome_sacado,
            aprovado=False,
            valor_nominal=valor_nominal,
            valor_liquido=None,
            motivos=[MotivoRecusa(
                codigo="FORMATO_INVALIDO_DATA_AQUISICAO",
                mensagem="Data de aquisição informada está em formato inválido.",
                dados={"campo": "DATA_AQUISICAO", "linha": linha_num}
            )]
        )

    recebivel = ReceivelInput(
        linha=linha_num,
        nome_fundo=nome_fundo,
        doc_fundo=doc_fundo_norm,
        nome_cedente=nome_cedente,
        doc_cedente=doc_cedente_norm,
        nome_sacado=nome_sacado,
        doc_sacado=doc_sacado_norm,
        nu_documento=nu_doc,
        tipo_recebivel=tipo_recebivel,
        valor_nominal=valor_nominal,
        data_vencimento=data_venc,
        data_aquisicao=data_aq,
        originais=dict(row_dict),
    )
    return recebivel, None


def iterar_csv_recebiveis(
    stream: io.TextIOBase,
    delimitador: str = ";"
) -> Iterator[Tuple[int, Optional[ReceivelInput], Optional[ResultadoAvaliacao]]]:
    """
    Streaming Unix-style: lê linha a linha sem carregar todo o arquivo na memória.
    Yields (linha_numero, ReceivelInput, ErroDeParsingSeHouver).
    Rastreia linhas malformadas ou ragged (quantidade de colunas divergente).
    """
    reader = csv.reader(stream, delimiter=delimitador)
    
    try:
        raw_headers = next(reader)
    except StopIteration:
        raise ValueError("Arquivo CSV vazio.")

    ok, faltantes, erro_msg = validar_cabecalho(raw_headers)
    if not ok:
        raise ValueError(erro_msg)

    num_cols_esperadas = len(raw_headers)
    headers_limpos = [normalizar_texto(h).lstrip("\ufeff").upper() for h in raw_headers]

    for idx, raw_row in enumerate(reader, start=2):
        if not raw_row or all(not str(c).strip() for c in raw_row):
            continue

        if len(raw_row) != num_cols_esperadas:
            erro_ragged = ResultadoAvaliacao(
                linha=idx,
                documento=f"LINHA-{idx}",
                sacado="DESCONHECIDO",
                aprovado=False,
                valor_nominal=None,
                valor_liquido=None,
                motivos=[MotivoRecusa(
                    codigo="LINHA_MALFORMADA_COLUNAS",
                    mensagem=f"Linha {idx} possui {len(raw_row)} colunas, diferente das {num_cols_esperadas} esperadas pelo cabeçalho.",
                    dados={"linha": idx, "colunas_encontradas": len(raw_row), "colunas_esperadas": num_cols_esperadas}
                )]
            )
            yield (idx, None, erro_ragged)
            continue

        row_dict = dict(zip(headers_limpos, raw_row))
        item, erro = parse_linha_csv(idx, row_dict)
        if erro:
            erro.detalhes["originais"] = dict(row_dict)
        yield (idx, item, erro)
