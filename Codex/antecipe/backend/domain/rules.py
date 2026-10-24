"""
Motor de regras com Strategy Pattern e Registry.
Implementa TODOS os 9 tipos conhecidos de validadores com schema estrito:
1. CNPJ_SACADO_VALIDO
2. SITUACAO_CADASTRAL_SACADO
3. TIPO_RECEBIVEL
4. VALOR_MINIMO
5. NAO_VENCIDA
6. PRAZO_MAXIMO
7. CONCENTRACAO_MAXIMA_SACADO
8. PRAZO_MINIMO
9. CONCENTRACAO_MAXIMA_CEDENTE
"""
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Set

from .cnpj import validar_cnpj
from .models import (
    EstadoProjetadoLote,
    MotivoRecusa,
    ReceivelInput,
    SituacaoCadastral,
    SnapshotCarteira,
)


class ValidadorStrategy(ABC):
    """Contrato base de um validador no Registry."""
    
    @property
    @abstractmethod
    def codigo(self) -> str:
        pass

    @abstractmethod
    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        """Valida tipos e restrições dos parâmetros na carga da regra. Levanta ValueError se inválido."""
        pass

    @abstractmethod
    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        """Executa a validação do recebível."""
        pass


class ValidadorCnpjSacadoValido(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "CNPJ_SACADO_VALIDO"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        # Sem parâmetros obrigatórios
        pass

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        if not validar_cnpj(recebivel.doc_sacado):
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem="CNPJ do sacado possui dígitos verificadores inválidos ou formato incorreto.",
                dados={"doc_sacado_mascarado": f"***{recebivel.doc_sacado[-4:]}" if len(recebivel.doc_sacado) >= 4 else "***"}
            )
        return None


class ValidadorSituacaoCadastralSacado(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "SITUACAO_CADASTRAL_SACADO"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        if "situacoes_aceitas" not in parametros:
            raise ValueError(f"Regra {self.codigo} requer o parâmetro 'situacoes_aceitas'.")
        sits = parametros["situacoes_aceitas"]
        if not isinstance(sits, list) or len(sits) == 0:
            raise ValueError(f"Regra {self.codigo}: 'situacoes_aceitas' deve ser uma lista não vazia.")

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        situacoes_aceitas = [str(s).upper() for s in parametros.get("situacoes_aceitas", [])]
        situacao_informada = contexto_cadastral.get(recebivel.doc_sacado)
        
        if not situacao_informada:
            situacao = SituacaoCadastral.NAO_VERIFICADA.value
        else:
            situacao = str(situacao_informada).upper()

        if situacao == SituacaoCadastral.NAO_VERIFICADA.value:
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem="Não foi possível confirmar que o sacado está ativo na fonte cadastral utilizada. Por isso, esta nota foi recusada. Confirme ou atualize o cadastro e envie novamente.",
                dados={"situacao_encontrada": situacao, "validador": self.codigo}
            )
        elif situacao not in situacoes_aceitas:
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem=f"Situação cadastral do sacado é '{situacao}', mas o fundo aceita apenas: {', '.join(situacoes_aceitas)}.",
                dados={"situacao_encontrada": situacao, "situacoes_aceitas": situacoes_aceitas}
            )
        return None


class ValidadorTipoRecebivel(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "TIPO_RECEBIVEL"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        if "tipos_aceitos" not in parametros:
            raise ValueError(f"Regra {self.codigo} requer o parâmetro 'tipos_aceitos'.")
        tipos = parametros["tipos_aceitos"]
        if not isinstance(tipos, list) or len(tipos) == 0:
            raise ValueError(f"Regra {self.codigo}: 'tipos_aceitos' deve ser uma lista não vazia.")

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        tipos_aceitos = [str(t).strip().upper() for t in parametros.get("tipos_aceitos", [])]
        tipo_atual = recebivel.tipo_recebivel.strip().upper()
        
        if tipo_atual not in tipos_aceitos:
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem=f"Tipo de recebível '{recebivel.tipo_recebivel}' não é aceito pelo fundo.",
                dados={"tipo_encontrado": recebivel.tipo_recebivel, "tipos_aceitos": parametros.get("tipos_aceitos", [])}
            )
        return None


