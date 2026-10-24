#!/usr/bin/env python3
"""Gera adaptações nativas a partir dos perfis canônicos em agents/."""

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_agent(path):
    data = path.read_text(encoding="utf-8")
    if not data.startswith("---\n"):
        raise ValueError(f"Frontmatter ausente: {path.name}")
    _, meta, body = data.split("---\n", 2)
    values = {}
    for line in meta.splitlines():
        if line.strip():
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    if not all(values.get(key) for key in ("name", "description")):
        raise ValueError(f"Metadados incompletos: {path.name}")
    return values, body.strip() + "\n", data


def build():
    codex_dir = ROOT / ".codex" / "agents"
    claude_dir = ROOT / ".claude" / "agents"
    codex_dir.mkdir(parents=True, exist_ok=True)
    claude_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for source in sorted((ROOT / "agents").glob("*.md")):
        meta, instructions, original = parse_agent(source)
        slug = meta["name"].replace("_", "-")
        content = (
            "name = " + json.dumps(meta["name"], ensure_ascii=False) + "\n"
            + "description = " + json.dumps(meta["description"], ensure_ascii=False) + "\n"
            + "developer_instructions = " + json.dumps(instructions, ensure_ascii=False) + "\n"
        )
        (codex_dir / f"{slug}.toml").write_text(content, encoding="utf-8")
        (claude_dir / f"{slug}.md").write_text(original, encoding="utf-8")
        count += 1
    destination = ROOT / ".claude" / "skills"
    for skill in (ROOT / ".agents" / "skills").iterdir():
        if skill.is_dir():
            shutil.copytree(skill, destination / skill.name, dirs_exist_ok=True)
    print(f"Adaptadores gerados: {count} agentes, skills locais sincronizadas.")


if __name__ == "__main__":
    build()
