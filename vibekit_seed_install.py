#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
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

DEFAULT_RELEASE_REPO = "servaltullius/vibe-kit-seed"
DEFAULT_CODEX_HOME = Path("~/.codex").expanduser()
CODEX_PROMPT_HEADER = "## Vibe-kit Auto-Prompt (Missing in Repo)"
CODEX_PROMPT_START = "<!-- vibekit:auto-prompt:start -->"
CODEX_PROMPT_END = "<!-- vibekit:auto-prompt:end -->"


@dataclass(frozen=True)
class ReleaseAssets:
    seed_md: Path
    seed_sha256: str
    installer_path: Path
    sha256sums_path: Path


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
            "- (Once) Run: `python3 scripts/vibe.py configure --apply`\n"
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
            "- (Once) Run: `python3 scripts/vibe.py configure --apply`\n"
            "- Run: `python3 scripts/vibe.py doctor --full`\n"
            "- Avoid repo-wide formatting/unrelated refactors.\n",
        ),
        "copilot": (
            ".github/copilot-instructions.md",
            "# Copilot Instructions\n\n"
            "- Use `.vibe/context/LATEST_CONTEXT.md` for repo context.\n"
            "- (Once) Run: `python3 scripts/vibe.py configure --apply`\n"
            "- Prefer small, localized changes.\n",
        ),
        "cursor": (
            ".cursor/rules/vibekit.md",
            "# Cursor Rules (vibe-kit)\n\n"
            "- Read: `.vibe/context/LATEST_CONTEXT.md`\n"
            "- (Once) Run: `python3 scripts/vibe.py configure --apply`\n"
            "- Run: `python3 scripts/vibe.py doctor --full`\n",
        ),
        "gemini": (
            "GEMINI.md",
            "# Gemini Instructions\n\n"
            "- Read: `.vibe/context/LATEST_CONTEXT.md`\n"
            "- (Once) Run: `python3 scripts/vibe.py configure --apply`\n"
            "- Run: `python3 scripts/vibe.py doctor --full`\n",
        ),
    }
    if agent == "all":
        for key in ("codex", "claude", "copilot", "cursor", "gemini"):
            rel, content = templates[key]
            _safe_write(root / rel, content.encode("utf-8"), force=force, apply=apply)
        return
    if agent not in templates:
        raise SystemExit(f"unknown --agent: {agent} (expected: codex|claude|copilot|cursor|gemini|all)")
    rel, content = templates[agent]
    _safe_write(root / rel, content.encode("utf-8"), force=force, apply=apply)


def _parse_sha256sums(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for idx, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line)
        if not m:
            raise ValueError(f"invalid SHA256SUMS line {idx}: {raw!r}")
        sha = m.group(1).lower()
        name = m.group(2).strip()
        if not name:
            raise ValueError(f"invalid SHA256SUMS line {idx}: empty filename")
        if name in out and out[name] != sha:
            raise ValueError(f"conflicting SHA256SUMS entry for {name}")
        out[name] = sha
    return out


def _resolve_release_assets(base_dir: Path) -> ReleaseAssets:
    sums_path = base_dir / "SHA256SUMS"
    if not sums_path.exists():
        raise ValueError(f"missing SHA256SUMS in {base_dir}")
    sums = _parse_sha256sums(sums_path.read_text(encoding="utf-8", errors="ignore"))

    seed_names = sorted(name for name in sums if name.startswith("VIBEKIT_SEED-") and name.endswith(".md"))
    if len(seed_names) != 1:
        raise ValueError(f"expected exactly one seed file in SHA256SUMS, found={len(seed_names)}")
    seed_name = seed_names[0]
    seed_path = base_dir / seed_name
    if not seed_path.exists():
        raise ValueError(f"missing seed file: {seed_name}")

    installer_name = "vibekit_seed_install.py"
    if installer_name not in sums:
        raise ValueError("SHA256SUMS missing vibekit_seed_install.py")
    installer_path = base_dir / installer_name
    if not installer_path.exists():
        raise ValueError(f"missing installer file: {installer_name}")

    # Verify all declared files that are present in this download directory.
    for name, expected in sums.items():
        p = base_dir / name
        if not p.exists():
            continue
        actual = _sha256_file(p)
        if actual != expected:
            raise ValueError(f"sha256 mismatch: {name} expected={expected} actual={actual}")

    return ReleaseAssets(
        seed_md=seed_path,
        seed_sha256=sums[seed_name],
        installer_path=installer_path,
        sha256sums_path=sums_path,
    )


