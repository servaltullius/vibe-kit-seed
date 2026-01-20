#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_CONFIG = {
    "project_name": "CHANGE_ME",
    "root": ".",
    "exclude_dirs": [
        "node_modules",
        "vendor",
        "third_party",
        "external",
        "extern",
        "deps",
        ".git",
        ".vibe",
        ".venv",
        "venv",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cache",
        ".idea",
        "dist",
        "build",
        "out",
        "coverage",
        "bin",
        "obj",
        "artifacts",
        "target",
        ".gradle",
        ".dart_tool",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".turbo",
        ".tmp",
        "__pycache__",
    ],
    "include_globs": [
        "**/*.cs",
        "**/*.xaml",
        "**/*.fs",
        "**/*.vb",
        "**/*.py",
        "**/*.js",
        "**/*.jsx",
        "**/*.ts",
        "**/*.tsx",
        "**/*.go",
        "**/*.rs",
        "**/*.java",
        "**/*.kt",
        "**/*.c",
        "**/*.h",
        "**/*.cpp",
        "**/*.hpp",
        "**/*.csproj",
        "**/*.sln",
        "**/*.fsproj",
        "**/*.vbproj",
        "**/*.md",
        "**/*.json",
        "**/*.yml",
        "**/*.yaml",
        "**/*.toml",
        "**/*.xml",
    ],
    "critical_tags": ["@critical", "CRITICAL:"],
    "context": {"latest_file": ".vibe/context/LATEST_CONTEXT.md", "max_recent_files": 12},
    "quality_gates": {
        "cycle_block": True,
        "dotnet_build_block_on_increase": True,
        "typecheck_prefer_solution": False,
        "complexity_warn_threshold": 15,
        "max_method_lines_warn": 50,
        "max_nesting_warn": 4,
        "max_params_warn": 5,
    },
    "placeholders": {
        "enabled": True,
        "target_lang": "korean",
        "bad_unit_words_ko": ["초", "분", "시간", "포인트", "%", "동안", "초당"],
    },
    "profiling": {"enabled_by_default": False, "mode": "dotnet", "entry": None},
}


DEFAULT_REQUIREMENTS = """watchdog>=4.0.0
python-dateutil>=2.8.2
"""


DEFAULT_DONT_DO_THIS = """# DONT_DO_THIS (vibe-kit)

Avoid these by default:
- Repo-wide formatting/re-linting.
- Large “cleanup” refactors unrelated to the task.
- Editing sample `*.xml` data outputs unless explicitly needed.
- Changing placeholder/token rules without updating tests.
"""


DEFAULT_AGENT_CHECKLIST = """# AGENT_CHECKLIST (vibe-kit)

## Quick start (do this first)
- Read: `.vibe/context/LATEST_CONTEXT.md`
- If you run only one command:
  - (WSL/Linux) `python3 scripts/vibe.py doctor --full`
  - (Windows) `scripts\\vibe.cmd doctor --full`

## Before coding
- Read: `.vibe/agent_memory/DONT_DO_THIS.md`
- Check impact for shared/core files: `python3 scripts/vibe.py impact <path>`
- Find entry points fast:
  - `python3 scripts/vibe.py search TranslationService`
  - `python3 scripts/vibe.py search PlaceholderMasker`

## While coding
- Keep changes small and localized.
- For placeholder/token logic, add/adjust tests under `tests/XTranslatorAi.Tests`.
- When validating xTranslator outputs: `python3 scripts/vibe.py qa <file.xml>`

## Before finishing
- Run: `python3 scripts/vibe.py doctor --full` (or at least `python3 scripts/vibe.py doctor`)
- Run tests (core): `dotnet test tests/XTranslatorAi.Tests/XTranslatorAi.Tests.csproj -c Release`
"""


DEFAULT_PROFILE_GUIDE = """# PROFILE_GUIDE (vibe-kit)

This project is primarily a Windows WPF app + Core library.

## Recommended (Windows) tooling
- PerfView (ETW) for CPU sampling
- `dotnet-trace` for .NET trace collection (optional)

### dotnet-trace quick start
1) Install (once):
   - `dotnet tool install --global dotnet-trace`
2) Run the app (or a target process), find PID, then collect:
   - `dotnet-trace collect --process-id <PID> --duration 00:00:20 -o trace.nettrace`
3) Open `trace.nettrace` in Visual Studio / PerfView.

## vibe-kit integration
- `python3 scripts/vibe.py doctor --full --profile` will only summarize existing logs under `.vibe/reports/`.
- No source-code injection is performed.
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _write_json_if_missing(path: Path, obj: object) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Initialize repo-local vibe-kit scaffolding.")
    parser.add_argument("--install-deps", action="store_true", help="Install Python deps via pip.")
    args = parser.parse_args(argv)

    root = _repo_root()
    vibe = root / ".vibe"

    created_dirs = 0
    for rel in ["brain", "context", "db", "reports", "agent_memory", "locks"]:
        (vibe / rel).mkdir(parents=True, exist_ok=True)
        created_dirs += 1

    project_name = root.name
    config = dict(DEFAULT_CONFIG)
    if config.get("project_name") == "CHANGE_ME":
        config["project_name"] = project_name

    created_files = []
    if _write_json_if_missing(vibe / "config.json", config):
        created_files.append(".vibe/config.json")
    if _write_if_missing(vibe / "brain" / "requirements.txt", DEFAULT_REQUIREMENTS):
        created_files.append(".vibe/brain/requirements.txt")
    if _write_if_missing(vibe / "agent_memory" / "DONT_DO_THIS.md", DEFAULT_DONT_DO_THIS):
        created_files.append(".vibe/agent_memory/DONT_DO_THIS.md")
    if _write_if_missing(vibe / "AGENT_CHECKLIST.md", DEFAULT_AGENT_CHECKLIST):
        created_files.append(".vibe/AGENT_CHECKLIST.md")
    if _write_if_missing(vibe / "context" / "PROFILE_GUIDE.md", DEFAULT_PROFILE_GUIDE):
        created_files.append(".vibe/context/PROFILE_GUIDE.md")
    if _write_if_missing(vibe / "context" / "LATEST_CONTEXT.md", "# LATEST_CONTEXT\n\n(Generated by vibe-kit)\n"):
        created_files.append(".vibe/context/LATEST_CONTEXT.md")

    print(f"[vibe-kit] ensured dirs under: {vibe}")
    if created_files:
        print("[vibe-kit] created:")
        for f in created_files:
            print(f"  - {f}")
    else:
        print("[vibe-kit] no new files (already initialized).")

    if args.install_deps:
        req = vibe / "brain" / "requirements.txt"
        print(f"[vibe-kit] installing deps: {req}")
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
        try:
            subprocess.check_call(cmd, cwd=str(root))
        except subprocess.CalledProcessError as e:
            print(f"[vibe-kit] pip failed: {e}", file=sys.stderr)
            return e.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
