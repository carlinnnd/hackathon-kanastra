#!/usr/bin/env python3
"""Registro local, cronológico, sanitizado e reconciliável de prompts."""

import argparse
import contextlib
import datetime as dt
try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGEX = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "[PRIVATE_KEY_REDACTED]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[AWS_ACCESS_KEY_REDACTED]"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[TOKEN_REDACTED]"),
    (re.compile(r"(?i)\"(?:[a-z0-9_]*(?:key|token|password|secret|senha)[a-z0-9_]*)\"\s*:\s*\"[^\"]*\""), '"credential": "[REDACTED]"'),
    (re.compile(r"(?i)\b[a-z0-9_]*(?:key|token|password|secret|senha)[a-z0-9_]*\s*=\s*[^\s,;]+"), "[CREDENTIAL_REDACTED]"),
    (re.compile(r"(?i)\b(password|senha|token|secret|api[_-]?key|client[_-]?secret)\s*[:=]\s*(['\"]?)[^\s,;'\"]+"), r"\1=[REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF_REDACTED]"),
]


def scrub(value):
    text = str(value or "")
    for pattern, replacement in REGEX:
        text = pattern.sub(replacement, text)
    lines = []
    for line in text.splitlines():
        if len(line) < 20000 and (line.count(",") >= 2 or line.count(";") >= 2 or re.match(r"^\s*\d+[,;]", line)):
            lines.append("[LINHA_TABULAR_OMITIDA]")
        else:
            lines.append(line)
    return "\n".join(lines)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_events(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def aggregate(events):
    records = {}
    orphans = []
    resolved = set()
    for event in events:
        kind = event["kind"]
        if kind == "prompt":
            records[event["id"]] = dict(event)
        elif kind == "orphan":
            orphans.append(event)
        elif kind == "resolve_orphan":
            resolved.add(event["id"])
        elif kind in ("stop", "close") and event.get("id") in records:
            target = records[event["id"]]
            if kind == "stop":
                target["response"] = event.get("response", "")
                target["response_at"] = event.get("at", "")
            else:
                target.update({key: event[key] for key in ("action", "files", "verification")})
                target["closed_at"] = event["at"]
    return list(records.values()), [item for item in orphans if item["id"] not in resolved]


def fenced(text):
    max_ticks = max((len(match.group()) for match in re.finditer(r"`+", text)), default=0)
    marker = "`" * max(3, max_ticks + 1)
    return f"{marker}text\n{text}\n{marker}"


def render(records, orphans, title="Registro cronológico de prompts"):
    output = [
        f"# {title}",
        "",
        "Gerado a partir dos hooks e de inclusões manuais. Horários em UTC. Texto sanitizado, com SHA-256 do prompt original. Ações são confirmadas separadamente.",
        "",
        "> **Registros individuais da equipe:**",
        "> - [Registro de Carlos (Orquestração & Frentes)](REGISTRO_PROMPTS_CARLOS.md)",
        "> - [Registro de Elias](REGISTRO_PROMPTS_ELIAS.md)",
        "> - [Registro de Pina (Leandro)](REGISTRO_PROMPTS_PINA.md)",
        "",
        "> *Nota de integridade documental:* O texto integral fiel dos prompts oficiais encontra-se preservado sob `.hackathon/prompts/` (ex: `p0002_user.txt`). Na visualização sanitizada acima, sentenças com mais de duas vírgulas ou ponto-e-vírgula são marcadas como `[LINHA_TABULAR_OMITIDA]` pela rotina de proteção estrita contra vazamento de dados tabulares/CSV.",
        "",
        "## Link do Chat utilizado no gpt : https://chatgpt.com/share/6add11ef-1b68-83e9-a251-183b83577dc5",
        "",
    ]
    if not records:
        output.extend(["Nenhum prompt registrado ainda.", ""])
    for record in records:
        action = record.get("action", "PENDENTE — reconciliar com o que foi feito")
        output.extend([
            f"## {record['id']} — {record['at']} — {record['source']}",
            "",
            f"- Sessão: `{scrub(record.get('session', 'desconhecida'))}`",
            f"- SHA-256 do prompt original: `{record['digest']}`",
            "- Texto do prompt (sanitizado):",
            "",
            fenced(record["prompt"]),
            "",
            "- Última mensagem do assistente (prévia, não prova execução):",
            "",
            fenced(record.get("response", "NÃO CAPTURADA")),
            "",
            f"- **O que foi feito com a resposta:** {scrub(action)}",
            f"- Arquivos/artefatos: {scrub(record.get('files', 'PENDENTE'))}",
            f"- Verificação: {scrub(record.get('verification', 'PENDENTE'))}",
            "",
        ])
    if orphans:
        output.extend(["## Eventos sem prompt associado — investigar", ""])
        for event in orphans:
            output.append(f"- {event['at']} — {event.get('session', '?')}: resposta sem prompt reconhecido")
    return "\n".join(output) + "\n"


class Ledger:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.private = self.root / ".hackathon" / "prompts"
        self.path = self.root / "docs" / "prompts-events.jsonl"
        self.public = self.root / "docs" / "REGISTRO_PROMPTS.md"
        self.carlos = self.root / "docs" / "REGISTRO_PROMPTS_CARLOS.md"
        self.elias = self.root / "docs" / "REGISTRO_PROMPTS_ELIAS.md"
        self.pina = self.root / "docs" / "REGISTRO_PROMPTS_PINA.md"
    @contextlib.contextmanager
    def locked(self):
        self.private.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.private / "lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            fd = handle.fileno()
            if fcntl:
                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            elif msvcrt:
                handle.seek(0)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                yield

    def append(self, event):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())

    def _build_team_sections(self):
        sections = []
        for label, member_path in (
            ("Parte II — Registro Cronológico de PINA (Leandro)", self.pina),
            ("Parte III — Registro Cronológico de ELIAS", self.elias),
        ):
            if member_path.is_file():
                raw = member_path.read_text(encoding="utf-8")
                idx = raw.find("\n## ")
                if idx != -1:
                    sections.append(f"\n---\n\n# {label}\n{raw[idx:].rstrip()}\n")
        return "".join(sections)

    def update_public(self):
        entries, orphans = aggregate(load_events(self.path))
        self.public.parent.mkdir(parents=True, exist_ok=True)
        team_extra = self._build_team_sections()
        fd, temp_path = tempfile.mkstemp(prefix=".prompts-", dir=self.public.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(render(entries, orphans) + team_extra)
            os.replace(temp_path, self.public)
            # Renderiza espelhamento para o registro de Carlos
            carlos_fd, carlos_temp = tempfile.mkstemp(prefix=".prompts-carlos-", dir=self.public.parent)
            try:
                with os.fdopen(carlos_fd, "w", encoding="utf-8") as handle:
                    handle.write(render(entries, orphans, title="Registro cronológico de prompts — CARLOS"))
                os.replace(carlos_temp, self.carlos)
            finally:
                if os.path.exists(carlos_temp):
                    os.unlink(carlos_temp)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        return entries, orphans

    def prompt(self, source, session, prompt, turn=""):
        with self.locked():
            entries, _ = aggregate(load_events(self.path))
            index = max((int(item["id"][1:]) for item in entries), default=0) + 1
            event = {"kind": "prompt", "id": f"P{index:04d}", "at": now(), "source": scrub(source), "session": scrub(session), "turn": scrub(turn), "digest": sha256(prompt), "prompt": scrub(prompt)}
            self.append(event)
            self.update_public()
            return event["id"]

    def stop(self, session, response, turn=""):
        with self.locked():
            entries, _ = aggregate(load_events(self.path))
            candidates = [item for item in entries if item["session"] == scrub(session) and "response_at" not in item]
            if turn:
                matched = [item for item in candidates if item.get("turn") == scrub(turn)]
                if matched:
                    candidates = matched
            if candidates:
                self.append({"kind": "stop", "id": candidates[-1]["id"], "at": now(), "response": scrub(response or "Sem mensagem final capturada")})
            else:
                orphan_count = sum(1 for event in load_events(self.path) if event["kind"] == "orphan")
                self.append({"kind": "orphan", "id": f"O{orphan_count+1:04d}", "at": now(), "session": scrub(session)})
            self.update_public()

    def close(self, ident, action, files, verification):
        if not action.strip() or not verification.strip():
            raise ValueError("Ação e verificação são obrigatórias")
        with self.locked():
            entries, _ = aggregate(load_events(self.path))
            if ident not in {item["id"] for item in entries}:
                raise ValueError("ID de prompt inexistente")
            self.append({"kind": "close", "id": ident, "at": now(), "action": scrub(action), "files": scrub(files), "verification": scrub(verification)})
            self.update_public()

    def resolve_orphan(self, ident, reason):
        if not reason.strip():
            raise ValueError("Explique a reconciliação do evento órfão")
        with self.locked():
            _, orphans = aggregate(load_events(self.path))
            if ident not in {item["id"] for item in orphans}:
                raise ValueError("Evento órfão inexistente ou já resolvido")
            self.append({"kind": "resolve_orphan", "id": ident, "at": now(), "reason": scrub(reason)})
            self.update_public()

    def audit(self):
        entries, orphans = aggregate(load_events(self.path))
        pending = [item["id"] for item in entries if not item.get("action") or not item.get("verification") or not item.get("response_at")]
        return entries, orphans, pending


def main():
    parser = argparse.ArgumentParser(description="Registro cronológico de prompts do hackathon")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hook")
    manual = commands.add_parser("manual")
    manual.add_argument("--source", required=True)
    manual.add_argument("--prompt-file", type=Path, required=True)
    stop = commands.add_parser("stop")
    stop.add_argument("--session", default="session-01")
    stop.add_argument("--response", default="Sem mensagem final capturada")
    stop.add_argument("--turn", default="")
    close = commands.add_parser("close")
    close.add_argument("--id", required=True)
    close.add_argument("--action", required=True)
    close.add_argument("--files", default="Não se aplica")
    close.add_argument("--verification", required=True)
    resolve = commands.add_parser("resolve-orphan")
    resolve.add_argument("--id", required=True)
    resolve.add_argument("--reason", required=True)
    commands.add_parser("status")
    commands.add_parser("audit")
    args = parser.parse_args()
    ledger = Ledger()
    if args.command == "hook":
        payload = json.load(sys.stdin)
        event = payload.get("hook_event_name")
        source = "codex" if "turn_id" in payload else "claude-code"
        session = str(payload.get("session_id", "desconhecida"))
        if event == "UserPromptSubmit":
            ledger.prompt(source, session, str(payload.get("prompt", "")), str(payload.get("turn_id", "")))
        elif event == "Stop":
            ledger.stop(session, str(payload.get("last_assistant_message", "")), str(payload.get("turn_id", "")))
            print("{}")
        return 0
    if args.command == "manual":
        value = args.prompt_file.read_text(encoding="utf-8")
        print(f"Registrado {ledger.prompt(args.source, 'manual', value)}")
        return 0
    if args.command == "stop":
        ledger.stop(args.session, args.response, args.turn)
        print("Evento stop registrado")
        return 0
    if args.command == "close":
        ledger.close(args.id, args.action, args.files, args.verification)
        print(f"Reconciliado {args.id}")
        return 0
    if args.command == "resolve-orphan":
        ledger.resolve_orphan(args.id, args.reason)
        print(f"Evento órfão reconciliado: {args.id}")
        return 0
    entries, orphans, pending = ledger.audit()
    print(f"Prompts: {len(entries)} | Pendências: {len(pending)} | Eventos órfãos: {len(orphans)}")
    if pending:
        print("IDs pendentes: " + ", ".join(pending))
    if args.command == "audit" and (not entries or pending or orphans):
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Falha no registro de prompts ({type(exc).__name__}); confira o hook e execute registro manual.", file=sys.stderr)
        sys.exit(2)