def _write_ci_guard_workflow(root: Path, *, force: bool, apply: bool) -> bool:
    rel = Path(".github/workflows/vibekit-guard.yml")
    path = root / rel
    if path.exists() and not force:
        return False
    if not apply:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    content = textwrap.dedent(
        """\
        name: vibekit-guard
        on:
          pull_request:
          push:
            branches: [main]

        jobs:
          vibe:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
              - uses: actions/setup-python@v5
                with:
                  python-version: "3.x"
              - name: Configure vibe-kit
                run: python3 scripts/vibe.py configure --apply
              - name: Run vibe doctor
                run: python3 scripts/vibe.py doctor --full
              - name: Validate agent instructions
                run: python3 scripts/vibe.py agents doctor --fail
        """
    )
    path.write_text(content, encoding="utf-8")
    return True


def _run_vibe(root: Path, args: list[str]) -> None:
    vibe = root / "scripts" / "vibe.py"
    if not vibe.exists():
        raise RuntimeError("scripts/vibe.py not found after installation")
    subprocess.check_call([sys.executable, str(vibe), *args], cwd=str(root))


def _bootstrap(
    *,
    root: Path,
    release_repo: str,
    release_tag: str | None,
    force: bool,
    apply: bool,
    agent: str | None,
    run_setup: bool,
    post_configure: bool,
    post_doctor: bool,
    post_hooks: bool,
    write_ci_guard: bool,
) -> int:
    root = root.resolve()
    if shutil.which("gh") is None:
        print("[bootstrap] missing `gh` CLI. Install GitHub CLI first.", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="vibekit-bootstrap-") as td:
        dl = Path(td)
        cmd = [
            "gh",
            "release",
            "download",
            "--repo",
            release_repo,
            "--pattern",
            "VIBEKIT_SEED-*.md",
            "--pattern",
            "vibekit_seed_install.py",
            "--pattern",
            "SHA256SUMS",
            "--dir",
            str(dl),
        ]
        if release_tag:
            cmd.insert(3, release_tag)
        try:
            subprocess.check_call(cmd)
            assets = _resolve_release_assets(dl)
        except (subprocess.CalledProcessError, ValueError) as e:
            print(f"[bootstrap] failed to download/verify release assets: {e}", file=sys.stderr)
            return 2

        rc = _install(
            seed_md=assets.seed_md,
            root=root,
            expected_seed_sha256=assets.seed_sha256,
            force=force,
            apply=apply,
            agent=agent,
            run_setup=run_setup,
        )
        if rc != 0:
            return rc

        if write_ci_guard:
            written = _write_ci_guard_workflow(root, force=force, apply=apply)
            if written:
                print("[bootstrap] wrote: .github/workflows/vibekit-guard.yml")
            else:
                print("[bootstrap] ci guard exists (use --force to overwrite)")

        if apply:
            try:
                if post_configure:
                    _run_vibe(root, ["configure", "--apply"])
                if post_doctor:
                    _run_vibe(root, ["doctor", "--full"])
                if post_hooks:
                    _run_vibe(root, ["hooks", "--install"])
            except (subprocess.CalledProcessError, RuntimeError) as e:
                print(f"[bootstrap] post-install step failed: {e}", file=sys.stderr)
                return 2

    return 0


