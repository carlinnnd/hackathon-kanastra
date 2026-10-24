"""
Teste de isolamento para o wrapper de demonstração pública efêmera (Vercel Serverless).
Executa 1 teste via subprocesso isolado (sys.executable -c) com ambiente estritamente configurado:
- PUBLIC_DEMO_MODE=true
- ENABLE_DEMO_CADASTRO=true
- DATABASE_URL apontando para banco temporário único criado em TemporaryDirectory.
- Nenhuma mutação de os.environ global no processo pai e sem impacto em outros testes.
- Valida:
  1. /api/health retorna cadastro_fonte SIMULADO_DEMO e aviso de demonstração pública.
  2. /api/portfolio/summary retorna 5 títulos e nominal R$ 501.000,00 com aviso obrigatório.
  3. POST /api/simulations com samples/demo.csv retorna 9 submetidos, total_nominal=30050.00,
     1 aprovado, 8 recusados, líquido aprovado R$ 4.700,00.
  4. GET /api/simulations/{id} preserva exatamente os mesmos valores.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestVercelDemoWrapperIsolated(unittest.TestCase):
    def test_smoke_public_demo_wrapper_isolated_subprocess(self):
        """
        Executa teste smoke isolado do wrapper Vercel em subprocesso dedicado.
        Garante isolamento absoluto de variáveis de ambiente, banco e imports.
        """
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        codex_root = Path(__file__).resolve().parent.parent.parent
        validadores_json = (repo_root / "validadores_antecipe.json").resolve()
        demo_csv = (codex_root / "samples" / "demo.csv").resolve()

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test-isolated-vercel-demo.db"
            db_url = f"sqlite:///{temp_db.as_posix()}"

            env = dict(os.environ)
            env["PUBLIC_DEMO_MODE"] = "true"
            env["ENABLE_DEMO_CADASTRO"] = "true"
            env["DATABASE_URL"] = db_url
            env["VALIDADORES_JSON_PATH"] = str(validadores_json)
            env["PYTHONPATH"] = str(codex_root)

            smoke_code = f"""
import sys
from fastapi.testclient import TestClient
from backend.vercel_app import app

client = TestClient(app)

# 1. Health
rh = client.get('/api/health')
assert rh.status_code == 200, f'Health failed: {{rh.status_code}}'
dh = rh.json()
assert dh['cadastro_fonte'] == 'SIMULADO_DEMO'
assert dh['total_registros_estoque'] == 5
assert 'aviso_demo_publica' in dh

# 2. Portfolio Summary
rp = client.get('/api/portfolio/summary')
assert rp.status_code == 200
dp = rp.json()
assert dp['total_recebiveis'] == 5
assert dp['total_nominal'] == '501000.00'
avisos = dp.get('avisos', [])
assert any('Demonstração pública' in a for a in avisos)

# 3. POST Demo CSV
with open(r'{demo_csv}', 'rb') as f:
    files = {{'file': ('demo.csv', f, 'text/csv')}}
    r_sim = client.post('/api/simulations', files=files)

assert r_sim.status_code == 200
ds = r_sim.json()
assert ds['total_itens'] == 9
assert ds['aprovados'] == 1
assert ds['recusados'] == 8
assert ds['total_nominal'] == '30050.00'
assert ds['total_liquido'] == '4700.00'

# 4. GET Simulation by ID
sim_id = ds['simulation_id']
r_get = client.get(f'/api/simulations/{{sim_id}}')
assert r_get.status_code == 200
dg = r_get.json()
assert dg['total_nominal'] == '30050.00'
assert dg['total_liquido'] == '4700.00'
assert dg['resultados'][0]['documento'] == 'NF-5001'
assert dg['resultados'][0]['valor_liquido'] == '4700.00'

print('VERCEL_WRAPPER_SMOKE_OK')
"""
            proc = subprocess.run(
                [sys.executable, "-c", smoke_code],
                env=env,
                capture_output=True,
                text=True,
                check=False
            )

            if proc.returncode != 0:
                self.fail(f"Subprocesso falhou com código {proc.returncode}:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")

            self.assertIn("VERCEL_WRAPPER_SMOKE_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
