"""
Suíte completa de testes de domínio para o motor Antecipe.
Testa exaustivamente todas as regras, limites, blockers e invariantes de robustez:
1. CSV com delimitador ';'
2. Decimal com vírgula e grupos corretos
3. Datas em formato 'dd/mm/aaaa'
4. Arquivo com cabeçalho inválido / faltante
5. CNPJ com dígitos verificadores inválidos
6. Situação cadastral não verificada (NAO_VERIFICADA)
7. Situação cadastral inativa (INATIVA)
8. Tipo de recebível não permitido
9. Valor abaixo do mínimo (R$ 100,00)
10. Valor exatamente no limite mínimo
11. Nota vencida (vencimento < data-base)
12. Prazo acima do máximo (180 dias)
13. Prazo exatamente no limite máximo (180 dias)
14. Validador inativo no JSON (ex: PRAZO_MINIMO inativo não deve barrar < 30 dias)
15. Alteração de parâmetro entre versões (versão A barra, versão B aprova)
16. Concentração máxima por raiz do CNPJ (8 primeiros dígitos)
17. Concentração acumulada projetada dentro do próprio lote
18. Concentração por raiz com filial diferente compartilhando exposição
19. Duas parcelas legítimas (mesmo número, vencimentos diferentes)
20. Mesma parcela enviada duas vezes no lote (duplicidade intra-lote)
21. Duplicidade de recebível já existente no estoque histórico global
22. Cálculo financeiro de Desconto Simples e fórmula direta com ROUND_HALF_UP
23. Total líquido do lote somando estritamente recebíveis aprovados
24. Rejeição de resultado financeiro inválido (fator de desconto abusivo)
25. Rejeição de Decimal malformado (NaN, Infinity, expoentes, milhar quebrado)
26. Rejeição de Cabeçalho com duplicidade e suporte a UTF-8 BOM
27. Rejeição de Linha Ragged / desbalanceada no CSV
28. Rejeição de campos essenciais vazios (ex: documento, sacado)
29. Data de aquisição inválida não vira None silencioso (gera recusa estruturada)
30. CNPJ com letras embutidas não vira válido apagando texto
31. Rejeição de configuração JSON com tipos inválidos (ex: bool como string, código duplicado/desconhecido)
32. Invariante de prazo zero (zero dias não gera desconto e valida parâmetros)
33. Isolamento profundo de SnapshotCarteira contra mutação externa
34. Rejeição de documento com letras em parse_linha_csv (sem fallback fraudulento)
35. Rejeição de valor que quantiza para R$ 0,00 mesmo com prazo zero (ex: Decimal('0.001'))
36. Proteção contra estouro de capacidade monetária (ex: 40 noves) sem 500
37. Contratos públicos preservados: normalizar_documento e parse_data_br
"""
import copy
import io
import json
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Adiciona o caminho raiz do Codex/antecipe para importação
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from domain.cnpj import normalizar_cnpj, validar_cnpj
from domain.engine import ConfiguracaoMotor, MotorAvaliacao, carregar_configuracao
from domain.ingestion import (
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
from domain.models import (
    EstadoProjetadoLote,
    ReceivelInput,
    SnapshotCarteira,
)
from domain.pricing import ParametrosPrecificacao, calcular_desconto_simples


class TestDomainEngineCompleto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        caminho_json = Path(__file__).resolve().parents[4] / "validadores_antecipe.json"
        with open(caminho_json, "r", encoding="utf-8") as f:
            cls.raw_json = json.load(f)
        cls.data_base_padrao = date(2026, 10, 22)
        cls.config_padrao = carregar_configuracao(cls.raw_json, cls.data_base_padrao)

    def _criar_recebivel(
        self,
        linha: int = 2,
        nu_documento: str = "NF-001",
        doc_cedente: str = "11222333000181",
        doc_sacado: str = "00000000000191",
        tipo: str = "Duplicata",
        valor: str = "1000.00",
        vencimento: date = date(2026, 11, 21),
    ) -> ReceivelInput:
        return ReceivelInput(
            linha=linha,
            nome_fundo="ANTECIPE FIDC",
            doc_fundo="92234400000180",
            nome_cedente="CEDENTE TESTE LTDA",
            doc_cedente=doc_cedente,
            nome_sacado="SACADO TESTE S.A.",
            doc_sacado=doc_sacado,
            nu_documento=nu_documento,
            tipo_recebivel=tipo,
            valor_nominal=Decimal(valor),
            data_vencimento=vencimento,
            data_aquisicao=None
        )

    # 1. CSV com delimitador ';'
    def test_01_csv_delimitador_ponto_e_virgula(self):
        csv_conteudo = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE A;11.222.333/0001-81;SACADO B;00.000.000/0001-91;DOC-100;Duplicata;1500,50;25/11/2026;22/10/2026\n"
        )
        stream = io.StringIO(csv_conteudo)
        itens = list(iterar_csv_recebiveis(stream, delimitador=";"))
        self.assertEqual(len(itens), 1)
        linha, item, erro = itens[0]
        self.assertIsNone(erro)
        self.assertIsNotNone(item)
        self.assertEqual(item.nu_documento, "DOC-100")
        self.assertEqual(item.valor_nominal, Decimal("1500.50"))

    # 2. Decimal com vírgula e grupos corretos
    def test_02_decimal_com_virgula(self):
        self.assertEqual(parse_decimal_br("1.234.567,89"), Decimal("1234567.89"))
        self.assertEqual(parse_decimal_br("500,00"), Decimal("500.00"))
        self.assertEqual(parse_decimal_br("100.50"), Decimal("100.50"))

    # 3. Datas em formato dd/mm/aaaa (preservando contrato público e estrito)
    def test_03_data_formato_br(self):
        d = parse_data_br("22/10/2026")
        self.assertEqual(d, date(2026, 10, 22))
        self.assertIsNone(parse_data_br("32/13/2026"))
        
        ok, d_estrito = parse_data_br_estrito("22/10/2026")
        self.assertTrue(ok)
        self.assertEqual(d_estrito, date(2026, 10, 22))

    # 4. Arquivo com cabeçalho inválido / faltante
    def test_04_cabecalho_invalido(self):
        csv_invalido = "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;VALOR_NOMINAL\n"
        stream = io.StringIO(csv_invalido)
        with self.assertRaises(ValueError) as ctx:
            list(iterar_csv_recebiveis(stream, delimitador=";"))
        self.assertIn("Cabeçalho inválido", str(ctx.exception))

    # 5. CNPJ com dígitos verificadores inválidos
    def test_05_cnpj_sacado_invalido(self):
        self.assertTrue(validar_cnpj("00000000000191"))
        self.assertFalse(validar_cnpj("00000000000192"))
        self.assertFalse(validar_cnpj("11111111111111"))
        
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(doc_sacado="00000000000192")
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={"00000000000192": "ATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "CNPJ_SACADO_VALIDO")

    # 6. Situação cadastral não verificada
    def test_06_situacao_cadastral_nao_verificada(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(doc_sacado="00000000000191")
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "SITUACAO_CADASTRAL_SACADO")
        self.assertEqual(res.status, "RECUSADA")
        self.assertIn("nota foi recusada", res.motivos[0].mensagem)

    # 7. Situação cadastral inativa
    def test_07_situacao_cadastral_inativa(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(doc_sacado="00000000000191")
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={"00000000000191": "INATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "SITUACAO_CADASTRAL_SACADO")
        self.assertIn("INATIVA", res.motivos[0].mensagem)

    # 8. Tipo de recebível não permitido
    def test_08_tipo_recebivel_nao_permitido(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(tipo="Cheque")
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={item.doc_sacado: "ATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "TIPO_RECEBIVEL")

    # 9. Valor abaixo do mínimo
    def test_09_valor_abaixo_do_minimo(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(valor="99.99")
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={item.doc_sacado: "ATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "VALOR_MINIMO")

    # 10. Valor exatamente no limite mínimo
    def test_10_valor_exatamente_minimo(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(valor="100.00")
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={item.doc_sacado: "ATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertTrue(res.aprovado)

    # 11. Nota vencida (vencimento < data-base)
    def test_11_nota_vencida(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(vencimento=date(2026, 10, 21))
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={item.doc_sacado: "ATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "NAO_VENCIDA")

    # 12. Prazo acima do máximo (180 dias)
    def test_12_prazo_acima_do_maximo(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(vencimento=self.data_base_padrao + timedelta(days=181))
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={item.doc_sacado: "ATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "PRAZO_MAXIMO")

    # 13. Prazo exatamente no limite máximo (180 dias)
    def test_13_prazo_exatamente_maximo(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(vencimento=self.data_base_padrao + timedelta(days=180))
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={item.doc_sacado: "ATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertTrue(res.aprovado)

    # 14. Validador inativo no JSON
    def test_14_validador_inativo_ignorado(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(vencimento=self.data_base_padrao + timedelta(days=10))
        res = motor.avaliar_recebivel(
            recebivel=item,
            contexto_cadastral={item.doc_sacado: "ATIVA"},
            estado_lote=EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            snapshot_historico=SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertTrue(res.aprovado)

    # 15. Alteração de parâmetros entre versões
    def test_15_alteracao_parametro_entre_versoes(self):
        json_v2 = copy.deepcopy(self.raw_json)
        for reg in json_v2["validadores"]:
            if reg["codigo"] == "PRAZO_MINIMO":
                reg["ativo"] = True
                reg["parametros"]["prazo_minimo_dias"] = 30

        config_v2 = carregar_configuracao(json_v2, self.data_base_padrao)
        motor_v2 = MotorAvaliacao(config_v2)

        item = self._criar_recebivel(vencimento=self.data_base_padrao + timedelta(days=15))
        motor_v1 = MotorAvaliacao(self.config_padrao)
        res_v1 = motor_v1.avaliar_recebivel(
            item, {item.doc_sacado: "ATIVA"},
            EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertTrue(res_v1.aprovado)

        res_v2 = motor_v2.avaliar_recebivel(
            item, {item.doc_sacado: "ATIVA"},
            EstadoProjetadoLote(Decimal("100000.00"), {}, {}),
            SnapshotCarteira(total_nominal=Decimal("100000.00"))
        )
        self.assertFalse(res_v2.aprovado)
        self.assertEqual(res_v2.motivos[0].codigo, "PRAZO_MINIMO")

    # 16. Concentração por raiz do CNPJ (8 primeiros dígitos)
    def test_16_concentracao_por_raiz_cnpj(self):
        motor = MotorAvaliacao(self.config_padrao)
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("100000.00"),
            exposicoes_sacado_raiz={"00000000": Decimal("9000.00")}
        )
        item = self._criar_recebivel(valor="2000.00", doc_sacado="00000000000191")
        res = motor.avaliar_recebivel(
            item, {item.doc_sacado: "ATIVA"},
            EstadoProjetadoLote(Decimal("100000.00"), {"00000000": Decimal("9000.00")}, {}),
            snapshot
        )
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "CONCENTRACAO_MAXIMA_SACADO")

    # 17. Concentração acumulada projetada dentro do próprio lote
    def test_17_concentracao_acumulada_projetada_lote(self):
        motor = MotorAvaliacao(self.config_padrao)
        snapshot = SnapshotCarteira(total_nominal=Decimal("100000.00"))
        estado_lote = EstadoProjetadoLote(Decimal("100000.00"), {}, {})

        item1 = self._criar_recebivel(linha=2, nu_documento="NF-01", valor="5000.00", doc_sacado="00000000000191")
        res1 = motor.avaliar_recebivel(item1, {item1.doc_sacado: "ATIVA"}, estado_lote, snapshot)
        self.assertTrue(res1.aprovado)

        item2 = self._criar_recebivel(linha=3, nu_documento="NF-02", valor="6000.00", doc_sacado="00000000000191")
        res2 = motor.avaliar_recebivel(item2, {item2.doc_sacado: "ATIVA"}, estado_lote, snapshot)
        self.assertTrue(res2.aprovado)

        item3 = self._criar_recebivel(linha=4, nu_documento="NF-03", valor="2000.00", doc_sacado="00000000000191")
        res3 = motor.avaliar_recebivel(item3, {item3.doc_sacado: "ATIVA"}, estado_lote, snapshot)
        self.assertFalse(res3.aprovado)
        self.assertEqual(res3.motivos[0].codigo, "CONCENTRACAO_MAXIMA_SACADO")

    # 18. Filiais com mesma raiz compartilham exposição
    def test_18_filiais_compartilham_exposicao(self):
        motor = MotorAvaliacao(self.config_padrao)
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("100000.00"),
            exposicoes_sacado_raiz={"00000000": Decimal("9500.00")}
        )
        estado_lote = EstadoProjetadoLote(Decimal("100000.00"), {"00000000": Decimal("9500.00")}, {})
        item_filial = self._criar_recebivel(doc_sacado="00000000000272", valor="1500.00")
        res = motor.avaliar_recebivel(item_filial, {item_filial.doc_sacado: "ATIVA"}, estado_lote, snapshot)
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "CONCENTRACAO_MAXIMA_SACADO")

    # 19. Duas parcelas legítimas com vencimentos diferentes
    def test_19_parcelas_legitimas_vencimentos_diferentes(self):
        motor = MotorAvaliacao(self.config_padrao)
        snapshot = SnapshotCarteira(total_nominal=Decimal("100000.00"))
        estado_lote = EstadoProjetadoLote(Decimal("100000.00"), {}, {})

        item_parc1 = self._criar_recebivel(linha=2, nu_documento="NF-PARCELADA", vencimento=date(2026, 11, 22))
        item_parc2 = self._criar_recebivel(linha=3, nu_documento="NF-PARCELADA", vencimento=date(2026, 12, 22))

        res1 = motor.avaliar_recebivel(item_parc1, {item_parc1.doc_sacado: "ATIVA"}, estado_lote, snapshot)
        res2 = motor.avaliar_recebivel(item_parc2, {item_parc2.doc_sacado: "ATIVA"}, estado_lote, snapshot)

        self.assertTrue(res1.aprovado)
        self.assertTrue(res2.aprovado)

    # 20. Mesma parcela enviada duas vezes no lote (duplicidade intra-lote)
    def test_20_duplicidade_intra_lote(self):
        motor = MotorAvaliacao(self.config_padrao)
        snapshot = SnapshotCarteira(total_nominal=Decimal("100000.00"))
        estado_lote = EstadoProjetadoLote(Decimal("100000.00"), {}, {})

        item1 = self._criar_recebivel(linha=2, nu_documento="NF-REPETIDA", vencimento=date(2026, 11, 22))
        item2 = self._criar_recebivel(linha=3, nu_documento="NF-REPETIDA", vencimento=date(2026, 11, 22))

        res1 = motor.avaliar_recebivel(item1, {item1.doc_sacado: "ATIVA"}, estado_lote, snapshot)
        res2 = motor.avaliar_recebivel(item2, {item2.doc_sacado: "ATIVA"}, estado_lote, snapshot)

        self.assertTrue(res1.aprovado)
        self.assertFalse(res2.aprovado)
        self.assertEqual(res2.motivos[0].codigo, "DUPLICIDADE_LOTE")

    # 21. Duplicidade no estoque histórico global
    def test_21_duplicidade_historica_estoque_global(self):
        motor = MotorAvaliacao(self.config_padrao)
        item = self._criar_recebivel(nu_documento="NF-HISTORICA", vencimento=date(2026, 11, 22))
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("100000.00"),
            chaves_duplicidade_existentes={item.chave_duplicidade}
        )
        estado_lote = EstadoProjetadoLote(Decimal("100000.00"), {}, {})

        res = motor.avaliar_recebivel(item, {item.doc_sacado: "ATIVA"}, estado_lote, snapshot)
        self.assertFalse(res.aprovado)
        self.assertEqual(res.motivos[0].codigo, "DUPLICIDADE_HISTORICA")
        self.assertIn("estoque global", res.motivos[0].mensagem)

    # 22. Cálculo financeiro de Desconto Simples
    def test_22_calculo_financeiro_direto(self):
        params = ParametrosPrecificacao(metodo="DESCONTO_SIMPLES", taxa_mensal=Decimal("0.02"), base_dias=30)
        res = calcular_desconto_simples(
            valor_nominal=Decimal("5000.00"),
            data_base=date(2026, 10, 22),
            data_vencimento=date(2026, 10, 22) + timedelta(days=90),
            params=params
        )
        self.assertTrue(res.valido)
        self.assertEqual(res.valor_liquido, Decimal("4700.00"))
        self.assertEqual(res.desconto, Decimal("300.00"))

        res_dizima = calcular_desconto_simples(
            valor_nominal=Decimal("1000.00"),
            data_base=date(2026, 10, 22),
            data_vencimento=date(2026, 10, 22) + timedelta(days=31),
            params=params
        )
        self.assertEqual(res_dizima.valor_liquido, Decimal("979.33"))
        self.assertEqual(res_dizima.desconto, Decimal("20.67"))

    # 23. Soma do total líquido somando estritamente recebíveis aprovados
    def test_23_soma_total_liquido_apenas_aprovados(self):
        motor = MotorAvaliacao(self.config_padrao)
        snapshot = SnapshotCarteira(total_nominal=Decimal("100000.00"))

        item1 = self._criar_recebivel(linha=2, nu_documento="NF-01", valor="1000.00")
        item2 = self._criar_recebivel(linha=3, nu_documento="NF-02", valor="1000.00")
        item3 = self._criar_recebivel(linha=4, nu_documento="NF-03", valor="5000.00", vencimento=date(2026, 10, 20))

        lote_stream = [
            (2, item1, None),
            (3, item2, None),
            (4, item3, None),
        ]

        resultados = list(motor.avaliar_lote_stream(
            iter(lote_stream),
            contexto_cadastral={"00000000000191": "ATIVA"},
            snapshot_historico=snapshot
        ))

        self.assertEqual(len(resultados), 3)
        self.assertTrue(resultados[0].aprovado)
        self.assertTrue(resultados[1].aprovado)
        self.assertFalse(resultados[2].aprovado)

        total_liquido = sum((r.valor_liquido for r in resultados if r.aprovado and r.valor_liquido), Decimal("0.00"))
        self.assertEqual(total_liquido, Decimal("1960.00"))

    # 24. Rejeição de resultado financeiro inválido
    def test_24_resultado_financeiro_invalido(self):
        params_extremos = ParametrosPrecificacao(metodo="DESCONTO_SIMPLES", taxa_mensal=Decimal("0.50"), base_dias=30)
        res = calcular_desconto_simples(
            valor_nominal=Decimal("100.00"),
            data_base=date(2026, 10, 22),
            data_vencimento=date(2026, 10, 22) + timedelta(days=90),
            params=params_extremos
        )
        self.assertFalse(res.valido)
        self.assertIn("líquido zero ou negativo", res.motivo_invalidez)

    # 25. Rejeição de Decimal malformado (NaN, Inf, expoentes, milhar quebrado)
    def test_25_rejeicao_decimal_malformado(self):
        self.assertIsNone(parse_decimal_br("NaN"))
        self.assertIsNone(parse_decimal_br("Infinity"))
        self.assertIsNone(parse_decimal_br("-Infinity"))
        self.assertIsNone(parse_decimal_br("1e5"))
        self.assertIsNone(parse_decimal_br("1.2.34,56"))
        self.assertIsNone(parse_decimal_br("100,50,20"))
        self.assertIsNone(parse_decimal_br("-50,00"))

    # 26. Cabeçalho com duplicidade e suporte a UTF-8 BOM
    def test_26_cabecalho_duplicado_e_bom(self):
        headers_bom = ["\ufeffNOME_FUNDO"] + CABECALHOS_OBRIGATORIOS[1:]
        ok, _, _ = validar_cabecalho(headers_bom)
        self.assertTrue(ok)

        headers_dup = CABECALHOS_OBRIGATORIOS + ["NOME_FUNDO"]
        ok_dup, _, msg_dup = validar_cabecalho(headers_dup)
        self.assertFalse(ok_dup)
        self.assertTrue("Cabeçalho duplicado" in msg_dup or "duplicadas detectadas" in msg_dup)

    # 27. Rejeição de linha ragged / desbalanceada no CSV
    def test_27_linha_ragged_desbalanceada(self):
        csv_ragged = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "FUNDO;123;CED;456;SAC;789;DOC1;Duplicata;1000,00;25/11/2026\n"
        )
        stream = io.StringIO(csv_ragged)
        itens = list(iterar_csv_recebiveis(stream, delimitador=";"))
        self.assertEqual(len(itens), 1)
        _, item, erro = itens[0]
        self.assertIsNone(item)
        self.assertIsNotNone(erro)
        self.assertEqual(erro.motivos[0].codigo, "LINHA_MALFORMADA_COLUNAS")

    # 28. Rejeição de campos essenciais vazios
    def test_28_campos_essenciais_vazios(self):
        row = {
            "NOME_FUNDO": "FUNDO",
            "DOC_FUNDO": "123",
            "NOME_CEDENTE": "",
            "DOC_CEDENTE": "11222333000181",
            "NOME_SACADO": "SACADO",
            "DOC_SACADO": "00000000000191",
            "NU_DOCUMENTO": "",
            "TIPO_RECEBIVEL": "Duplicata",
            "VALOR_NOMINAL": "1000,00",
            "DATA_VENCIMENTO_ORIGINAL": "25/11/2026",
            "DATA_AQUISICAO": "22/10/2026",
        }
        item, erro = parse_linha_csv(2, row)
        self.assertIsNone(item)
        self.assertIsNotNone(erro)
        self.assertEqual(erro.motivos[0].codigo, "CAMPOS_OBRIGATORIOS_VAZIOS")

    # 29. Data de aquisição inválida não vira None silencioso
    def test_29_data_aquisicao_invalida(self):
        row = {
            "NOME_FUNDO": "FUNDO",
            "DOC_FUNDO": "123",
            "NOME_CEDENTE": "CEDENTE",
            "DOC_CEDENTE": "11222333000181",
            "NOME_SACADO": "SACADO",
            "DOC_SACADO": "00000000000191",
            "NU_DOCUMENTO": "DOC-1",
            "TIPO_RECEBIVEL": "Duplicata",
            "VALOR_NOMINAL": "1000,00",
            "DATA_VENCIMENTO_ORIGINAL": "25/11/2026",
            "DATA_AQUISICAO": "data_corrompida",
        }
        item, erro = parse_linha_csv(2, row)
        self.assertIsNone(item)
        self.assertIsNotNone(erro)
        self.assertEqual(erro.motivos[0].codigo, "FORMATO_INVALIDO_DATA_AQUISICAO")

    # 30. CNPJ com letras não é aceito apagando texto
    def test_30_cnpj_com_letras_rejeitado(self):
        ok, norm = normalizar_cnpj("00.000.000/0001-9A")
        self.assertFalse(ok)
        self.assertFalse(validar_cnpj("00.000.000/0001-9A"))

    # 31. Rejeição de configuração JSON com tipos inválidos
    def test_31_validacao_estrita_configuracao_json(self):
        cfg_bool_str = copy.deepcopy(self.raw_json)
        cfg_bool_str["validadores"][0]["ativo"] = "false"
        with self.assertRaises(ValueError) as ctx1:
            carregar_configuracao(cfg_bool_str)
        self.assertIn("booleano estrito", str(ctx1.exception))

        cfg_desconhecido = copy.deepcopy(self.raw_json)
        cfg_desconhecido["validadores"].append({
            "codigo": "REGRA_INEXISTENTE",
            "ativo": True,
            "parametros": {}
        })
        with self.assertRaises(ValueError) as ctx2:
            carregar_configuracao(cfg_desconhecido)
        self.assertIn("Código de validador desconhecido", str(ctx2.exception))

        cfg_duplicado = copy.deepcopy(self.raw_json)
        cfg_duplicado["validadores"].append(cfg_duplicado["validadores"][0])
        with self.assertRaises(ValueError) as ctx3:
            carregar_configuracao(cfg_duplicado)
        self.assertIn("Código de validador duplicado", str(ctx3.exception))

        cfg_metodo_inv = copy.deepcopy(self.raw_json)
        cfg_metodo_inv["precificacao"]["metodo"] = "JUROS_COMPOSTOS"
        with self.assertRaises(ValueError) as ctx4:
            carregar_configuracao(cfg_metodo_inv)
        self.assertIn("Método de precificação inválido", str(ctx4.exception))

    # 32. Invariante de prazo zero
    def test_32_invariante_prazo_zero(self):
        params = ParametrosPrecificacao(metodo="DESCONTO_SIMPLES", taxa_mensal=Decimal("0.02"), base_dias=30)
        res = calcular_desconto_simples(
            valor_nominal=Decimal("1500.00"),
            data_base=date(2026, 10, 22),
            data_vencimento=date(2026, 10, 22),
            params=params
        )
        self.assertTrue(res.valido)
        self.assertEqual(res.dias, 0)
        self.assertEqual(res.desconto, Decimal("0.00"))
        self.assertEqual(res.valor_liquido, Decimal("1500.00"))

    # 33. Isolamento profundo de SnapshotCarteira
    def test_33_isolamento_snapshot_carteira(self):
        snapshot = SnapshotCarteira(
            total_nominal=Decimal("100000.00"),
            exposicoes_sacado_raiz={"00000000": Decimal("5000.00")},
            chaves_duplicidade_existentes={"DOC1"}
        )
        copia = snapshot.criar_copia_isolada()
        copia.exposicoes_sacado_raiz["00000000"] = Decimal("99999.00")
        copia.chaves_duplicidade_existentes.add("DOC2")

        self.assertEqual(snapshot.exposicoes_sacado_raiz["00000000"], Decimal("5000.00"))
        self.assertNotIn("DOC2", snapshot.chaves_duplicidade_existentes)

    # 34. Blocker A: Rejeição de documento com letras em parse_linha_csv (sem fallback fraudulento)
    def test_34_rejeicao_documento_com_letras_nao_mascara_fraude(self):
        # Linha com DOC_SACADO contendo letras embutidas que formariam CNPJ se as letras fossem apagadas
        row = {
            "NOME_FUNDO": "ANTECIPE FIDC",
            "DOC_FUNDO": "92234400000180",
            "NOME_CEDENTE": "CEDENTE",
            "DOC_CEDENTE": "11222333000181",
            "NOME_SACADO": "SACADO",
            "DOC_SACADO": "abc04252011000110",  # Letras embutidas
            "NU_DOCUMENTO": "DOC-ABC",
            "TIPO_RECEBIVEL": "Duplicata",
            "VALOR_NOMINAL": "1000,00",
            "DATA_VENCIMENTO_ORIGINAL": "25/11/2026",
            "DATA_AQUISICAO": "22/10/2026",
        }
        item, erro = parse_linha_csv(2, row)
        # Deve rejeitar imediatamente no parsing sem produzir ReceivelInput limpo fraudulento
        self.assertIsNone(item)
        self.assertIsNotNone(erro)
        self.assertEqual(erro.motivos[0].codigo, "FORMATO_INVALIDO_DOCUMENTO_SACADO")

    # 35. Blocker B: Rejeição de valor que arredonda para R$ 0,00 mesmo com prazo zero
    def test_35_rejeicao_liquido_zerado_prazo_zero(self):
        params = ParametrosPrecificacao(metodo="DESCONTO_SIMPLES", taxa_mensal=Decimal("0.02"), base_dias=30)
        # Decimal('0.001') quantizado para centavos resulta em 0.00 -> deve ser rejeitado
        res = calcular_desconto_simples(
            valor_nominal=Decimal("0.001"),
            data_base=date(2026, 10, 22),
            data_vencimento=date(2026, 10, 22),
            params=params
        )
        self.assertFalse(res.valido)
        self.assertIn("R$ 0,00", res.motivo_invalidez)

    # 36. Blocker C: Proteção contra estouro de capacidade monetária (ex: 40 noves)
    def test_36_protecao_estouro_capacidade_monetaria(self):
        params = ParametrosPrecificacao(metodo="DESCONTO_SIMPLES", taxa_mensal=Decimal("0.02"), base_dias=30)
        nominal_gigante = Decimal("9" * 40)
        # Não pode lançar InvalidOperation nem crashar sem controle
        res = calcular_desconto_simples(
            valor_nominal=nominal_gigante,
            data_base=date(2026, 10, 22),
            data_vencimento=date(2026, 10, 22) + timedelta(days=1),
            params=params
        )
        self.assertFalse(res.valido)
        self.assertIn("capacidade monetária", res.motivo_invalidez)

        # No parsing CSV, valor com mais de 16 inteiros deve retornar None (FORMATO_INVALIDO_VALOR)
        self.assertIsNone(parse_decimal_br("9" * 40))

    # 37. Preservação dos contratos públicos legados
    def test_37_contratos_publicos_preservados(self):
        # normalizar_documento remove apenas pontuação
        self.assertEqual(normalizar_documento("11.222.333/0001-81"), "11222333000181")
        # parse_data_br retorna Optional[date]
        self.assertEqual(parse_data_br("25/11/2026"), date(2026, 11, 25))
        self.assertIsNone(parse_data_br("invalido"))
        self.assertEqual(parse_data_br("25/11/2026"), date(2026, 11, 25))
        self.assertIsNone(parse_data_br("invalido"))

    # 38. Blocker de Precisão e Representação Exata de Centavos (Sol Audit)
    def test_38_precisao_exata_centavos_sem_arredondamento_silencioso(self):
        # 1. Frações não nulas além de 2 casas devem ser rejeitadas estritamente
        self.assertIsNone(parse_decimal_br("100.005"))
        self.assertIsNone(parse_decimal_br("100,005"))
        self.assertIsNone(parse_decimal_br("50.001"))
        self.assertIsNone(parse_decimal_br("50,0001"))

        # 2. Valores exatos com zeros redundantes devem normalizar para centavos exatos
        dec_zeros = parse_decimal_br("100.000")
        self.assertIsNotNone(dec_zeros)
        self.assertEqual(dec_zeros, Decimal("100.00"))

        dec_virgula = parse_decimal_br("100,00")
        self.assertIsNotNone(dec_virgula)
        self.assertEqual(dec_virgula, Decimal("100.00"))

        dec_ponto = parse_decimal_br("100.00")
        self.assertIsNotNone(dec_ponto)
        self.assertEqual(dec_ponto, Decimal("100.00"))

        # 3. No fluxo de parse_linha_csv, '100.005' deve produzir recusa com FORMATO_INVALIDO_VALOR
        row_fracao = {
            "NOME_FUNDO": "ANTECIPE FIDC",
            "DOC_FUNDO": "92234400000180",
            "NOME_CEDENTE": "CEDENTE",
            "DOC_CEDENTE": "11222333000181",
            "NOME_SACADO": "SACADO",
            "DOC_SACADO": "00000000000191",
            "NU_DOCUMENTO": "DOC-CENTS",
            "TIPO_RECEBIVEL": "Duplicata",
            "VALOR_NOMINAL": "100.005",
            "DATA_VENCIMENTO_ORIGINAL": "25/11/2026",
            "DATA_AQUISICAO": "22/10/2026",
        }
        item_fracao, erro_fracao = parse_linha_csv(2, row_fracao)
        self.assertIsNone(item_fracao)
        self.assertIsNotNone(erro_fracao)
        self.assertEqual(erro_fracao.motivos[0].codigo, "FORMATO_INVALIDO_VALOR")

        # 4. Invariante de pricing: líquido NUNCA pode exceder valor nominal para taxa >= 0
        params = ParametrosPrecificacao(metodo="DESCONTO_SIMPLES", taxa_mensal=Decimal("0.02"), base_dias=30)
        res_dia0 = calcular_desconto_simples(
            valor_nominal=Decimal("100.00"),
            data_base=date(2026, 10, 22),
            data_vencimento=date(2026, 10, 22),
            params=params
        )
        self.assertTrue(res_dia0.valido)
        self.assertLessEqual(res_dia0.valor_liquido, Decimal("100.00"))
        self.assertEqual(res_dia0.valor_liquido, Decimal("100.00"))
        self.assertEqual(res_dia0.desconto, Decimal("0.00"))

if __name__ == "__main__":
    unittest.main()
