"""
Matriz Adversarial de 20 Casos Baseada Exclusivamente no JSON Real e Contratos Oficiais.
Contratos reais:
- validadores_antecipe.json:
    - CNPJ_SACADO_VALIDO (ativo: true)
    - SITUACAO_CADASTRAL_SACADO (ativo: true, situacoes_aceitas: ["ATIVA"])
    - TIPO_RECEBIVEL (ativo: true, tipos_aceitos: ["Duplicata", "Duplicata de Serviço"])
    - VALOR_MINIMO (ativo: true, valor_minimo: 100.0)
    - NAO_VENCIDA (ativo: true)
    - PRAZO_MAXIMO (ativo: true, prazo_maximo_dias: 180)
    - CONCENTRACAO_MAXIMA_SACADO (ativo: true, percentual_maximo: 10.0, agrupamento: "RAIZ_CNPJ")
    - PRAZO_MINIMO (ativo: false)
    - CONCENTRACAO_MAXIMA_CEDENTE (ativo: false)
- Precificação real:
    - metodo: "DESCONTO_SIMPLES"
    - taxa_mensal_percentual: 2.0
    - base_dias: 30
- Data base padrão: 2026-10-22
- Cabeçalhos de CSV reais (11 colunas):
    NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;
    NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO
- Motor de Avaliação real:
    MotorAvaliacao(config=carregar_configuracao(...))
    avaliar_recebivel(recebivel, contexto_cadastral, estado_lote, snapshot_historico)
    ou avaliar_lote_stream(itens, contexto_cadastral, snapshot_historico)
"""
import copy
import io
import json
import os
import unittest
from datetime import date
from decimal import Decimal

try:
    from backend.domain.cnpj import validar_cnpj, normalizar_cnpj
    from backend.domain.engine import ConfiguracaoMotor, MotorAvaliacao, carregar_configuracao
    from backend.domain.ingestion import iterar_csv_recebiveis, validar_cabecalho
    from backend.domain.models import (
        EstadoProjetadoLote,
        MotivoRecusa,
        ReceivelInput,
        ResultadoAvaliacao,
        SituacaoCadastral,
        SnapshotCarteira,
    )
except ImportError:
    from Codex.antecipe.backend.domain.cnpj import validar_cnpj, normalizar_cnpj
    from Codex.antecipe.backend.domain.engine import ConfiguracaoMotor, MotorAvaliacao, carregar_configuracao
    from Codex.antecipe.backend.domain.ingestion import iterar_csv_recebiveis, validar_cabecalho
    from Codex.antecipe.backend.domain.models import (
        EstadoProjetadoLote,
        MotivoRecusa,
        ReceivelInput,
        ResultadoAvaliacao,
        SituacaoCadastral,
        SnapshotCarteira,
    )


def carregar_json_real() -> dict:
    """Carrega o arquivo validadores_antecipe.json original com parse_float=Decimal."""
    caminho = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "validadores_antecipe.json"))
    if not os.path.exists(caminho):
        caminho = "validadores_antecipe.json"
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f, parse_float=Decimal)