def _default_template_dir() -> Path:
    try:
        out = subprocess.check_output(["git", "config", "--global", "--get", "init.templateDir"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = ""
    if out:
        return Path(os.path.expanduser(out))
    return Path("~/.git-template").expanduser()


def _build_global_post_checkout_hook_script(
    *,
    python_executable: str,
    installer_script: str,
    release_repo: str,
    release_tag: str | None,
    marker_file: str,
    agent: str,
) -> str:
    marker = marker_file.strip() or ".vibekit.auto"
    py_q = shlex.quote(python_executable)
    installer_q = shlex.quote(installer_script)
    repo_q = shlex.quote(release_repo)
    tag_part = f" --tag {shlex.quote(release_tag)}" if release_tag else ""
    agent_q = shlex.quote(agent)
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        repo="$(git rev-parse --show-toplevel 2>/dev/null || true)"
        if [ -z "$repo" ]; then
          exit 0
        fi
        if [ ! -f "$repo/{marker}" ]; then
          exit 0
        fi
        if [ -f "$repo/.vibe/config.json" ]; then
          exit 0
        fi

        {py_q} {installer_q} bootstrap --root "$repo" --repo {repo_q}{tag_part} --apply --agent {agent_q} --run-setup --post-configure --post-doctor --post-hooks --write-ci-guard || true
        """
    )


def _build_global_codex_vibekit_prompt_block(
    *,
    installer_script: str,
    release_repo: str,
    release_tag: str | None,
    marker_file: str,
    suppress_file: str,
) -> str:
    marker = marker_file.strip() or ".vibekit.auto"
    suppress = suppress_file.strip() or ".vibekit.ignore"
    installer_q = shlex.quote(installer_script)
    repo_q = shlex.quote(release_repo)
    tag_part = f" --tag {shlex.quote(release_tag)}" if release_tag else ""
    cmd = (
        f"python3 {installer_q} bootstrap --root . --repo {repo_q}{tag_part} "
        "--apply --agent all --run-setup --post-configure --post-doctor --post-hooks --write-ci-guard"
    )
    return textwrap.dedent(
        f"""\
        {CODEX_PROMPT_START}
        {CODEX_PROMPT_HEADER}
        - At the start of each coding session, if the current working directory is inside a git repository and `.vibe/config.json` is missing:
          - If `{suppress}` exists in repo root, do not ask.
          - Ask exactly once: "이 프로젝트에 vibe-kit이 없습니다. 지금 설치할까요? (yes/no)"
          - If user says `yes`:
            - Run: `{cmd}`
            - Create `{marker}` in repo root.
          - If user says `no`:
            - Create `{suppress}` in repo root to suppress repeated prompts.
        {CODEX_PROMPT_END}
        """
    ).strip()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _pick_codex_global_instructions_file(codex_home: Path) -> Path:
    override = codex_home / "AGENTS.override.md"
    if override.exists() and _read_text(override).strip():
        return override
    return codex_home / "AGENTS.md"


def _install_codex_global_prompt(
    *,
    codex_home: Path,
    installer_script: str,
    release_repo: str,
    release_tag: str | None,
    marker_file: str,
    suppress_file: str,
    force: bool,
) -> tuple[bool, Path]:
    home = codex_home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    target = _pick_codex_global_instructions_file(home)
    target.parent.mkdir(parents=True, exist_ok=True)

    existing = _read_text(target)
    block = _build_global_codex_vibekit_prompt_block(
        installer_script=installer_script,
        release_repo=release_repo,
        release_tag=release_tag,
        marker_file=marker_file,
        suppress_file=suppress_file,
    )
    replacement = block + "\n"

    start = existing.find(CODEX_PROMPT_START)
    end = existing.find(CODEX_PROMPT_END)
    if start != -1 and end != -1 and end > start:
        if not force:
            return False, target
        end = end + len(CODEX_PROMPT_END)
        updated = existing[:start].rstrip()
        if updated:
            updated += "\n\n"
        updated += replacement
        tail = existing[end:].lstrip("\n")
        if tail:
            updated += "\n" + tail
        target.write_text(updated, encoding="utf-8", newline="\n")
        return True, target

    legacy = existing.find(CODEX_PROMPT_HEADER)
    if legacy != -1:
        if not force:
            return False, target
        next_heading = existing.find("\n## ", legacy + len(CODEX_PROMPT_HEADER))
        tail = existing[next_heading + 1 :] if next_heading != -1 else ""
        head = existing[:legacy].rstrip()
        updated = head
        if updated:
            updated += "\n\n"
        updated += replacement
        if tail:
            updated += "\n" + tail.lstrip("\n")
        target.write_text(updated, encoding="utf-8", newline="\n")
        return True, target

    updated = existing
    if updated and not updated.endswith("\n"):
        updated += "\n"
    if updated and not updated.endswith("\n\n"):
        updated += "\n"
    updated += replacement
    target.write_text(updated, encoding="utf-8", newline="\n")
    return True, target


def _install_global_hook(
    *,
    template_dir: Path,
    hook_script: str,
    force: bool,
) -> int:
    template_dir = template_dir.expanduser().resolve()
    hooks_dir = template_dir / "hooks"
    hook_path = hooks_dir / "post-checkout"

    hooks_dir.mkdir(parents=True, exist_ok=True)
    if hook_path.exists() and not force:
        print(f"[global-hook] exists: {hook_path} (use --force to overwrite)")
        return 0

    hook_path.write_text(hook_script, encoding="utf-8", newline="\n")
    mode = hook_path.stat().st_mode
    hook_path.chmod(mode | 0o111)

    subprocess.check_call(["git", "config", "--global", "init.templateDir", str(template_dir)])

    print(f"[global-hook] installed: {hook_path}")
    print(f"[global-hook] configured: git init.templateDir={template_dir}")
    print("[global-hook] opt-in per repo by creating `.vibekit.auto` in that repo root.")
    return 0


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
        help="Generate agent instruction files (optional): codex|claude|copilot|cursor|gemini|all",
    )
    p_install.add_argument(
        "--run-setup",
        action="store_true",
        help="After extraction, run scripts/setup_vibe_env.py (explicit opt-in).",
    )
    p_boot = sub.add_parser(
        "bootstrap",
        help="Download the latest (or tagged) release assets, verify checksums, and install into a repo.",
    )
    p_boot.add_argument("--root", type=Path, default=Path("."), help="Install root (project directory).")
    p_boot.add_argument("--repo", default=DEFAULT_RELEASE_REPO, help="GitHub repo in OWNER/REPO format.")
    p_boot.add_argument("--tag", help="Release tag to download (default: latest).")
    p_boot.add_argument("--force", action="store_true", help="Overwrite existing files.")
    p_boot.add_argument("--apply", action="store_true", help="Actually write files (default is dry-run).")
    p_boot.add_argument("--agent", help="Generate agent instruction files: codex|claude|copilot|cursor|gemini|all")
    p_boot.add_argument("--run-setup", action="store_true", help="Run scripts/setup_vibe_env.py after install.")
    p_boot.add_argument("--post-configure", action="store_true", help="Run `python3 scripts/vibe.py configure --apply`.")
    p_boot.add_argument("--post-doctor", action="store_true", help="Run `python3 scripts/vibe.py doctor --full`.")
    p_boot.add_argument("--post-hooks", action="store_true", help="Run `python3 scripts/vibe.py hooks --install`.")
    p_boot.add_argument(
        "--write-ci-guard",
        action="store_true",
        help="Write `.github/workflows/vibekit-guard.yml` in target repo.",
    )

    p_global = sub.add_parser(
        "install-global-hook",
        help="Install a global git template post-checkout hook for opt-in auto-bootstrap.",
    )
    p_global.add_argument("--template-dir", type=Path, help="Global git template directory (default: init.templateDir or ~/.git-template).")
    p_global.add_argument("--repo", default=DEFAULT_RELEASE_REPO, help="GitHub repo in OWNER/REPO format.")
    p_global.add_argument("--tag", help="Release tag to pin in global bootstrap commands (default: latest).")
    p_global.add_argument("--agent", default="all", help="Agent file set to generate during bootstrap.")
    p_global.add_argument("--marker-file", default=".vibekit.auto", help="Opt-in marker file name in project root.")
    p_global.add_argument("--suppress-file", default=".vibekit.ignore", help="Per-repo marker file to suppress install prompt.")
    p_global.add_argument("--codex-home", type=Path, default=DEFAULT_CODEX_HOME, help="Codex home directory for global AGENTS instructions.")
    p_global.add_argument(
        "--install-codex-prompt",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Install/update global Codex AGENTS prompt for missing vibe-kit repos.",
    )
    p_global.add_argument("--force", action="store_true", help="Overwrite existing post-checkout hook.")

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

    if args.cmd == "bootstrap":
        return _bootstrap(
            root=args.root,
            release_repo=args.repo,
            release_tag=args.tag,
            force=bool(args.force),
            apply=bool(args.apply),
            agent=args.agent,
            run_setup=bool(args.run_setup),
            post_configure=bool(args.post_configure),
            post_doctor=bool(args.post_doctor),
            post_hooks=bool(args.post_hooks),
            write_ci_guard=bool(args.write_ci_guard),
        )

    if args.cmd == "install-global-hook":
        template_dir = args.template_dir or _default_template_dir()
        hook_script = _build_global_post_checkout_hook_script(
            python_executable=sys.executable,
            installer_script=str(Path(__file__).resolve()),
            release_repo=args.repo,
            release_tag=args.tag,
            marker_file=args.marker_file,
            agent=args.agent,
        )
        try:
            rc = _install_global_hook(template_dir=template_dir, hook_script=hook_script, force=bool(args.force))
            if rc != 0:
                return rc
            if bool(args.install_codex_prompt):
                changed, target = _install_codex_global_prompt(
                    codex_home=args.codex_home,
                    installer_script=str(Path(__file__).resolve()),
                    release_repo=args.repo,
                    release_tag=args.tag,
                    marker_file=args.marker_file,
                    suppress_file=args.suppress_file,
                    force=bool(args.force),
                )
                if changed:
                    print(f"[global-codex] installed: {target}")
                else:
                    print(f"[global-codex] unchanged: {target}")
            else:
                print("[global-codex] skipped (--no-install-codex-prompt)")
            return 0
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"[global-hook] failed: {e}", file=sys.stderr)
            return 2

    raise RuntimeError(f"unknown cmd: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
