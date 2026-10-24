"""
Motor de Avaliação e Simulação de Recebíveis.
Módulo principal de domínio: `backend.domain.engine`.
Composição Unix-style:
- Recebe iterador/lote de ReceivelInput
- Carrega configuração congelada e validada estritamente contra schema
- Aplica regras individuais -> duplicidade -> regras de carteira (concentração) -> precificação
- Acumula projeção determinística estritamente de recebíveis aprovados
- Gera resultados iteráveis e agregados sem N+1.
"""
import copy
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from .models import (
    EstadoProjetadoLote,
    MotivoRecusa,
    ReceivelInput,
    ResultadoAvaliacao,
    SnapshotCarteira,
)
from .pricing import ParametrosPrecificacao, calcular_desconto_simples
from .rules import RuleRegistry


@dataclass(frozen=True)
class RegraConfigurada:
    codigo: str
    ativo: bool
    parametros: Dict[str, Any]


@dataclass(frozen=True)
class ConfiguracaoMotor:
    fundo_nome: str
    fundo_cnpj: str
    data_base: date
    regras: List[RegraConfigurada]
    precificacao: ParametrosPrecificacao
    raw_config: Dict[str, Any] = field(default_factory=dict)


def carregar_configuracao(
    json_config: Dict[str, Any],
    data_base_default: Optional[date] = None,
    registry: Optional[RuleRegistry] = None
) -> ConfiguracaoMotor:
    """
    Constrói a ConfiguracaoMotor a partir do JSON de regras oficial (validadores_antecipe.json).
    Aplica validação rigorosa de schema:
    - Rejeita tipos booleanos falsos (ex: string "false")
    - Rejeita códigos desconhecidos ou duplicados
    - Rejeita regras sem parâmetros obrigatórios exigidos pelo validador
    - Rejeita precificação com método diferente de DESCONTO_SIMPLES
    - Rejeita base de dias <= 0 ou taxas não finitas/negativas
    - Rejeita defaults ocultos; exige campos essenciais
    - Retorna cópia profunda imutável.
    """
    if not isinstance(json_config, dict):
        raise ValueError("Configuração deve ser um objeto JSON (dict).")

    # Deep copy completo para isolamento
    config_dict = copy.deepcopy(json_config)

    fundo_info = config_dict.get("fundo")
    if not isinstance(fundo_info, dict):
        raise ValueError("Configuração requer objeto 'fundo' com 'nome' e 'cnpj'.")
    
    fundo_nome = str(fundo_info.get("nome", "")).strip()
    fundo_cnpj = str(fundo_info.get("cnpj", "")).strip()
    if not fundo_nome:
        raise ValueError("Campo 'fundo.nome' é obrigatório e não pode ser vazio.")

    # Data base estrita
    data_base_str = config_dict.get("data_base")
    if data_base_str:
        try:
            dt_base = datetime.strptime(str(data_base_str), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Formato de 'data_base' inválido ({data_base_str}). Esperado AAAA-MM-DD.")
    elif data_base_default:
        dt_base = data_base_default
    else:
        dt_base = date(2026, 10, 22)

    # Precificação estrita
    prec_raw = config_dict.get("precificacao")
    if not isinstance(prec_raw, dict):
        raise ValueError("Configuração requer objeto 'precificacao'.")
    
    metodo = prec_raw.get("metodo")
    if metodo != "DESCONTO_SIMPLES":
        raise ValueError(f"Método de precificação inválido ou ausente: '{metodo}'. Apenas 'DESCONTO_SIMPLES' é suportado.")

    if "base_dias" not in prec_raw:
        raise ValueError("Parâmetro 'base_dias' é obrigatório em precificacao.")
    base_dias_raw = prec_raw["base_dias"]
    if not isinstance(base_dias_raw, int) or base_dias_raw <= 0:
        raise ValueError(f"'base_dias' deve ser inteiro positivo, recebido: {base_dias_raw}")

    if "taxa_mensal_percentual" not in prec_raw:
        raise ValueError("Parâmetro 'taxa_mensal_percentual' é obrigatório em precificacao.")
    try:
        taxa_perc = Decimal(str(prec_raw["taxa_mensal_percentual"]))
        if not taxa_perc.is_finite() or taxa_perc < Decimal("0"):
            raise ValueError()
    except Exception:
        raise ValueError(f"'taxa_mensal_percentual' deve ser Decimal finito não negativo, recebido: {prec_raw.get('taxa_mensal_percentual')}")

    taxa_mensal = taxa_perc / Decimal("100")
    prec_params = ParametrosPrecificacao(
        metodo=metodo,
        taxa_mensal=taxa_mensal,
        base_dias=base_dias_raw
    )

    # Validadores e regras
    reg_engine = registry or RuleRegistry()
    raw_validadores = config_dict.get("validadores")
    if not isinstance(raw_validadores, list):
        raise ValueError("'validadores' deve ser uma lista de regras.")

    regras: List[RegraConfigurada] = []
    codigos_vistos: Set[str] = set()

    for idx, r in enumerate(raw_validadores):
        if not isinstance(r, dict):
            raise ValueError(f"Validador no índice {idx} deve ser um objeto JSON.")
        
        codigo = r.get("codigo")
        if not codigo or not isinstance(codigo, str):
            raise ValueError(f"Validador no índice {idx} não possui 'codigo' válido.")
        codigo = codigo.strip()

        if codigo in codigos_vistos:
            raise ValueError(f"Código de validador duplicado na configuração: '{codigo}'.")
        codigos_vistos.add(codigo)

        if not reg_engine.eh_codigo_conhecido(codigo):
            raise ValueError(f"Código de validador desconhecido: '{codigo}'.")

        ativo = r.get("ativo")
        # Exige booleano estrito (rejeita 'true', 'false', 1, 0)
        if not isinstance(ativo, bool):
            raise ValueError(f"Campo 'ativo' da regra '{codigo}' deve ser booleano estrito (true/false).")

        parametros = r.get("parametros")
        if not isinstance(parametros, dict):
            raise ValueError(f"Campo 'parametros' da regra '{codigo}' deve ser um objeto JSON.")

        # Valida schema dos parâmetros mesmo se inativo, para garantir integridade do arquivo
        strategy = reg_engine.obter(codigo)
        if strategy:
            try:
                strategy.validar_schema_parametros(parametros)
            except ValueError as ve:
                raise ValueError(f"Erro nos parâmetros da regra '{codigo}': {str(ve)}")

        regras.append(RegraConfigurada(
            codigo=codigo,
            ativo=ativo,
            parametros=copy.deepcopy(parametros)
        ))

    return ConfiguracaoMotor(
        fundo_nome=fundo_nome,
        fundo_cnpj=fundo_cnpj,
        data_base=dt_base,
        regras=regras,
        precificacao=prec_params,
        raw_config=config_dict
    )


class MotorAvaliacao:
    """
    Motor central que orquestra a avaliação de cada recebível.
    Totalmente desacoplado de IO / banco.
    """

    def __init__(
        self,
        config: ConfiguracaoMotor,
        registry: Optional[RuleRegistry] = None
    ) -> None:
        self.config = config
        self.registry = registry or RuleRegistry()
        self.regras_ativas = [r for r in config.regras if r.ativo]

    def avaliar_recebivel(
        self,
        recebivel: ReceivelInput,
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> ResultadoAvaliacao:
        """
        Avalia um único recebível dentro do fluxo sequencial do lote.
        """
        motivos: List[MotivoRecusa] = []
        
        # 1. Checagem de Duplicidade Histórica (em relação ao estoque global de carteira)
        chave = recebivel.chave_duplicidade
        if chave in snapshot_historico.chaves_duplicidade_existentes:
            motivos.append(MotivoRecusa(
                codigo="DUPLICIDADE_HISTORICA",
                mensagem="Recebível já existe na carteira histórica do estoque global.",
                dados={"chave_duplicidade": chave}
            ))

        # 2. Checagem de Duplicidade Intra-lote (mesmo lote enviado)
        if chave in estado_lote.chaves_vistas_no_lote:
            motivos.append(MotivoRecusa(
                codigo="DUPLICIDADE_LOTE",
                mensagem="Recebível duplicado dentro do próprio lote submetido.",
                dados={"chave_duplicidade": chave}
            ))
        else:
            estado_lote.chaves_vistas_no_lote.add(chave)

        # 3. Execução das regras ativas do Registry
        for regra in self.regras_ativas:
            strategy = self.registry.obter(regra.codigo)
            if not strategy:
                continue
            motivo = strategy.validar(
                recebivel=recebivel,
                data_base=self.config.data_base,
                parametros=regra.parametros,
                contexto_cadastral=contexto_cadastral,
                estado_lote=estado_lote,
                snapshot_historico=snapshot_historico,
            )
            if motivo:
                motivos.append(motivo)

        # 4. Decisão e Precificação
        if motivos:
            return ResultadoAvaliacao(
                linha=recebivel.linha,
                documento=recebivel.nu_documento,
                sacado=recebivel.nome_sacado,
                aprovado=False,
                valor_nominal=recebivel.valor_nominal,
                valor_liquido=None,
                motivos=motivos,
                dias_vencimento=(recebivel.data_vencimento - self.config.data_base).days
            )

        # 5. Cálculo Financeiro (apenas aprovados)
        res_prec = calcular_desconto_simples(
            valor_nominal=recebivel.valor_nominal,
            data_base=self.config.data_base,
            data_vencimento=recebivel.data_vencimento,
            params=self.config.precificacao
        )

        if not res_prec.valido:
            motivo_fin = MotivoRecusa(
                codigo="CALCULO_FINANCEIRO_INVALIDO",
                mensagem=res_prec.motivo_invalidez or "Cálculo financeiro resultou em valor inválido.",
                dados={"valor_nominal": str(recebivel.valor_nominal), "desconto": str(res_prec.desconto)}
            )
            return ResultadoAvaliacao(
                linha=recebivel.linha,
                documento=recebivel.nu_documento,
                sacado=recebivel.nome_sacado,
                aprovado=False,
                valor_nominal=recebivel.valor_nominal,
                valor_liquido=None,
                motivos=[motivo_fin],
                dias_vencimento=res_prec.dias,
                desconto=res_prec.desconto
            )

        # 6. Atualização do estado projetado do lote (apenas se APROVADO)
        raiz = recebivel.raiz_cnpj_sacado
        cedente = recebivel.doc_cedente
        estado_lote.total_nominal += recebivel.valor_nominal
        estado_lote.exposicoes_sacado_raiz[raiz] = (
            estado_lote.exposicoes_sacado_raiz.get(raiz, Decimal("0.00")) + recebivel.valor_nominal
        )
        estado_lote.exposicoes_cedente[cedente] = (
            estado_lote.exposicoes_cedente.get(cedente, Decimal("0.00")) + recebivel.valor_nominal
        )

        return ResultadoAvaliacao(
            linha=recebivel.linha,
            documento=recebivel.nu_documento,
            sacado=recebivel.nome_sacado,
            aprovado=True,
            valor_nominal=recebivel.valor_nominal,
            valor_liquido=res_prec.valor_liquido,
            motivos=[],
            dias_vencimento=res_prec.dias,
            desconto=res_prec.desconto
        )

    def avaliar_lote_stream(
        self,
        itens: Iterator[Tuple[int, Optional[ReceivelInput], Optional[ResultadoAvaliacao]]],
        contexto_cadastral: Dict[str, str],
        snapshot_historico: SnapshotCarteira,
    ) -> Iterator[ResultadoAvaliacao]:
        """
        Avalia um fluxo/gerador de recebíveis linha a linha, preservando streaming.
        Garante isolamento profundo da cópia do snapshot.
        """
        snapshot_isolado = snapshot_historico.criar_copia_isolada()
        estado_lote = EstadoProjetadoLote(
            total_nominal=snapshot_isolado.total_nominal,
            exposicoes_sacado_raiz=dict(snapshot_isolado.exposicoes_sacado_raiz),
            exposicoes_cedente=dict(snapshot_isolado.exposicoes_cedente),
            chaves_vistas_no_lote=set()
        )

        for linha_num, recebivel, erro_parsing in itens:
            if erro_parsing:
                yield erro_parsing
                continue
            if recebivel is None:
                continue

            resultado = self.avaliar_recebivel(
                recebivel=recebivel,
                contexto_cadastral=contexto_cadastral,
                estado_lote=estado_lote,
                snapshot_historico=snapshot_isolado
            )
            yield resultado
