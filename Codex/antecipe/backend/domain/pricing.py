"""
Cálculo financeiro de antecipação e precificação.
Regra de Desconto Simples comercial:
  fator = 1 - (taxa_mensal * dias / base_dias)
  liquido_bruto = valor_nominal * fator
  valor_liquido = round(liquido_bruto, 2, ROUND_HALF_UP)
  desconto = valor_nominal - valor_liquido

Uso estrito de Decimal, finitude e arredondamento ROUND_HALF_UP.
Proteção contra estouro de capacidade/precisão monetária (limite de 18 dígitos / Numeric(18,2)).
Invariante estrita: valor_liquido NUNCA pode exceder valor_nominal para taxa_mensal >= 0.
Rejeição de valor líquido nulo ou negativo inclusive com prazo zero ou centavos residuais.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

# Limite máximo monetário para evitar estouro de capacidade em campos Numeric(18, 2)
# R$ 999.999.999.999.999,99 (16 dígitos inteiros + 2 decimais)
LIMITE_MAXIMO_MONETARIO = Decimal("9999999999999999.99")
CENTS_MINIMOS = Decimal("0.01")


@dataclass(frozen=True)
class ParametrosPrecificacao:
    metodo: str = "DESCONTO_SIMPLES"
    taxa_mensal: Decimal = Decimal("0.02")  # 2.0% -> 0.02
    base_dias: int = 30

    def __post_init__(self) -> None:
        if self.metodo != "DESCONTO_SIMPLES":
            raise ValueError(f"Método de precificação não suportado: {self.metodo}")
        if not isinstance(self.base_dias, int) or self.base_dias <= 0:
            raise ValueError(f"Base de dias deve ser inteiro positivo, recebido: {self.base_dias}")
        if not isinstance(self.taxa_mensal, Decimal) or not self.taxa_mensal.is_finite() or self.taxa_mensal < Decimal("0"):
            raise ValueError(f"Taxa mensal deve ser Decimal finito não negativo, recebido: {self.taxa_mensal}")


@dataclass(frozen=True)
class ResultadoPrecificacao:
    valor_nominal: Decimal
    dias: int
    desconto: Decimal
    valor_liquido: Decimal
    valido: bool
    motivo_invalidez: Optional[str] = None


def calcular_desconto_simples(
    valor_nominal: Decimal,
    data_base: date,
    data_vencimento: date,
    params: ParametrosPrecificacao
) -> ResultadoPrecificacao:
    """
    Calcula o valor líquido aplicando a fórmula direta do edital/especificação:
      liquido_bruto = valor_nominal * (1 - taxa_mensal * dias / base_dias)
    Arredonda o valor líquido diretamente com ROUND_HALF_UP para centavos,
    e obtém o desconto derivado: desconto = valor_nominal - valor_liquido.
    Garante que valor_liquido <= valor_nominal e desconto >= 0 para taxa_mensal >= 0.
    """
    if not isinstance(valor_nominal, Decimal) or not valor_nominal.is_finite() or valor_nominal <= Decimal("0"):
        return ResultadoPrecificacao(
            valor_nominal=valor_nominal,
            dias=0,
            desconto=Decimal("0.00"),
            valor_liquido=Decimal("0.00"),
            valido=False,
            motivo_invalidez="Valor nominal deve ser Decimal positivo e finito."
        )

    # Proteção de capacidade monetária máxima para evitar InvalidOperation ou estouro no DB
    if valor_nominal > LIMITE_MAXIMO_MONETARIO:
        return ResultadoPrecificacao(
            valor_nominal=valor_nominal,
            dias=0,
            desconto=Decimal("0.00"),
            valor_liquido=Decimal("0.00"),
            valido=False,
            motivo_invalidez="Valor nominal excede a capacidade monetária suportada pelo sistema."
        )

    # Invariantes dos parâmetros
    if params.metodo != "DESCONTO_SIMPLES" or params.base_dias <= 0 or params.taxa_mensal < Decimal("0"):
        return ResultadoPrecificacao(
            valor_nominal=valor_nominal,
            dias=0,
            desconto=Decimal("0.00"),
            valor_liquido=Decimal("0.00"),
            valido=False,
            motivo_invalidez="Parâmetros de precificação inválidos."
        )

    dias = (data_vencimento - data_base).days
    
    if dias < 0:
        return ResultadoPrecificacao(
            valor_nominal=valor_nominal,
            dias=dias,
            desconto=Decimal("0.00"),
            valor_liquido=Decimal("0.00"),
            valido=False,
            motivo_invalidez="Título com vencimento anterior à data-base não pode ser precificado."
        )

    # Prazo zero: sem desconto comercial
    if dias == 0:
        try:
            vl = valor_nominal.quantize(CENTS_MINIMOS, rounding=ROUND_HALF_UP)
        except InvalidOperation:
            return ResultadoPrecificacao(
                valor_nominal=valor_nominal,
                dias=0,
                desconto=Decimal("0.00"),
                valor_liquido=Decimal("0.00"),
                valido=False,
                motivo_invalidez="Erro de quantização no arredondamento monetário."
            )

        # Invariante estrita: líquido nunca pode ser maior que o nominal com taxa não negativa
        if vl > valor_nominal:
            vl = valor_nominal.quantize(CENTS_MINIMOS, rounding=ROUND_HALF_UP)

        if vl <= Decimal("0.00"):
            return ResultadoPrecificacao(
                valor_nominal=valor_nominal,
                dias=0,
                desconto=Decimal("0.00"),
                valor_liquido=Decimal("0.00"),
                valido=False,
                motivo_invalidez="Valor nominal após arredondamento comercial resulta em R$ 0,00."
            )

        return ResultadoPrecificacao(
            valor_nominal=valor_nominal,
            dias=0,
            desconto=Decimal("0.00"),
            valor_liquido=vl,
            valido=True
        )

    # Cálculo com alta precisão
    # fator = 1 - (taxa_mensal * dias / base_dias)
    fator_prazo = Decimal(dias) / Decimal(params.base_dias)
    fator_desconto = params.taxa_mensal * fator_prazo
    fator_liquido = Decimal("1") - fator_desconto

    if fator_liquido <= Decimal("0"):
        return ResultadoPrecificacao(
            valor_nominal=valor_nominal,
            dias=dias,
            desconto=valor_nominal.quantize(CENTS_MINIMOS, rounding=ROUND_HALF_UP),
            valor_liquido=Decimal("0.00"),
            valido=False,
            motivo_invalidez="Desconto financeiro excede ou iguala o valor de face (líquido zero ou negativo)."
        )

    try:
        liquido_bruto = valor_nominal * fator_liquido
        valor_liquido = liquido_bruto.quantize(CENTS_MINIMOS, rounding=ROUND_HALF_UP)
        
        # Invariante estrita: líquido nunca pode ser maior que o nominal para taxa >= 0
        if valor_liquido > valor_nominal:
            valor_liquido = valor_nominal.quantize(CENTS_MINIMOS, rounding=ROUND_HALF_UP)

        # Desconto derivado exatamente da diferença
        desconto = valor_nominal - valor_liquido
        desconto = desconto.quantize(CENTS_MINIMOS, rounding=ROUND_HALF_UP)
        if desconto < Decimal("0.00"):
            desconto = Decimal("0.00")
    except InvalidOperation:
        return ResultadoPrecificacao(
            valor_nominal=valor_nominal,
            dias=dias,
            desconto=Decimal("0.00"),
            valor_liquido=Decimal("0.00"),
            valido=False,
            motivo_invalidez="Operação monetária inválida por estouro de capacidade de quantização."
        )

    if valor_liquido <= Decimal("0.00"):
        return ResultadoPrecificacao(
            valor_nominal=valor_nominal,
            dias=dias,
            desconto=desconto,
            valor_liquido=valor_liquido,
            valido=False,
            motivo_invalidez="Desconto financeiro excede ou iguala o valor de face (líquido zero ou negativo)."
        )

    return ResultadoPrecificacao(
        valor_nominal=valor_nominal,
        dias=dias,
        desconto=desconto,
        valor_liquido=valor_liquido,
        valido=True
    )
