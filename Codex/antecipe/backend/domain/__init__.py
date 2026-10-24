"""
Exposição pública do subpacote domain.
Facilita importação por outros módulos (ex: backend.domain.*).
Compatibilidade retroativa estrita garantida para todos os contratos originais.
"""
from .cnpj import normalizar_cnpj, validar_cnpj
from .engine import ConfiguracaoMotor, MotorAvaliacao, RegraConfigurada, carregar_configuracao
from .limits import VALOR_MAXIMO_PERMITIDO, TOTAL_MAXIMO_PERMITIDO
from .ingestion import (
    CABECALHOS_OBRIGATORIOS,
    iterar_csv_recebiveis,
    normalizar_documento,
    normalizar_texto,
    parse_data_br,
    parse_data_br_estrito,
    parse_decimal_br,
    parse_linha_csv,
    validar_cabecalho,
)
from .models import (
    EstadoProjetadoLote,
    MotivoRecusa,
    ReceivelInput,
    ResultadoAvaliacao,
    SituacaoCadastral,
    SnapshotCarteira,
)
from .pricing import (
    CENTS_MINIMOS,
    LIMITE_MAXIMO_MONETARIO,
    ParametrosPrecificacao,
    ResultadoPrecificacao,
    calcular_desconto_simples,
)
from .rules import RuleRegistry, ValidadorStrategy

__all__ = [
    "normalizar_documento",
    "normalizar_texto",
    "normalizar_cnpj",
    "validar_cnpj",
    "VALOR_MAXIMO_PERMITIDO",
    "TOTAL_MAXIMO_PERMITIDO",
    "ConfiguracaoMotor",
    "MotorAvaliacao",
    "RegraConfigurada",
    "carregar_configuracao",
    "CABECALHOS_OBRIGATORIOS",
    "iterar_csv_recebiveis",
    "parse_data_br",
    "parse_data_br_estrito",
    "parse_decimal_br",
    "parse_linha_csv",
    "validar_cabecalho",
    "EstadoProjetadoLote",
    "MotivoRecusa",
    "ReceivelInput",
    "ResultadoAvaliacao",
    "SituacaoCadastral",
    "SnapshotCarteira",
    "ParametrosPrecificacao",
    "ResultadoPrecificacao",
    "calcular_desconto_simples",
    "LIMITE_MAXIMO_MONETARIO",
    "CENTS_MINIMOS",
    "RuleRegistry",
    "ValidadorStrategy",
]