class TestMatriz20CasosReais(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_json = carregar_json_real()
        cls.config_padrao = carregar_configuracao(cls.raw_json, data_base_default=date(2026, 10, 22))

    def setUp(self):
        self.config = copy.deepcopy(self.config_padrao)
        self.motor = MotorAvaliacao(self.config)
        # CNPJs matematicamente válidos
        self.contexto_cadastral = {
            "11222333000181": SituacaoCadastral.ATIVA.value,
            "11222333000262": SituacaoCadastral.ATIVA.value,  # Filial
            "99888777000100": SituacaoCadastral.INATIVA.value,  # Inativa com DV válido
            "00000000000191": SituacaoCadastral.ATIVA.value,  # Banco do Brasil
        }
        # Snapshot base de carteira com total suficiente para absorver notas dentro do limite de 10%
        self.snapshot_base = SnapshotCarteira(
            total_nominal=Decimal("100000.00"),
            exposicoes_sacado_raiz={"00000000": Decimal("5000.00")}
        )

    # 1. Imutabilidade e versão congelada por simulação
    def test_caso_01_imutabilidade_configuracao(self):
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-100", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("1500.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertTrue(res.aprovado)
        # Garante que taxa e regras permanecem congeladas no motor
        self.assertEqual(self.motor.config.precificacao.taxa_mensal, Decimal("0.02"))

    # 2. Duplicidade intra-lote: primeira ocorrência recusada bloqueia ocorrência subsequente
    def test_caso_02_duplicidade_intra_lote_apos_recusa(self):
        # 1ª ocorrência com valor abaixo de 100.00 (recusada)
        rec1 = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-DUPL-01", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("50.00"), data_vencimento=date(2026, 11, 20)
        )
        # 2ª ocorrência com valor válido (R$ 500.00)
        rec2 = ReceivelInput(
            linha=2, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-DUPL-01", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 11, 20)
        )
        itens = [(1, rec1, None), (2, rec2, None)]
        res = list(self.motor.avaliar_lote_stream(itens, self.contexto_cadastral, self.snapshot_base))
        
        self.assertFalse(res[0].aprovado)
        self.assertEqual(res[0].motivos[0].codigo, "VALOR_MINIMO")
        # Segunda é recusada por duplicidade de lote
        self.assertFalse(res[1].aprovado)
        self.assertEqual(res[1].motivos[0].codigo, "DUPLICIDADE_LOTE")

    # 3. Parcelas legítimas vs parcelas duplicadas (mesmo número com vencimentos distintos)
    def test_caso_03_parcelas_legitimas_vencimentos_distintos(self):
        rec1 = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-PARC", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 11, 20)
        )
        rec2 = ReceivelInput(
            linha=2, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-PARC", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 12, 20)
        )
        itens = [(1, rec1, None), (2, rec2, None)]
        res = list(self.motor.avaliar_lote_stream(itens, self.contexto_cadastral, self.snapshot_base))
        self.assertTrue(res[0].aprovado)
        self.assertTrue(res[1].aprovado)

    # 4. Concentração máxima por raiz de CNPJ: filiais compartilham o teto
    def test_caso_04_filial_compartilha_teto_concentracao(self):
        # Carteira histórica R$ 100.000. Matriz (raiz 11222333) já possui R$ 9.500.
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("100000.00"),
            exposicoes_sacado_raiz={"11222333": Decimal("9500.00")}
        )
        # Filial tenta adicionar R$ 2.000 (totalizaria 11.500 / 102.000 = 11.27% > 10.0%)
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="FILIAL SACADO", doc_sacado="11222333000262",
            nu_documento="NF-FILIAL", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("2000.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, snapshot))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "CONCENTRACAO_MAXIMA_SACADO")

    # 5. Concentração exatamente no limite de 10.00%
    def test_caso_05_concentracao_exatamente_no_limite(self):
        # Total prévio 90.000. Nova nota de 10.000 -> Total 100.000. Sacado 10.000 / 100.000 = 10.00%
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("90000.00"),
            exposicoes_sacado_raiz={}
        )
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-EXATO-10", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("10000.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, snapshot))[0]
        self.assertTrue(res.aprovado)

    # 6. Concentração acumulada intra-lote (duas notas somadas estouram o limite)
    def test_caso_06_concentracao_acumulada_intra_lote(self):
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("90000.00"),
            exposicoes_sacado_raiz={}
        )
        rec1 = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-ACUM-1", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("10000.00"), data_vencimento=date(2026, 11, 20)
        )
        rec2 = ReceivelInput(
            linha=2, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-ACUM-2", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 11, 20)
        )
        itens = [(1, rec1, None), (2, rec2, None)]
        res = list(self.motor.avaliar_lote_stream(itens, self.contexto_cadastral, snapshot))
        self.assertTrue(res[0].aprovado)
        self.assertFalse(res[1].aprovado)
        self.assertEqual(res[1].motivos[0].codigo, "CONCENTRACAO_MAXIMA_SACADO")

    # 7. Sacado com histórico já estourado não pode agravar exposição
    def test_caso_07_sacado_ja_estourado_bloqueia_novas_notas(self):
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("100000.00"),
            exposicoes_sacado_raiz={"11222333": Decimal("15000.00")}  # 15.00%
        )
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-ESTOURO", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, snapshot))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "CONCENTRACAO_MAXIMA_SACADO")

    # 8. Situação cadastral do sacado desconhecida / NAO_VERIFICADA
    def test_caso_08_situacao_cadastral_desconhecida(self):
        # CNPJ com DV válido matematicamente, mas ausente do contexto cadastral
        cnpj_valido_sem_cadastro = "88777666000100"
        self.assertTrue(validar_cnpj(cnpj_valido_sem_cadastro))
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO DESCONHECIDO", doc_sacado=cnpj_valido_sem_cadastro,
            nu_documento="NF-DESCONHECIDO", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "SITUACAO_CADASTRAL_SACADO")

    # 9. Situação cadastral do sacado INATIVA
    def test_caso_09_situacao_cadastral_inativa(self):
        # CNPJ 99888777000100 com DV válido, mapeado explicitamente como INATIVA
        self.assertTrue(validar_cnpj("99888777000100"))
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO INATIVO", doc_sacado="99888777000100",
            nu_documento="NF-INATIVA", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "SITUACAO_CADASTRAL_SACADO")

    # 10. Validação matemática de CNPJ com dígito verificador incorreto
    def test_caso_10_cnpj_sacado_invalido(self):
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO CNPJ INVALIDO", doc_sacado="11222333000199", # DV incorreto
            nu_documento="NF-CNPJ-BAD", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "CNPJ_SACADO_VALIDO")

    # 11. Tipo de recebível não aceito (ex: Boleto)
    def test_caso_11_tipo_recebivel_rejeitado(self):
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-BOLETO", tipo_recebivel="Boleto",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "TIPO_RECEBIVEL")

    # 12. Delimitador ponto e vírgula e decimal com vírgula no parser real
    def test_caso_12_csv_ponto_e_virgula_e_decimal(self):
        csv_content = io.StringIO(
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE A;00.111.222/0001-33;SACADO B;11.222.333/0001-81;DOC123;Duplicata;2.278,08;20/11/2026;\n"
        )
        itens = list(iterar_csv_recebiveis(csv_content))
        self.assertEqual(len(itens), 1)
        idx, rec, erro = itens[0]
        self.assertIsNone(erro)
        self.assertEqual(rec.valor_nominal, Decimal("2278.08"))
        self.assertEqual(rec.data_vencimento, date(2026, 11, 20))

    # 13. CSV malformado (linha com colunas insuficientes)
    def test_caso_13_csv_linha_malformada(self):
        csv_content = io.StringIO(
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE A\n"
        )
        itens = list(iterar_csv_recebiveis(csv_content))
        self.assertEqual(len(itens), 1)
        idx, rec, erro = itens[0]
        self.assertIsNone(rec)
        self.assertIsNotNone(erro)
        self.assertEqual(erro.motivos[0].codigo, "LINHA_MALFORMADA_COLUNAS")

    # 14. Validação de cabeçalho ausente ou com nomes divergentes
    def test_caso_14_cabecalho_invalido(self):
        headers_divergentes = ["COL1", "COL2", "COL3"]
        valido, faltantes, erro_msg = validar_cabecalho(headers_divergentes)
        self.assertFalse(valido)
        self.assertIn("DATA_VENCIMENTO_ORIGINAL", faltantes)

    # 15. Nota vencida (vencimento anterior à data base 2026-10-22)
    def test_caso_15_nota_vencida_recusada(self):
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-VENCIDA", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2026, 10, 20) # Data-base é 22/10
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "NAO_VENCIDA")

    # 16. Prazo exatamente no limite máximo (180 dias)
    def test_caso_16_prazo_exatamente_maximo(self):
        # 2026-10-22 + 180 dias = 2027-04-20
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-MAX-PRAZO", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2027, 4, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertTrue(res.aprovado)

    # 17. Prazo excedido por 1 dia (181 dias)
    def test_caso_17_prazo_excedido_por_um_dia(self):
        # 2026-10-22 + 181 dias = 2027-04-21
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-PRAZO-181", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("500.00"), data_vencimento=date(2027, 4, 21)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "PRAZO_MAXIMO")

    # 18. Valor exatamente no limite mínimo (R$ 100,00)
    def test_caso_18_valor_exatamente_minimo(self):
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-EXATO-100", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("100.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertTrue(res.aprovado)

    # 19. Valor abaixo do mínimo por 1 centavo (R$ 99,99)
    def test_caso_19_valor_abaixo_minimo_um_centavo(self):
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-99-99", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("99.99"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "VALOR_MINIMO")

    # 20. Cálculo financeiro exato com desconto simples e arredondamento HALF_UP
    def test_caso_20_calculo_financeiro_desconto_simples_real(self):
        # Taxa mensal 2.0% -> 0.02 / 30 dias.
        # Prazo: 29 dias (de 22/10/2026 a 20/11/2026).
        # Valor nominal: R$ 1.000,00.
        # Desconto = 1000.00 * (0.02 / 30) * 29 = 19.333333...
        # Arredondamento HALF_UP: 19.33.
        # Valor líquido = 1000.00 - 19.33 = 980.67.
        rec = ReceivelInput(
            linha=1, nome_fundo="ANTECIPE FIDC", doc_fundo="92234400000180",
            nome_cedente="CEDENTE S/A", doc_cedente="00111222000133",
            nome_sacado="SACADO ATIVO", doc_sacado="11222333000181",
            nu_documento="NF-FINANCEIRO", tipo_recebivel="Duplicata",
            valor_nominal=Decimal("1000.00"), data_vencimento=date(2026, 11, 20)
        )
        res = list(self.motor.avaliar_lote_stream([(1, rec, None)], self.contexto_cadastral, self.snapshot_base))[0]
        self.assertTrue(res.aprovado)
        self.assertEqual(res.desconto, Decimal("19.33"))
        self.assertEqual(res.valor_liquido, Decimal("980.67"))


if __name__ == "__main__":
    unittest.main()