class ValidadorValorMinimo(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "VALOR_MINIMO"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        if "valor_minimo" not in parametros:
            raise ValueError(f"Regra {self.codigo} requer o parâmetro 'valor_minimo'.")
        try:
            val = Decimal(str(parametros["valor_minimo"]))
            if not val.is_finite() or val < Decimal("0"):
                raise ValueError()
        except Exception:
            raise ValueError(f"Regra {self.codigo}: 'valor_minimo' deve ser Decimal finito e positivo.")

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        valor_min = Decimal(str(parametros["valor_minimo"]))
        if recebivel.valor_nominal < valor_min:
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem=f"Valor nominal de R$ {recebivel.valor_nominal:.2f} é inferior ao mínimo permitido de R$ {valor_min:.2f}.",
                dados={"valor_nominal": str(recebivel.valor_nominal), "valor_minimo": str(valor_min)}
            )
        return None


class ValidadorNaoVencida(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "NAO_VENCIDA"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        pass

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        if recebivel.data_vencimento < data_base:
            dias_atraso = (data_base - recebivel.data_vencimento).days
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem=f"Recebível já vencido há {dias_atraso} dia(s) em relação à data-base ({data_base.strftime('%d/%m/%Y')}).",
                dados={"vencimento": recebivel.data_vencimento.isoformat(), "data_base": data_base.isoformat(), "dias_atraso": dias_atraso}
            )
        return None


class ValidadorPrazoMaximo(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "PRAZO_MAXIMO"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        if "prazo_maximo_dias" not in parametros:
            raise ValueError(f"Regra {self.codigo} requer o parâmetro 'prazo_maximo_dias'.")
        dias = parametros["prazo_maximo_dias"]
        if not isinstance(dias, int) or dias <= 0:
            raise ValueError(f"Regra {self.codigo}: 'prazo_maximo_dias' deve ser inteiro positivo.")

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        max_dias = int(parametros["prazo_maximo_dias"])
        dias = (recebivel.data_vencimento - data_base).days
        
        if dias > max_dias:
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem=f"Prazo até o vencimento é de {dias} dias, excedendo o limite máximo permitido de {max_dias} dias.",
                dados={"dias_vencimento": dias, "prazo_maximo_dias": max_dias}
            )
        return None


class ValidadorPrazoMinimo(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "PRAZO_MINIMO"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        if "prazo_minimo_dias" not in parametros:
            raise ValueError(f"Regra {self.codigo} requer o parâmetro 'prazo_minimo_dias'.")
        dias = parametros["prazo_minimo_dias"]
        if not isinstance(dias, int) or dias < 0:
            raise ValueError(f"Regra {self.codigo}: 'prazo_minimo_dias' deve ser inteiro não negativo.")

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        min_dias = int(parametros["prazo_minimo_dias"])
        dias = (recebivel.data_vencimento - data_base).days
        
        if dias < min_dias:
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem=f"Prazo até o vencimento é de {dias} dias, inferior ao prazo mínimo exigido de {min_dias} dias.",
                dados={"dias_vencimento": dias, "prazo_minimo_dias": min_dias}
            )
        return None


