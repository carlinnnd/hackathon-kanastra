from decimal import Decimal

# Capacidade técnica máxima para armazenamento monetário exato sob Numeric(15, 2)
# Faixa cujo roundtrip em centavos é preservado sob Numeric(15, 2); SQLite pode usar float internamente
# Teto: R$ 9.999.999.999.999,99 (13 dígitos inteiros e 2 casas decimais)
VALOR_MAXIMO_PERMITIDO: Decimal = Decimal("9999999999999.99")
TOTAL_MAXIMO_PERMITIDO: Decimal = VALOR_MAXIMO_PERMITIDO
