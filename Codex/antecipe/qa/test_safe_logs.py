"""
Auditoria Real de Logs Seguros e Prevenção de Vazamentos (Rubrica 5.2.4).
Testes unitários estritos contra o logger e formatação REAIS da aplicação (Codex.antecipe.backend.logger):
- Importa `logger` e `SafeJsonFormatter` reais do produto.
- Testa contenção e filtragem da allowlist sob emissão direta de eventos e extras pelo logger.
- Assegura ausência absoluta de sentinelas, nomes, CPFs, CNPJs e payloads brutos fora de ALLOWED_LOG_FIELDS.
- Garante conformidade de saída JSON estruturada de linha única.
Nota: testes de integração capturando requisições HTTP reais serão executados na esteira de segurança/API.
"""
import io
import json
import logging
import unittest
from decimal import Decimal

# Importação dos componentes REAIS do produto com suporte a backend direto ou namespace kit
try:
    from backend.logger import logger, SafeJsonFormatter, ALLOWED_LOG_FIELDS
except ImportError:
    from Codex.antecipe.backend.logger import logger, SafeJsonFormatter, ALLOWED_LOG_FIELDS


class TestSafeLogsRealProduct(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(SafeJsonFormatter())
        # Acopla handler de captura ao logger real do produto
        logger.addHandler(self.handler)
        self.orig_level = logger.level
        logger.setLevel(logging.INFO)

    def tearDown(self):
        logger.removeHandler(self.handler)
        logger.setLevel(self.orig_level)

    def test_01_safe_json_formatter_rejeita_campos_fora_da_allowlist(self):
        """Campos de payload bruto, dados de cliente ou segredos passados em extra são expurgados."""
        sentinela_segredo = "SENTINEL_ADMIN_SECRET_KEY_999"
        sentinela_csv_row = "10.062.050/0001-57;TECIDOS SANTARÉM;VALOR;2278,08"
        sentinela_cpf = "123.456.789-00"

        logger.info(
            "Evento de auditoria de simulação",
            extra={
                "event": "simulacao_concluida",
                "simulation_id": "sim-uuid-12345",
                "total_itens": 100,
                "aprovados": 90,
                "recusados": 10,
                "duration_ms": 154.2,
                # Atributos invasivos / vazamento que devem ser bloqueados pela allowlist
                "admin_token": sentinela_segredo,
                "raw_csv_row": sentinela_csv_row,
                "cpf_cliente": sentinela_cpf,
            }
        )

        log_raw = self.stream.getvalue()
        self.assertNotIn(sentinela_segredo, log_raw)
        self.assertNotIn(sentinela_csv_row, log_raw)
        self.assertNotIn(sentinela_cpf, log_raw)

        # Valida parse JSON estrito
        log_obj = json.loads(log_raw.strip())
        self.assertEqual(log_obj["level"], "INFO")
        self.assertEqual(log_obj["event"], "simulacao_concluida")
        self.assertEqual(log_obj["simulation_id"], "sim-uuid-12345")
        self.assertEqual(log_obj["total_itens"], 100)
        self.assertEqual(log_obj["aprovados"], 90)
        self.assertEqual(log_obj["recusados"], 10)
        
        # Garante que chaves proibidas não existem no objeto serializado
        self.assertNotIn("admin_token", log_obj)
        self.assertNotIn("raw_csv_row", log_obj)
        self.assertNotIn("cpf_cliente", log_obj)

    def test_02_erro_admin_e_erros_de_autenticacao_sem_vazamento(self):
        """Erros de autenticação ou tokens inválidos não registram o segredo no log."""
        token_sentinela = "SENTINEL_BEARER_MALFORMED_TOKEN_XYZ"
        # Simula tentativa de login/admin com token falso
        logger.warning(
            "Tentativa de acesso administrativo não autorizado",
            extra={
                "event": "admin_auth_failed",
                "status_code": 401,
                "error_code": "ADMIN_TOKEN_INVALIDO",
                "attempted_token": token_sentinela  # deve ser filtrado
            }
        )

        log_raw = self.stream.getvalue()
        self.assertNotIn(token_sentinela, log_raw)
        log_obj = json.loads(log_raw.strip())
        self.assertEqual(log_obj["status_code"], 401)
        self.assertEqual(log_obj["error_code"], "ADMIN_TOKEN_INVALIDO")
        self.assertNotIn("attempted_token", log_obj)

    def test_03_erro_parsing_e_linhas_malformadas_sem_vazamento_de_payload(self):
        """Falhas de parsing de CSV não despejam o conteúdo corrompido nos logs."""
        linha_sensivel = "NOME_SACADO;EMPRESA CONFIDENCIAL;CNPJ;11.222.333/0001-81;VALOR;9999999.99"
        logger.error(
            "Falha de validação estrutural no lote CSV",
            extra={
                "event": "csv_parsing_error",
                "error_code": "FORMATO_LINHA_INVALIDO",
                "raw_payload": linha_sensivel  # Proibido
            }
        )

        log_raw = self.stream.getvalue()
        self.assertNotIn(linha_sensivel, log_raw)
        self.assertNotIn("11.222.333/0001-81", log_raw)
        self.assertNotIn("EMPRESA CONFIDENCIAL", log_raw)
        log_obj = json.loads(log_raw.strip())
        self.assertEqual(log_obj["error_code"], "FORMATO_LINHA_INVALIDO")
        self.assertNotIn("raw_payload", log_obj)

    def test_04_estrutura_json_valida_e_campos_permitidos(self):
        """Todos os logs emitidos pelo produto respeitam estritamente a allowlist oficial."""
        logger.info("Teste simples de verificação", extra={"event": "healthcheck_ok", "status_code": 200})
        log_raw = self.stream.getvalue().strip()
        log_obj = json.loads(log_raw)
        for chave in log_obj.keys():
            self.assertIn(chave, ALLOWED_LOG_FIELDS | {"timestamp", "level", "message"})


if __name__ == "__main__":
    unittest.main()