class ValidadorConcentracaoMaximaSacado(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "CONCENTRACAO_MAXIMA_SACADO"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        if "percentual_maximo" not in parametros:
            raise ValueError(f"Regra {self.codigo} requer o parâmetro 'percentual_maximo'.")
        try:
            perc = Decimal(str(parametros["percentual_maximo"]))
            if not perc.is_finite() or perc <= Decimal("0") or perc > Decimal("100"):
                raise ValueError()
        except Exception:
            raise ValueError(f"Regra {self.codigo}: 'percentual_maximo' deve ser Decimal finito entre 0 e 100.")

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        perc_max = Decimal(str(parametros["percentual_maximo"]))
        limite_fracao = perc_max / Decimal("100")
        
        raiz = recebivel.raiz_cnpj_sacado
        exposicao_atual = estado_lote.exposicoes_sacado_raiz.get(raiz, Decimal("0.00"))
        total_atual = estado_lote.total_nominal
        
        exposicao_projetada = exposicao_atual + recebivel.valor_nominal
        total_projetado = total_atual + recebivel.valor_nominal
        
        if total_projetado <= Decimal("0.00"):
            return None
            
        fracao_projetada = exposicao_projetada / total_projetado
        
        if fracao_projetada > limite_fracao:
            perc_calculado = (fracao_projetada * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem=(
                    f"Concentração projetada por raiz do sacado ({perc_calculado}%) excede o limite "
                    f"máximo configurado de {perc_max}%."
                ),
                dados={
                    "raiz_cnpj": raiz,
                    "concentracao_projetada_percentual": str(perc_calculado),
                    "limite_percentual": str(perc_max),
                    "exposicao_projetada": str(exposicao_projetada),
                    "carteira_total_projetada": str(total_projetado)
                }
            )
        return None


class ValidadorConcentracaoMaximaCedente(ValidadorStrategy):
    @property
    def codigo(self) -> str:
        return "CONCENTRACAO_MAXIMA_CEDENTE"

    def validar_schema_parametros(self, parametros: Dict[str, Any]) -> None:
        if "percentual_maximo" not in parametros:
            raise ValueError(f"Regra {self.codigo} requer o parâmetro 'percentual_maximo'.")
        try:
            perc = Decimal(str(parametros["percentual_maximo"]))
            if not perc.is_finite() or perc <= Decimal("0") or perc > Decimal("100"):
                raise ValueError()
        except Exception:
            raise ValueError(f"Regra {self.codigo}: 'percentual_maximo' deve ser Decimal finito entre 0 e 100.")

    def validar(
        self,
        recebivel: ReceivelInput,
        data_base: date,
        parametros: Dict[str, Any],
        contexto_cadastral: Dict[str, str],
        estado_lote: EstadoProjetadoLote,
        snapshot_historico: SnapshotCarteira,
    ) -> Optional[MotivoRecusa]:
        perc_max = Decimal(str(parametros["percentual_maximo"]))
        limite_fracao = perc_max / Decimal("100")
        
        cedente = recebivel.doc_cedente
        exposicao_atual = estado_lote.exposicoes_cedente.get(cedente, Decimal("0.00"))
        total_atual = estado_lote.total_nominal
        
        exposicao_projetada = exposicao_atual + recebivel.valor_nominal
        total_projetado = total_atual + recebivel.valor_nominal
        
        if total_projetado <= Decimal("0.00"):
            return None
            
        fracao_projetada = exposicao_projetada / total_projetado
        
        if fracao_projetada > limite_fracao:
            perc_calculado = (fracao_projetada * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return MotivoRecusa(
                codigo=self.codigo,
                mensagem=(
                    f"Concentração projetada do cedente ({perc_calculado}%) excede o limite "
                    f"máximo configurado de {perc_max}%."
                ),
                dados={
                    "doc_cedente": cedente,
                    "concentracao_projetada_percentual": str(perc_calculado),
                    "limite_percentual": str(perc_max),
                    "exposicao_projetada": str(exposicao_projetada),
                    "carteira_total_projetada": str(total_projetado)
                }
            )
        return None


class RuleRegistry:
    """Registro de estratégias de validação com verificação de integridade."""
    
    def __init__(self) -> None:
        self._strategies: Dict[str, ValidadorStrategy] = {}
        self.registrar(ValidadorCnpjSacadoValido())
        self.registrar(ValidadorSituacaoCadastralSacado())
        self.registrar(ValidadorTipoRecebivel())
        self.registrar(ValidadorValorMinimo())
        self.registrar(ValidadorNaoVencida())
        self.registrar(ValidadorPrazoMaximo())
        self.registrar(ValidadorPrazoMinimo())
        self.registrar(ValidadorConcentracaoMaximaSacado())
        self.registrar(ValidadorConcentracaoMaximaCedente())

    def registrar(self, strategy: ValidadorStrategy) -> None:
        self._strategies[strategy.codigo] = strategy

    def obter(self, codigo: str) -> Optional[ValidadorStrategy]:
        return self._strategies.get(codigo)

    def codigos_disponiveis(self) -> List[str]:
        return list(self._strategies.keys())

    def eh_codigo_conhecido(self, codigo: str) -> bool:
        return codigo in self._strategies
