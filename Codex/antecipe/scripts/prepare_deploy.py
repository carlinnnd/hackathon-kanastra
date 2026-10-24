"""Prepara pacote restrito de publicação, sem dados de estoque/bancos/credenciais."""
import hashlib
import json
import re
import shutil
from pathlib import Path


def preparar(stage):
    root = Path(__file__).resolve().parents[3]
    stage = Path(stage).resolve()
    allowed = (root / "Codex" / "antecipe" / ".data").resolve()
    if allowed not in stage.parents:
        raise ValueError("Pacote deve ficar dentro de Codex/antecipe/.data")
    if stage.exists():
        raise ValueError("Use um diretório novo para cada publicação; não sobrescreva pacotes anteriores.")
    stage.mkdir(parents=True)
    for name in ("app.py", "requirements.txt", ".python-version", "vercel.json", ".vercelignore", "validadores_antecipe.json"):
        shutil.copy2(root / name, stage / name)
    backend = root / "Codex/antecipe/backend"
    for source in backend.rglob("*.py"):
        rel = source.relative_to(backend)
        if "tests" in rel.parts or "__pycache__" in rel.parts:
            continue
        target = stage / "Codex/antecipe/backend" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for name in ("samples/demo.csv", "data/cnpj_situacao_mock.csv"):
        source = root / "Codex/antecipe" / name
        target = stage / "Codex/antecipe" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    dist = root / "Codex/antecipe/frontend/dist"
    html = (dist / "index.html").read_text(encoding="utf-8")
    for name in ["index.html"] + [m.lstrip("/") for m in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)]:
        target = stage / "public" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dist / name, target)
    files = sorted(p for p in stage.rglob("*") if p.is_file())
    print(json.dumps({"stage": str(stage), "files": len(files), "bytes": sum(p.stat().st_size for p in files),
        "hashes": {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    preparar(parser.parse_args().stage)
