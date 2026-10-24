import csv
import io
import json
import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "Codex" / "antecipe"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from backend.domain.cnpj import validar_cnpj
from backend.domain.engine import MotorAvaliacao, carregar_configuracao
from backend.domain.ingestion import (
    CABECALHOS_OBRIGATORIOS,
    iterar_csv_recebiveis,
    normalizar_documento,
    parse_data_br,
    parse_decimal_br,
    validar_cabecalho,
)
from backend.domain.models import EstadoProjetadoLote, ReceivelInput, SnapshotCarteira
from backend.domain.pricing import LIMITE_MAXIMO_MONETARIO, ParametrosPrecificacao, calcular_desconto_simples
from backend.domain.rules import RuleRegistry
from backend.application.sample_batches import iterar_linhas_lote_sintetico


def _make_recebivel(
    linha: int = 2,
    nome_fundo: str = "ANTECIPE FIDC",
    doc_fundo: str = "12345678000199",
    nome_cedente: str = "INDUSTRIA BRASIL SA",
    doc_cedente: str = "11222333000181",
    nome_sacado: str = "COMERCIAL ALPHA LTDA",
    doc_sacado: str = "04252011000110",
    nu_documento: str = "NF-1001",
    tipo_recebivel: str = "Duplicata",
    valor_nominal: Decimal = Decimal("5000.00"),
    data_vencimento: date = date(2026, 11, 21),
    data_aquisicao: date = date(2026, 10, 22),
) -> ReceivelInput:
    return ReceivelInput(
        linha=linha,
        nome_fundo=nome_fundo,
        doc_fundo=doc_fundo,
        nome_cedente=nome_cedente,
        doc_cedente=doc_cedente,
        nome_sacado=nome_sacado,
        doc_sacado=doc_sacado,
        nu_documento=nu_documento,
        tipo_recebivel=tipo_recebivel,
        valor_nominal=valor_nominal,
        data_vencimento=data_vencimento,
        data_aquisicao=data_aquisicao,
    )


