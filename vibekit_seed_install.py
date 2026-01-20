#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


PAYLOAD_RE = re.compile(
    r"<!--\s*VIBEKIT_PAYLOAD_BASE64_BEGIN\s*-->\s*(?P<b64>.*?)\s*<!--\s*VIBEKIT_PAYLOAD_BASE64_END\s*-->",
    re.DOTALL,
)


ALLOWED_EXACT: set[str] = {
    "scripts/vibe.py",
    "scripts/vibe.cmd",
    "scripts/vibekit.py",
    "scripts/vibekit.cmd",
    "scripts/setup_vibe_env.py",
    "scripts/install_hooks.py",
    ".vibe/README.md",
    ".vibe/AGENT_CHECKLIST.md",
    ".vibe/agent_memory/DONT_DO_THIS.md",
    ".vibe/context/PROFILE_GUIDE.md",
    ".vibe/brain/requirements.txt",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_payload(seed_text: str) -> bytes:
    m = PAYLOAD_RE.search(seed_text)
    if not m:
        raise SystemExit("payload not found in seed file")
    b64 = "".join(m.group("b64").split())
    return base64.b64decode(b64.encode("ascii"))


def _normalize_member_name(name: str) -> str:
    if not name:
        raise ValueError("empty zip entry name")
    if "\\" in name:
        raise ValueError(f"backslash not allowed in zip entry: {name!r}")
    if "\x00" in name:
        raise ValueError("NUL not allowed in zip entry name")
    if name == "." or name.startswith("./") or "/./" in name or name.endswith("/."):
        raise ValueError(f"dot segments not allowed in zip entry: {name!r}")
    if name.startswith("/"):
        raise ValueError(f"absolute path not allowed in zip entry: {name!r}")
    if re.match(r"^[A-Za-z]:", name):
        raise ValueError(f"windows drive path not allowed in zip entry: {name!r}")

    p = PurePosixPath(name)
    if p.is_absolute():
        raise ValueError(f"absolute path not allowed in zip entry: {name!r}")
    if any(part == ".." for part in p.parts):
        raise ValueError(f"path traversal not allowed in zip entry: {name!r}")

    normalized = p.as_posix()
    if normalized == "":
        raise ValueError("empty normalized zip entry name")
    return normalized


def _is_allowed(rel: str) -> bool:
    if rel in ALLOWED_EXACT:
        return True
    p = PurePosixPath(rel)
    if p.parent == PurePosixPath("scripts") and p.suffix == ".py":
        return p.name in {"vibe.py", "vibekit.py", "setup_vibe_env.py", "install_hooks.py"}
    if p.parent == PurePosixPath(".vibe/brain") and p.suffix == ".py":
        return True
    return False


def _safe_write(path: Path, data: bytes, *, force: bool, apply: bool) -> bool:
    if path.exists() and not force:
        return False
    if not apply:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def _apply_gitignore(root: Path, *, apply: bool) -> None:
    gi = root / ".gitignore"
    if not gi.exists():
        return
    wanted = [
        "",
        "# vibe-kit",
        ".vibe/db/",
        ".vibe/reports/",
        ".vibe/locks/",
        ".vibe/context/LATEST_CONTEXT.md",
    ]
    text = gi.read_text(encoding="utf-8", errors="ignore")
    for line in wanted:
        if line and line in text:
            continue
        if line == "" and text.endswith("\n\n"):
            continue
        if line == "":
            text += "\n"
        else:
            text += ("\n" if not text.endswith("\n") else "") + line + "\n"
    if apply:
        gi.write_text(text, encoding="utf-8")


def _write_agent_instructions(root: Path, agent: str, *, force: bool, apply: bool) -> None:
    agent = agent.lower().strip()
    templates: dict[str, tuple[str, str]] = {
        "codex": (
            "AGENTS.md",
            "# Agent Notes\n\n"
            "## Quick start\n"
            "- Read: `.vibe/context/LATEST_CONTEXT.md`\n"
            "- Run: `python3 scripts/vibe.py doctor --full`\n\n"
            "## Repo rules\n"
            "- Avoid repo-wide formatting and unrelated cleanup refactors.\n"
            "- Treat placeholders/tokens as runtime contracts (e.g. `<...>`, `{0}`, `%s`).\n"
            "- Prefer small, testable edits; keep behavior stable.\n",
        ),
        "claude": (
            "CLAUDE.md",
            "# Project Instructions\n\n"
            "- Read: `.vibe/context/LATEST_CONTEXT.md`\n"
            "- Run: `python3 scripts/vibe.py doctor --full`\n"
            "- Avoid repo-wide formatting/unrelated refactors.\n",
        ),
        "copilot": (
            ".github/copilot-instructions.md",
            "# Copilot Instructions\n\n"
            "- Use `.vibe/context/LATEST_CONTEXT.md` for repo context.\n"
            "- Prefer small, localized changes.\n",
        ),
        "cursor": (
            ".cursor/rules/vibekit.md",
            "# Cursor Rules (vibe-kit)\n\n"
            "- Read: `.vibe/context/LATEST_CONTEXT.md`\n"
            "- Run: `python3 scripts/vibe.py doctor --full`\n",
        ),
        "gemini": (
            "GEMINI.md",
            "# Gemini Instructions\n\n"
            "- Read: `.vibe/context/LATEST_CONTEXT.md`\n"
            "- Run: `python3 scripts/vibe.py doctor --full`\n",
        ),
    }
    if agent not in templates:
        raise SystemExit(f"unknown --agent: {agent}")
    rel, content = templates[agent]
    _safe_write(root / rel, content.encode("utf-8"), force=force, apply=apply)


def _install(
    *,
    seed_md: Path,
    root: Path,
    expected_seed_sha256: str,
    force: bool,
    apply: bool,
    agent: str | None,
    run_setup: bool,
) -> int:
    seed_md = seed_md.resolve()
    root = root.resolve()

    expected = expected_seed_sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise SystemExit("--expected-seed-sha256 must be a 64-char hex sha256")

    actual = _sha256_file(seed_md)
    if actual != expected:
        print(f"[seed] sha256 mismatch: expected={expected} actual={actual}", file=sys.stderr)
        return 2

    seed_text = seed_md.read_text(encoding="utf-8", errors="ignore")
    payload = _extract_payload(seed_text)

    created = 0
    skipped = 0
    with ZipFile(io.BytesIO(payload), "r") as z:
        seen_names: set[str] = set()
        for info in z.infolist():
            if info.is_dir():
                continue
            try:
                rel = _normalize_member_name(info.filename)
            except ValueError as e:
                print(f"[seed] invalid zip entry: {e}", file=sys.stderr)
                return 2
            if rel in seen_names:
                print(f"[seed] duplicate zip entry: {rel}", file=sys.stderr)
                return 2
            seen_names.add(rel)
            if not _is_allowed(rel):
                print(f"[seed] zip entry not allowlisted: {rel}", file=sys.stderr)
                return 2

        for info in z.infolist():
            if info.is_dir():
                continue
            rel = _normalize_member_name(info.filename)
            dest = root / rel
            data = z.read(info.filename)
            if _safe_write(dest, data, force=force, apply=apply):
                created += 1
            else:
                skipped += 1

    _apply_gitignore(root, apply=apply)

    if agent:
        _write_agent_instructions(root, agent, force=force, apply=apply)

    if run_setup:
        setup = root / "scripts" / "setup_vibe_env.py"
        if not setup.exists():
            print("[seed] setup requested but missing: scripts/setup_vibe_env.py", file=sys.stderr)
            return 2
        if not apply:
            print("[seed] setup requested but running in dry-run mode; skipping setup")
        else:
            subprocess.check_call([sys.executable, str(setup)], cwd=str(root))

    mode = "apply" if apply else "dry-run"
    print(f"[seed] installed ({mode}): created={created} skipped={skipped} root={root}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Install vibe-kit from a signed/hashed seed markdown.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_sha = sub.add_parser("sha256", help="Print sha256 of a file (for verification).")
    p_sha.add_argument("path", type=Path)

    p_install = sub.add_parser("install", help="Install files from VIBEKIT_SEED*.md into a repo.")
    p_install.add_argument("seed_md", type=Path, help="Path to VIBEKIT_SEED*.md")
    p_install.add_argument("--root", type=Path, default=Path("."), help="Install root (project directory).")
    p_install.add_argument("--expected-seed-sha256", required=True, help="Expected sha256 of the seed markdown file.")
    p_install.add_argument("--force", action="store_true", help="Overwrite existing files.")
    p_install.add_argument(
        "--apply",
        action="store_true",
        help="Actually write files. Without this flag, the installer runs in dry-run mode.",
    )
    p_install.add_argument(
        "--agent",
        help="Generate one agent instruction file (optional): codex|claude|copilot|cursor|gemini",
    )
    p_install.add_argument(
        "--run-setup",
        action="store_true",
        help="After extraction, run scripts/setup_vibe_env.py (explicit opt-in).",
    )

    args = ap.parse_args(argv)

    if args.cmd == "sha256":
        print(_sha256_file(args.path))
        return 0

    if args.cmd == "install":
        return _install(
            seed_md=args.seed_md,
            root=args.root,
            expected_seed_sha256=args.expected_seed_sha256,
            force=bool(args.force),
            apply=bool(args.apply),
            agent=args.agent,
            run_setup=bool(args.run_setup),
        )

    raise RuntimeError(f"unknown cmd: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
