#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from context_db import load_config


def _git_root(cfg) -> Path | None:
    git_dir = cfg.root / ".git"
    return cfg.root if git_dir.exists() else None


def _staged_files(cfg) -> list[str]:
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
    p = subprocess.run(cmd, cwd=str(cfg.root), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if p.returncode != 0:
        return []
    files = [line.strip() for line in p.stdout.splitlines() if line.strip()]
    return files


def _run(py: Path, args: list[str]) -> int:
    cmd = [sys.executable, str(py), *args]
    p = subprocess.run(cmd)
    return p.returncode


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="vibe-kit pre-commit (staged-only, fast).")
    parser.add_argument("--run-tests", action="store_true", help="Also run core tests (slower).")
    args = parser.parse_args(argv)

    cfg = load_config()
    if _git_root(cfg) is None:
        print("[precommit] no .git directory found; skipping.")
        return 0

    staged = _staged_files(cfg)
    staged_cs = [f for f in staged if f.endswith(".cs")]
    staged_proj = [f for f in staged if f.endswith(".csproj") or f.endswith(".sln")]

    if not staged:
        print("[precommit] no staged files.")
        return 0

    brain = cfg.root / ".vibe" / "brain"

    # Update index for staged files only.
    for f in staged:
        if not (f.endswith(".cs") or f.endswith(".xaml") or f.endswith(".csproj") or f.endswith(".sln") or f.endswith(".md")):
            continue
        _run(brain / "indexer.py", ["--file", f])

    rc = 0

    # Typecheck gate only if C# code/project changed.
    if staged_cs or staged_proj:
        rc = max(rc, _run(brain / "typecheck_baseline.py", []))

    # Cycle detection only if project files changed.
    if staged_proj:
        rc = max(rc, _run(brain / "check_circular.py", []))

    # Complexity: warnings only (staged .cs).
    if staged_cs:
        _run(brain / "check_complexity.py", ["--files", *staged_cs])

    if args.run_tests:
        rc = max(rc, _run(brain / "run_core_tests.py", ["--fast"]))

    if rc != 0:
        print("[precommit] FAIL")
    else:
        print("[precommit] OK")
    return 1 if rc != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
