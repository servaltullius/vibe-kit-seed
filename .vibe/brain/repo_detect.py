#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable


GRADLE_FILES = ("gradlew", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")


def read_text_best_effort(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def walk_repo_files(root: Path, exclude_dirs: Iterable[str]):
    excluded = {str(entry).lower() for entry in exclude_dirs}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name.lower() not in excluded]
        for name in filenames:
            yield Path(dirpath) / name


def repo_has_any_suffix(root: Path, exclude_dirs: Iterable[str], suffixes: set[str]) -> bool:
    wanted = {suffix.lower() for suffix in suffixes}
    for path in walk_repo_files(root, exclude_dirs):
        if path.suffix.lower() in wanted:
            return True
    return False


def repo_has_any_named_file(root: Path, exclude_dirs: Iterable[str], names: set[str]) -> bool:
    wanted = {name.lower() for name in names}
    for path in walk_repo_files(root, exclude_dirs):
        if path.name.lower() in wanted:
            return True
    return False


def detect_package_manager(root: Path, package_json: dict[str, Any] | None) -> tuple[str, str]:
    if isinstance(package_json, dict):
        raw_pm = package_json.get("packageManager")
        if isinstance(raw_pm, str) and raw_pm.strip():
            name = raw_pm.strip().split("@", 1)[0].strip().lower()
            if name in {"npm", "pnpm", "yarn", "bun"}:
                return name, "packageManager field"

    if (root / "bun.lock").exists() or (root / "bun.lockb").exists():
        return "bun", "lockfile"
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm", "lockfile"
    if (root / "yarn.lock").exists():
        return "yarn", "lockfile"
    if (root / "package-lock.json").exists():
        return "npm", "lockfile"

    return "npm", "default"


def detect_pyright(root: Path) -> bool:
    if (root / "pyrightconfig.json").exists():
        return True
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        return "[tool.pyright]" in read_text_best_effort(pyproject)
    return False


def load_package_json(root: Path) -> dict[str, Any] | None:
    path = root / "package.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def collect_dotnet_targets(root: Path, exclude_dirs: Iterable[str]) -> tuple[list[Path], list[Path]]:
    slns: list[Path] = []
    projects: list[Path] = []
    for path in walk_repo_files(root, exclude_dirs):
        suffix = path.suffix.lower()
        if suffix == ".sln":
            slns.append(path)
        elif suffix in {".csproj", ".fsproj", ".vbproj"}:
            projects.append(path)
    slns.sort(key=lambda path: path.as_posix())
    projects.sort(key=lambda path: path.as_posix())
    return slns, projects


def _dotnet_project_score(path: Path) -> int:
    score = 0
    name = path.name.lower()
    path_text = path.as_posix().lower()
    if "core" in name:
        score += 50
    if "lib" in name or "library" in name:
        score += 30
    if "/tests/" in path_text or name.endswith(".tests.csproj") or ".tests" in name:
        score -= 100
    if "test" in name:
        score -= 80
    if "app" in name or "ui" in name or "wpf" in name:
        score -= 30
    if "/src/" in path_text:
        score += 10
    return score


def pick_dotnet_target(root: Path, exclude_dirs: Iterable[str], *, prefer_solution: bool) -> Path | None:
    slns, projects = collect_dotnet_targets(root, exclude_dirs)

    if prefer_solution and slns:
        root_slns = [path for path in slns if path.parent == root]
        return root_slns[0] if root_slns else slns[0]

    if projects:
        return sorted(projects, key=lambda path: (-_dotnet_project_score(path), path.as_posix()))[0]

    if slns:
        root_slns = [path for path in slns if path.parent == root]
        return root_slns[0] if root_slns else slns[0]

    return None


def has_gradle_files(root: Path, exclude_dirs: Iterable[str]) -> bool:
    if any((root / name).exists() for name in GRADLE_FILES):
        return True
    return repo_has_any_named_file(root, exclude_dirs, set(GRADLE_FILES))


def has_pytest_config(root: Path) -> bool:
    if (root / "pytest.ini").exists():
        return True
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return False
    return "[tool.pytest" in read_text_best_effort(pyproject)
