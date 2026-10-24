import json
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from prompt_ledger import Ledger, scrub
from generate_fixture import generate
from benchmark import count_csv
from check_logs import inspect


class KitTests(unittest.TestCase):
    def test_scrub_credential_and_data(self):
        value = "senha=exemplo123\nBearer ABCDEFGHIJKLMNOP\nana@example.com\nid,email,name,token\n1,a,b,c"
        cleaned = scrub(value)
        self.assertNotIn("exemplo123", cleaned)
        self.assertNotIn("ABCDEFGHIJKLMNOP", cleaned)
        self.assertNotIn("ana@example.com", cleaned)
        self.assertIn("[LINHA_TABULAR_OMITIDA]", cleaned)

    def test_prompt_and_stop_and_close(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = Ledger(root)
            ident = ledger.prompt("codex", "s1", "Conserte a função do parser", "t1")
            ledger.stop("s1", "Sugeri duas modificações", "t1")
            entries, orphans, pending = ledger.audit()
            self.assertEqual(len(entries), 1)
            self.assertEqual(orphans, [])
            self.assertEqual(pending, [ident])
            ledger.close(ident, "Nenhuma alteração aplicada; hipótese descartada", "Nenhum", "Revisado diff vazio")
            self.assertEqual(ledger.audit()[2], [])
            text = (root / "docs" / "REGISTRO_PROMPTS.md").read_text(encoding="utf-8")
            self.assertIn("Nenhuma alteração aplicada", text)
            self.assertIn("Conserte a função", text)

    def test_orphan_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory))
            ledger.stop("sessao-antiga", "Retorno perdido")
            self.assertEqual(ledger.audit()[1][0]["id"], "O0001")
            ident = ledger.prompt("manual", "sessao-antiga", "Prompt recuperado")
            ledger.close(ident, "Resposta recuperada e analisada", "Não se aplica", "Verificado manualmente")
            ledger.resolve_orphan("O0001", f"Reconciliado com {ident}")
            self.assertEqual(ledger.audit()[1], [])

    def test_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = generate(Path(directory) / "fixture.csv", 101)
            self.assertEqual(count_csv(path), 101)
            with self.assertRaises(FileExistsError):
                generate(path, 10)

    def test_hook_json(self):
        root = Path(__file__).resolve().parents[1]
        for relative in (".codex/hooks.json", ".claude/settings.json"):
            data = json.loads((root / relative).read_text(encoding="utf-8"))
            self.assertIn("UserPromptSubmit", data["hooks"])
            self.assertIn("Stop", data["hooks"])

    def test_native_agents_parse(self):
        root = Path(__file__).resolve().parents[1]
        files = list((root / ".codex" / "agents").glob("*.toml"))
        self.assertEqual(len(files), 9)
        for path in files:
            content = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(content["name"])
            self.assertTrue(content["description"])
            self.assertTrue(content["developer_instructions"])

    def test_sensitive_log_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.jsonl"
            path.write_text('{"timestamp":"2026-10-23T15:00:00Z","level":"INFO","event":"done","rows_read":5}\n', encoding="utf-8")
            checked, errors = inspect([path], ["FAKE_ONLY_00000001"])
            self.assertEqual(checked, 1)
            self.assertEqual(errors, [])
            path.write_text('{"timestamp":"t","level":"INFO","event":"row","csv_row":"FAKE_ONLY_00000001"}\n', encoding="utf-8")
            _, errors = inspect([path], ["FAKE_ONLY_00000001"])
            self.assertTrue(any("vazou" in problem for problem in errors))

    def test_benchmark_smoke(self):
        root = Path(__file__).resolve().parents[1]
        call = [
            sys.executable, str(root / "scripts" / "benchmark.py"), "--rows", "10",
            "--runs", "1", "--expect-one-output-row-per-input",
            "--command", f"{sys.executable} tests/mock_copy.py --input {{input}} --output {{output}}",
        ]
        proc = subprocess.run(call, cwd=root, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Correção semântica: NÃO verificada", proc.stdout)


if __name__ == "__main__":
    unittest.main()