class AntecipeDomainSuiteTests(unittest.TestCase):
    """Suíte abrangente de testes de domínio, regras, ingestão CSV e precisão financeira (Elias)."""

    @classmethod
    def setUpClass(cls):
        cls.validadores_path = ROOT / "validadores_antecipe.json"
        cls.raw_json = json.loads(cls.validadores_path.read_text(encoding="utf-8"), parse_float=Decimal)
        cls.data_base = date(2026, 10, 22)
        cls.config = carregar_configuracao(cls.raw_json, data_base_default=cls.data_base)

    def _novo_estado_e_snapshot(self, total_carteira: Decimal = Decimal("500000.00")):
        snapshot = SnapshotCarteira(
            total_nominal=total_carteira,
            exposicoes_sacado_raiz={"04252011": Decimal("10000.00")},
            exposicoes_cedente={"11222333000181": Decimal("20000.00")},
            chaves_duplicidade_existentes=set(),
        )
        estado = EstadoProjetadoLote(
            total_nominal=snapshot.total_nominal,
            exposicoes_sacado_raiz=dict(snapshot.exposicoes_sacado_raiz),
            exposicoes_cedente=dict(snapshot.exposicoes_cedente),
            chaves_vistas_no_lote=set(),
        )
        return estado, snapshot

    def test_01_carregar_configuracao_oficial_validadores_json(self):
        self.assertEqual(self.config.fundo_nome, "ANTECIPE FIDC")
        self.assertEqual(self.config.data_base, date(2026, 10, 22))
        self.assertEqual(self.config.precificacao.metodo, "DESCONTO_SIMPLES")
        self.assertEqual(self.config.precificacao.base_dias, 30)
        self.assertEqual(self.config.precificacao.taxa_mensal, Decimal("0.02"))
        codigos_ativos = [r.codigo for r in self.config.regras if r.ativo]
        self.assertEqual(
            codigos_ativos,
            [
                "CNPJ_SACADO_VALIDO",
                "SITUACAO_CADASTRAL_SACADO",
                "TIPO_RECEBIVEL",
                "VALOR_MINIMO",
                "NAO_VENCIDA",
                "PRAZO_MAXIMO",
                "CONCENTRACAO_MAXIMA_SACADO",
            ],
        )

    def test_02_rejeita_configuracao_com_ativo_string_ou_codigo_desconhecido(self):
        bad_bool = json.loads(self.validadores_path.read_text(encoding="utf-8"))
        bad_bool["validadores"][0]["ativo"] = "true"
        with self.assertRaises(ValueError):
            carregar_configuracao(bad_bool, data_base_default=self.data_base)

        bad_code = json.loads(self.validadores_path.read_text(encoding="utf-8"))
        bad_code["validadores"][0]["codigo"] = "REGRA_INEXISTENTE_XYZ"
        with self.assertRaises(ValueError):
            carregar_configuracao(bad_code, data_base_default=self.data_base)

    def test_03_rejeita_configuracao_com_validador_duplicado_ou_metodo_invalido(self):
        dup = json.loads(self.validadores_path.read_text(encoding="utf-8"))
        dup["validadores"].append(dup["validadores"][0].copy())
        with self.assertRaises(ValueError):
            carregar_configuracao(dup, data_base_default=self.data_base)

        bad_prec = json.loads(self.validadores_path.read_text(encoding="utf-8"))
        bad_prec["precificacao"]["metodo"] = "JUROS_COMPOSTOS"
        with self.assertRaises(ValueError):
            carregar_configuracao(bad_prec, data_base_default=self.data_base)

    def test_04_validacao_algoritmica_cnpj_digitos_verificadores(self):
        self.assertTrue(validar_cnpj("04252011000110"))
        self.assertTrue(validar_cnpj("11.222.333/0001-81"))
        self.assertFalse(validar_cnpj("04252011000119"))
        self.assertFalse(validar_cnpj("00000000000000"))
        self.assertFalse(validar_cnpj("11111111111111"))
        self.assertFalse(validar_cnpj("12345678901"))

    def test_05_aprovacao_completa_e_calculo_desconto_simples_exato(self):
        motor = MotorAvaliacao(self.config)
        estado, snapshot = self._novo_estado_e_snapshot()
        rec = _make_recebivel(
            valor_nominal=Decimal("5000.00"),
            data_vencimento=date(2026, 11, 21),  # 30 dias exatos de 22/10/2026
        )
        res = motor.avaliar_recebivel(rec, {"04252011000110": "ATIVA"}, estado, snapshot)
        self.assertTrue(res.aprovado)
        self.assertEqual(res.status, "APROVADA")
        self.assertEqual(res.dias_vencimento, 30)
        # Desconto = 5000.00 * 0.02 * (30/30) = 100.00 -> Líquido = 4900.00
        self.assertEqual(res.desconto, Decimal("100.00"))
        self.assertEqual(res.valor_liquido, Decimal("4900.00"))

    def test_06_arredondamento_comercial_round_half_up_centavos(self):
        params = ParametrosPrecificacao(metodo="DESCONTO_SIMPLES", taxa_mensal=Decimal("0.025"), base_dias=30)
        # 1005.00 * 0.025 * (5 / 30) = 4.1875 -> ROUND_HALF_UP = 4.19
        res = calcular_desconto_simples(
            valor_nominal=Decimal("1005.00"),
            data_base=date(2026, 10, 22),
            data_vencimento=date(2026, 10, 27),
            params=params,
        )
        self.assertTrue(res.valido)
        self.assertEqual(res.desconto, Decimal("4.19"))
        self.assertEqual(res.valor_liquido, Decimal("1000.81"))

    def test_07_fronteira_valor_minimo_100_reais(self):
        motor = MotorAvaliacao(self.config)
        estado, snapshot = self._novo_estado_e_snapshot()
        abaixo = _make_recebivel(nu_documento="NF-99", valor_nominal=Decimal("99.99"))
        exato = _make_recebivel(nu_documento="NF-100", valor_nominal=Decimal("100.00"))

        res_abaixo = motor.avaliar_recebivel(abaixo, {"04252011000110": "ATIVA"}, estado, snapshot)
        res_exato = motor.avaliar_recebivel(exato, {"04252011000110": "ATIVA"}, estado, snapshot)

        self.assertFalse(res_abaixo.aprovado)
        self.assertIn("VALOR_MINIMO", [m.codigo for m in res_abaixo.motivos])
        self.assertTrue(res_exato.aprovado)

    def test_08_fronteira_nao_vencida_e_prazo_maximo_180_dias(self):
        motor = MotorAvaliacao(self.config)
        estado, snapshot = self._novo_estado_e_snapshot()
        cadastro = {"04252011000110": "ATIVA"}

        vencida = _make_recebivel(nu_documento="NF-VENC", data_vencimento=self.data_base - timedelta(days=1))
        no_dia = _make_recebivel(nu_documento="NF-DIA0", data_vencimento=self.data_base)
        no_limite_180 = _make_recebivel(nu_documento="NF-180D", data_vencimento=self.data_base + timedelta(days=180))
        acima_181 = _make_recebivel(nu_documento="NF-181D", data_vencimento=self.data_base + timedelta(days=181))

        self.assertIn("NAO_VENCIDA", [m.codigo for m in motor.avaliar_recebivel(vencida, cadastro, estado, snapshot).motivos])
        self.assertTrue(motor.avaliar_recebivel(no_dia, cadastro, estado, snapshot).aprovado)
        self.assertTrue(motor.avaliar_recebivel(no_limite_180, cadastro, estado, snapshot).aprovado)
        self.assertIn("PRAZO_MAXIMO", [m.codigo for m in motor.avaliar_recebivel(acima_181, cadastro, estado, snapshot).motivos])

    def test_09_tipos_recebivel_aceitos_e_recusados(self):
        motor = MotorAvaliacao(self.config)
        estado, snapshot = self._novo_estado_e_snapshot()
        cadastro = {"04252011000110": "ATIVA"}

        for idx, tipo_ok in enumerate(["Duplicata", "Duplicata de Serviço"]):
            rec = _make_recebivel(nu_documento=f"NF-OK-{idx}", tipo_recebivel=tipo_ok)
            self.assertTrue(motor.avaliar_recebivel(rec, cadastro, estado, snapshot).aprovado)

        for idx, tipo_bad in enumerate(["Cheque", "CCB", "Nota Comercial"]):
            rec = _make_recebivel(nu_documento=f"NF-BAD-{idx}", tipo_recebivel=tipo_bad)
            res = motor.avaliar_recebivel(rec, cadastro, estado, snapshot)
            self.assertFalse(res.aprovado)
            self.assertIn("TIPO_RECEBIVEL", [m.codigo for m in res.motivos])

    def test_10_situacao_cadastral_inapta_baixada_suspensa_e_nao_verificada(self):
        motor = MotorAvaliacao(self.config)
        estado, snapshot = self._novo_estado_e_snapshot()

        for idx, sit in enumerate(["INAPTA", "BAIXADA", "SUSPENSA"]):
            rec = _make_recebivel(nu_documento=f"NF-SIT-{idx}")
            res = motor.avaliar_recebivel(rec, {"04252011000110": sit}, estado, snapshot)
            self.assertFalse(res.aprovado)
            self.assertIn("SITUACAO_CADASTRAL_SACADO", [m.codigo for m in res.motivos])

        # Sacado ausente no dicionário cadastral -> NAO_VERIFICADA -> RECUSADA
        rec_ausente = _make_recebivel(nu_documento="NF-SEM-CAD")
        res_ausente = motor.avaliar_recebivel(rec_ausente, {}, estado, snapshot)
        self.assertFalse(res_ausente.aprovado)
        self.assertIn("SITUACAO_CADASTRAL_SACADO", [m.codigo for m in res_ausente.motivos])

    def test_11_antiduplicidade_historica_intralote_e_parcelas_legitimas(self):
        motor = MotorAvaliacao(self.config)
        estado, snapshot = self._novo_estado_e_snapshot()
        cadastro = {"04252011000110": "ATIVA"}

        parcela_1 = _make_recebivel(nu_documento="NF-PARC", data_vencimento=date(2026, 11, 20))
        parcela_2 = _make_recebivel(nu_documento="NF-PARC", data_vencimento=date(2026, 12, 20))
        copia_parcela_1 = _make_recebivel(nu_documento="NF-PARC", data_vencimento=date(2026, 11, 20))

        # Parcelas com mesmo número de documento mas vencimentos distintos são aceitas
        self.assertTrue(motor.avaliar_recebivel(parcela_1, cadastro, estado, snapshot).aprovado)
        self.assertTrue(motor.avaliar_recebivel(parcela_2, cadastro, estado, snapshot).aprovado)

        # Reenvio idêntico no mesmo lote gera DUPLICIDADE_LOTE
        res_dup_lote = motor.avaliar_recebivel(copia_parcela_1, cadastro, estado, snapshot)
        self.assertFalse(res_dup_lote.aprovado)
        self.assertIn("DUPLICIDADE_LOTE", [m.codigo for m in res_dup_lote.motivos])

        # Item já presente no estoque histórico gera DUPLICIDADE_HISTORICA
        item_hist = _make_recebivel(nu_documento="NF-HIST-99", data_vencimento=date(2026, 11, 25))
        snapshot.chaves_duplicidade_existentes.add(item_hist.chave_duplicidade)
        res_dup_hist = motor.avaliar_recebivel(item_hist, cadastro, estado, snapshot)
        self.assertFalse(res_dup_hist.aprovado)
        self.assertIn("DUPLICIDADE_HISTORICA", [m.codigo for m in res_dup_hist.motivos])

    def test_12_concentracao_maxima_sacado_por_raiz_cnpj_e_fronteira_10_porcento(self):
        motor = MotorAvaliacao(self.config)
        # Carteira atual = 90.000,00 com 0 de exposição para a raiz 04252011
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("90000.00"),
            exposicoes_sacado_raiz={},
            exposicoes_cedente={},
            chaves_duplicidade_existentes=set(),
        )
        estado = EstadoProjetadoLote(
            total_nominal=snapshot.total_nominal,
            exposicoes_sacado_raiz={},
            exposicoes_cedente={},
            chaves_vistas_no_lote=set(),
        )
        cadastro = {"04252011000110": "ATIVA"}

        # Nota de R$ 10.000,00 -> projetado = 10.000 / (90.000 + 10.000) = 10,00% exatos -> APROVADA!
        nota_10_exato = _make_recebivel(
            nu_documento="NF-CONC-10",
            doc_sacado="04252011000110",
            valor_nominal=Decimal("10000.00"),
        )
        res_10 = motor.avaliar_recebivel(nota_10_exato, cadastro, estado, snapshot)
        self.assertTrue(res_10.aprovado)
        self.assertEqual(estado.total_nominal, Decimal("100000.00"))
        self.assertEqual(estado.exposicoes_sacado_raiz["04252011"], Decimal("10000.00"))

        # Nova nota de R$ 500,00 da mesma raiz -> 10.500 / 100.500 = 10,45% > 10% -> RECUSADA!
        nota_excesso = _make_recebivel(
            nu_documento="NF-CONC-EXC",
            doc_sacado="04252011000110",
            valor_nominal=Decimal("500.00"),
        )
        res_exc = motor.avaliar_recebivel(nota_excesso, cadastro, estado, snapshot)
        self.assertFalse(res_exc.aprovado)
        self.assertIn("CONCENTRACAO_MAXIMA_SACADO", [m.codigo for m in res_exc.motivos])
        # Nota recusada NÃO pode alterar o saldo projetado da carteira
        self.assertEqual(estado.total_nominal, Decimal("100000.00"))
        self.assertEqual(estado.exposicoes_sacado_raiz["04252011"], Decimal("10000.00"))

    def test_13_ativacao_dinamica_regras_inativas_prazo_minimo_e_concentracao_cedente(self):
        cfg_custom = json.loads(self.validadores_path.read_text(encoding="utf-8"), parse_float=Decimal)
        for v in cfg_custom["validadores"]:
            if v["codigo"] in ("PRAZO_MINIMO", "CONCENTRACAO_MAXIMA_CEDENTE"):
                v["ativo"] = True

        config_ativa = carregar_configuracao(cfg_custom, data_base_default=self.data_base)
        motor = MotorAvaliacao(config_ativa)
        estado, snapshot = self._novo_estado_e_snapshot(total_carteira=Decimal("10000.00"))
        cadastro = {"04252011000110": "ATIVA"}

        # Prazo de 3 dias (< 5 dias de PRAZO_MINIMO) e valor alto (> 15% de CONCENTRACAO_MAXIMA_CEDENTE)
        rec = _make_recebivel(
            nu_documento="NF-CUSTOM",
            valor_nominal=Decimal("5000.00"),
            data_vencimento=self.data_base + timedelta(days=3),
        )
        res = motor.avaliar_recebivel(rec, cadastro, estado, snapshot)
        codigos = [m.codigo for m in res.motivos]
        self.assertFalse(res.aprovado)
        self.assertIn("PRAZO_MINIMO", codigos)
        self.assertIn("CONCENTRACAO_MAXIMA_CEDENTE", codigos)

    def test_14_ingestao_csv_formato_pt_br_e_rejeicao_Mais_de_2_casas_decimais(self):
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;"
            "NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;12.345.678/0001-99;CEDENTE SA;11.222.333/0001-81;SACADO LTDA;04.252.011/0001-10;"
            "NF-01;Duplicata;1.234,56;21/11/2026;22/10/2026\n"
            "ANTECIPE FIDC;12.345.678/0001-99;CEDENTE SA;11.222.333/0001-81;SACADO LTDA;04.252.011/0001-10;"
            "NF-02;Duplicata;1000,123;21/11/2026;22/10/2026\n"
        )
        itens = list(iterar_csv_recebiveis(io.StringIO(csv_content), delimitador=";"))
        self.assertEqual(len(itens), 2)

        _, item_ok, err_ok = itens[0]
        self.assertIsNone(err_ok)
        self.assertEqual(item_ok.valor_nominal, Decimal("1234.56"))
        self.assertEqual(item_ok.doc_sacado, "04252011000110")

        _, item_bad, err_bad = itens[1]
        self.assertIsNone(item_bad)
        self.assertIsNotNone(err_bad)
        self.assertFalse(err_bad.aprovado)

    def test_15_gerador_lote_sintetico_homologado_100_linhas(self):
        linhas = list(iterar_linhas_lote_sintetico(100, seed_tag="TEST100"))
        texto = "".join(linhas)
        reader = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
        self.assertEqual(len(reader), 100)
        self.assertIn("VALOR_NOMINAL", reader[0])
        self.assertIn("DATA_VENCIMENTO_ORIGINAL", reader[0])

    def test_16_validacao_cabecalho_csv_bom_duplicado_e_faltante(self):
        # BOM UTF-8 na primeira coluna deve ser normalizado e aceito (retorna (True, [], ""))
        headers_bom = ["\ufeffNOME_FUNDO"] + CABECALHOS_OBRIGATORIOS[1:]
        ok_bom, cols_bom, msg_bom = validar_cabecalho(headers_bom)
        self.assertTrue(ok_bom)
        self.assertEqual(cols_bom, [])
        self.assertEqual(msg_bom, "")

        # Coluna duplicada deve ser recusada
        headers_dup = CABECALHOS_OBRIGATORIOS + ["VALOR_NOMINAL"]
        ok_dup, cols_dup, msg_dup = validar_cabecalho(headers_dup)
        self.assertFalse(ok_dup)
        self.assertIn("VALOR_NOMINAL", cols_dup)
        self.assertIn("duplicadas", msg_dup)

        # Coluna obrigatória faltante deve ser recusada
        headers_missing = [h for h in CABECALHOS_OBRIGATORIOS if h != "DATA_VENCIMENTO_ORIGINAL"]
        ok_mis, cols_mis, msg_mis = validar_cabecalho(headers_missing)
        self.assertFalse(ok_mis)
        self.assertIn("DATA_VENCIMENTO_ORIGINAL", cols_mis)
        self.assertIn("ausentes", msg_mis)

    def test_17_parse_decimal_br_rejeita_nan_inf_notacao_cientifica_e_negativos(self):
        self.assertEqual(parse_decimal_br("1.234.567,89"), Decimal("1234567.89"))
        self.assertEqual(parse_decimal_br("500,00"), Decimal("500.00"))
        self.assertEqual(parse_decimal_br("100"), Decimal("100.00"))
        for invalido in ["NaN", "Infinity", "-Inf", "1e5", "-500,00", "100,999", "", None]:
            self.assertIsNone(parse_decimal_br(invalido))

    def test_18_parse_data_br_formatos_suportados_e_datas_invalidas(self):
        self.assertEqual(parse_data_br("22/10/2026"), date(2026, 10, 22))
        self.assertEqual(parse_data_br("2026-10-22"), date(2026, 10, 22))
        self.assertIsNone(parse_data_br("31/02/2026"))
        self.assertIsNone(parse_data_br("data-invalida"))
        self.assertIsNone(parse_data_br(""))

    def test_19_protecao_capacidade_monetaria_maxima_e_prazo_zero(self):
        params = ParametrosPrecificacao(metodo="DESCONTO_SIMPLES", taxa_mensal=Decimal("0.02"), base_dias=30)
        # Prazo zero (vencimento == data_base): desconto zero e líquido igual ao nominal
        res_zero = calcular_desconto_simples(
            valor_nominal=Decimal("2500.00"),
            data_base=self.data_base,
            data_vencimento=self.data_base,
            params=params,
        )
        self.assertTrue(res_zero.valido)
        self.assertEqual(res_zero.dias, 0)
        self.assertEqual(res_zero.desconto, Decimal("0.00"))
        self.assertEqual(res_zero.valor_liquido, Decimal("2500.00"))

        # Acima do limite máximo monetário Numeric(18,2) -> inválido
        res_overflow = calcular_desconto_simples(
            valor_nominal=LIMITE_MAXIMO_MONETARIO + Decimal("0.01"),
            data_base=self.data_base,
            data_vencimento=self.data_base + timedelta(days=30),
            params=params,
        )
        self.assertFalse(res_overflow.valido)

    def test_20_avaliar_lote_stream_isola_snapshot_historico_original(self):
        motor = MotorAvaliacao(self.config)
        _, snapshot_original = self._novo_estado_e_snapshot(total_carteira=Decimal("500000.00"))
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;"
            "NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE SA;11.222.333/0001-81;SACADO LTDA;04.252.011/0001-10;"
            "NF-STREAM-1;Duplicata;2.000,00;21/11/2026;22/10/2026\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE SA;11.222.333/0001-81;SACADO LTDA;04.252.011/0001-10;"
            "NF-STREAM-1;Duplicata;2.000,00;21/11/2026;22/10/2026\n"
        )
        itens_iter = iterar_csv_recebiveis(io.StringIO(csv_content), delimitador=";")
        resultados = list(
            motor.avaliar_lote_stream(
                itens=itens_iter,
                contexto_cadastral={"04252011000110": "ATIVA"},
                snapshot_historico=snapshot_original,
            )
        )
        self.assertEqual(len(resultados), 2)
        self.assertTrue(resultados[0].aprovado)
        self.assertFalse(resultados[1].aprovado)
        self.assertIn("DUPLICIDADE_LOTE", [m.codigo for m in resultados[1].motivos])
        # O snapshot histórico original não deve ter sido mutado pelo stream
        self.assertEqual(snapshot_original.total_nominal, Decimal("500000.00"))
        self.assertEqual(len(snapshot_original.chaves_duplicidade_existentes), 0)

    def test_21_lote_demonstracao_oficial_samples_demo_csv(self):
        demo_path = PROJECT / "samples" / "demo.csv"
        self.assertTrue(demo_path.exists())
        with demo_path.open("r", encoding="utf-8") as f:
            itens = list(iterar_csv_recebiveis(f, delimitador=";"))
        self.assertEqual(len(itens), 9)


if __name__ == "__main__":
    unittest.main()
