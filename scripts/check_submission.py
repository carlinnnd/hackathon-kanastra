#!/usr/bin/env python3
"""Auditoria estrutural do kit e dos campos mínimos para submissão."""

import argparse
import json
import re
import sys
from pathlib import Path

from prompt_ledger import Ledger


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "AGENTS.md", "CLAUDE.md", "docs/CRITERIOS.md", "docs/ESPECIFICACAO.md",
    "docs/EVIDENCIAS.md", "docs/MATRIZ_RECUSAS.md", "docs/REGISTRO_PROMPTS.md",
    ".codex/hooks.json", ".claude/settings.json", "scripts/prompt_ledger.py",
    "scripts/generate_fixture.py", "scripts/benchmark.py", "scripts/check_logs.py", "research/REFERENCIAS.md",
]


def run(final=False, root=ROOT):
    errors = []
    warnings = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"Arquivo obrigatório ausente: {relative}")
    for relative in (".codex/hooks.json", ".claude/settings.json"):
        path = root / relative
        if path.is_file():
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
                for event in ("UserPromptSubmit", "Stop"):
                    if event not in obj.get("hooks", {}):
                        errors.append(f"Hook {event} ausente em {relative}")
            except json.JSONDecodeError:
                errors.append(f"Config JSON inválida: {relative}")
    codex = sorted((root / ".codex" / "agents").glob("*.toml"))
    claude = sorted((root / ".claude" / "agents").glob("*.md"))
    skills = sorted((root / ".agents" / "skills").glob("*/SKILL.md"))
    if len(codex) != 9 or len(claude) != 9:
        errors.append(f"Esperados 9 agentes em cada plataforma; codex={len(codex)}, claude={len(claude)}")
    if len(skills) != 5:
        errors.append(f"Esperadas 5 skills locais; encontrados {len(skills)}")
    for file in skills:
        if not re.match(r"^---\nname: [a-z0-9-]+\ndescription: .+\n---\n", file.read_text(encoding="utf-8")):
            errors.append(f"Skill com frontmatter inválido: {file}")
    if final:
        for relative in ("docs/ESPECIFICACAO.md", "docs/EVIDENCIAS.md", "docs/MATRIZ_RECUSAS.md"):
            path = root / relative
            if path.exists() and "PENDENTE" in path.read_text(encoding="utf-8"):
                errors.append(f"Ainda há PENDENTE em {relative}")
        entries, orphans, pending = Ledger(root).audit()
        if not entries:
            errors.append("Nenhum prompt registrado")
        if pending:
            errors.append(f"Prompts sem ação/resposta/verificação: {', '.join(pending)}")
        if orphans:
            errors.append(f"Eventos Stop sem prompt associado: {len(orphans)}")
        warnings.append("Auditoria estática não substitui testes funcionais, benchmark, revisão de segredos ou gitleaks no histórico Git.")
    for item in warnings:
        print(f"AVISO: {item}")
    for item in errors:
        print(f"ERRO: {item}")
    print(f"Auditoria {'final' if final else 'do kit'}: {'FALHOU' if errors else 'OK'}")
    return not errors


def main():
    parser = argparse.ArgumentParser(description="Confere estrutura do kit e pré-requisitos de entrega")
    parser.add_argument("--final", action="store_true", help="Exigir especificação preenchida e prompt ledger completo")
    args = parser.parse_args()
    return 0 if run(final=args.final) else 1


if __name__ == "__main__":
    sys.exit(main())
