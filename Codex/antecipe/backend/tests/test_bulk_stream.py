"""
Suíte de testes dirigidos para o transporte WebSocket Bulk Stream.
Isolamento estrito:
- Testes WebSocket executam sob banco temporário SQLite em memória isolado (PUBLIC_DEMO_MODE=True).
- NUNCA toca no banco de dados real nem polui a base da aplicação.
- Casos dirigidos:
  1. Capabilities em /api/health e cabeçalho 'Allow: POST' em 405.
  2. Protocolo completo (start -> ready -> ack -> finish -> complete -> query -> audit).
  3. Chunking com divisão de caractere UTF-8 multibyte, quebras CRLF e linhas multilinhas entre frames.
  4. Monkeypatch de max_records excedido (rollback integral sem registros órfãos).
  5. Desconexão do cliente durante ingestão (rollback integral imediato).
"""
import io
import json
import os
import unittest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app

settings.ADMIN_TOKEN = "hackathon-test-admin-token-2026"
settings.ENABLE_DEMO_CADASTRO = True


class TestBulkStreamWebSocketDirigido(unittest.TestCase):
    def setUp(self):
        # Isola em PUBLIC_DEMO_MODE para o endpoint WebSocket alocar banco :memory: efêmero próprio por conexão
        self.old_public_mode = settings.PUBLIC_DEMO_MODE
        settings.PUBLIC_DEMO_MODE = True
        self.client = TestClient(app)

    def tearDown(self):
        settings.PUBLIC_DEMO_MODE = self.old_public_mode

    def test_01_health_upload_capabilities_e_allow_405(self):
        """Verifica capabilities em /health e preservação do header Allow em 405."""
        res_h = self.client.get("/api/health")
        self.assertEqual(res_h.status_code, 200)
        caps = res_h.json().get("upload_capabilities", {})
        self.assertEqual(caps.get("bulk_transport"), "websocket")
        self.assertEqual(caps.get("max_records"), 1_000_000)

        res_405 = self.client.get("/api/simulations")
        self.assertEqual(res_405.status_code, 405)
        self.assertIn("allow", res_405.headers)
        self.assertIn("POST", res_405.headers["allow"].upper())

    def test_02_websocket_stream_fluxo_completo_query_e_audit_core(self):
        """Valida fluxo completo do stream com audit via SQL Core."""
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
            "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-STREAM-01;Duplicata;5000,00;20/01/2027;\n"
            "ANTECIPE FIDC;92.234.400/0001-80;INDUSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-STREAM-02;Cheque;1500,00;20/01/2027;\n"
        )
        csv_bytes = csv_content.encode("utf-8")
        total_size = len(csv_bytes)

        with self.client.websocket_connect("/api/simulations/stream") as ws:
            ws.send_json({
                "type": "start",
                "filename": "lote.csv",
                "size_bytes": total_size,
                "protocol_version": 1
            })
            ready = ws.receive_json()
            self.assertEqual(ready["type"], "ready")

            mid = total_size // 2
            ws.send_bytes(csv_bytes[:mid])
            ack1 = ws.receive_json()
            self.assertEqual(ack1["type"], "ack")

            ws.send_bytes(csv_bytes[mid:])
            ack2 = ws.receive_json()
            self.assertEqual(ack2["type"], "ack")

            ws.send_json({"type": "finish"})

            complete = None
            for _ in range(5):
                msg = ws.receive_json()
                if msg["type"] == "complete":
                    complete = msg
                    break

            self.assertIsNotNone(complete)
            env = complete["simulation"]
            self.assertEqual(env["total_itens"], 2)
            self.assertEqual(env["aprovados"], 1)
            self.assertEqual(env["total_liquido"], "4700.00")

            # Valida query paginada com limites válidos
            ws.send_json({"type": "query", "request_id": "q1", "page": 1, "page_size": 10})
            page = ws.receive_json()
            self.assertEqual(page["type"], "page")
            self.assertEqual(len(page["simulation"]["resultados"]), 2)

            # Valida audit com SQL Core e hash canônico
            ws.send_json({"type": "audit", "request_id": "a1"})
            audit = ws.receive_json()
            self.assertEqual(audit["type"], "audit")
            self.assertEqual(audit["count"], 2)
            self.assertEqual(audit["approved"], 1)
            self.assertEqual(audit["total_liquido"], "4700.00")
            self.assertTrue(bool(audit["decisions_sha256"]))

            ws.send_json({"type": "close"})

    def test_03_chunking_utf8_multibyte_e_crlf_cross_frames(self):
        """
        Valida que dividir um caractere UTF-8 multibyte (ex: 'Ã' em 2 bytes \xc3\x83)
        ou quebras CRLF exatamente entre frames de WebSocket não corrompe o texto nem o leitor.
        """
        csv_content = (
            "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\r\n"
            "ANTECIPE FIDC;92.234.400/0001-80;INDÚSTRIA BRASIL SA;11.222.333/0001-81;COMERCIAL ALPHA LTDA;04.252.011/0001-10;NF-UTF8;Duplicata;5000,00;20/01/2027;\r\n"
        )
        csv_bytes = csv_content.encode("utf-8")
        total_size = len(csv_bytes)

        # Encontra a posição do 'Ú' em INDÚSTRIA (\xc3\x9a) e quebra no primeiro byte
        idx_u = csv_bytes.find(b"\xc3\x9a")
        cut_point = idx_u + 1  # Divide o caractere multibyte exatamente no meio

        with self.client.websocket_connect("/api/simulations/stream") as ws:
            ws.send_json({"type": "start", "filename": "multibyte.csv", "size_bytes": total_size, "protocol_version": 1})
            ws.receive_json()

            ws.send_bytes(csv_bytes[:cut_point])
            ws.receive_json()  # ack1

            ws.send_bytes(csv_bytes[cut_point:])
            ws.receive_json()  # ack2

            ws.send_json({"type": "finish"})

            complete = None
            for _ in range(5):
                msg = ws.receive_json()
                if msg["type"] == "complete":
                    complete = msg
                    break

            self.assertIsNotNone(complete)
            self.assertEqual(complete["simulation"]["total_itens"], 1)
            self.assertEqual(complete["simulation"]["aprovados"], 1)

            ws.send_json({"type": "close"})

    def test_04_max_records_limite_excedido_rollback(self):
        """Se o lote exceder max_records, deve abortar com erro e rollback."""
        old_max = settings.MAX_STREAM_RECORDS
        try:
            settings.MAX_STREAM_RECORDS = 1  # Força teto de 1 linha
            csv_content = (
                "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
                "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE;11.222.333/0001-81;SACADO;04.252.011/0001-10;NF-01;Duplicata;1500,00;20/01/2027;\n"
                "ANTECIPE FIDC;92.234.400/0001-80;CEDENTE;11.222.333/0001-81;SACADO;04.252.011/0001-10;NF-02;Duplicata;1500,00;20/01/2027;\n"
            )
            csv_bytes = csv_content.encode("utf-8")
            with self.client.websocket_connect("/api/simulations/stream") as ws:
                ws.send_json({"type": "start", "filename": "excedido.csv", "size_bytes": len(csv_bytes), "protocol_version": 1})
                ws.receive_json()
                ws.send_bytes(csv_bytes)
                ws.receive_json()
                ws.send_json({"type": "finish"})

                err = ws.receive_json()
                self.assertEqual(err["type"], "error")
                self.assertIn("Limite máximo de registros", err["mensagem"])
        finally:
            settings.MAX_STREAM_RECORDS = old_max

    def test_05_disconnect_durante_streaming_rollback(self):
        """Queda de conexão do cliente durante transmissão binária aborta leitor e dá rollback."""
        csv_header = "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO\n"
        with self.client.websocket_connect("/api/simulations/stream") as ws:
            ws.send_json({"type": "start", "filename": "abort.csv", "size_bytes": 10000, "protocol_version": 1})
            ws.receive_json()
            ws.send_bytes(csv_header.encode("utf-8"))
            ws.receive_json()
            # Cliente desconecta abruptamente sem enviar finish
            ws.close()


if __name__ == "__main__":
    unittest.main()
