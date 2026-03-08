#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from context_db import normalize_rel


JS_EXTS = [
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".mts",
    ".cts",
]

JS_IMPORT_RE = re.compile(
    r"""
    (?:
      \bimport\s+(?:[\w*\s{},]*\s+from\s+)? |
      \bexport\s+(?:[\w*\s{},]*\s+from\s+) |
      \brequire\s*\(\s* |
      \bimport\s*\(\s*
    )
    ['"](?P<spec>[^'"]+)['"]
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Dep:
    from_file: str
    to_file: str
    kind: str
    line: int | None = None
    detail: str | None = None


def line_number(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def candidate_python_roots(cfg) -> list[str]:
    arch = cfg.architecture or {}
    roots_raw = arch.get("python_roots")
    roots: list[str] = []
    if isinstance(roots_raw, list):
        roots = [str(x).strip().strip("/").replace("\\", "/") for x in roots_raw if isinstance(x, str) and x.strip()]

    defaults: list[str] = []
    if (cfg.root / "src").exists():
        defaults.append("src")
    defaults.append(".")

    merged: list[str] = []
    for root in [*roots, *defaults]:
        item = root or "."
        if item not in merged:
            merged.append(item)
    return merged


def build_python_module_index(cfg, py_files: list[str]) -> dict[str, str]:
    roots = candidate_python_roots(cfg)
    module_to_file: dict[str, str] = {}
    for rel_s in py_files:
        p = PurePosixPath(rel_s)
        if p.suffix != ".py":
            continue
        for root in roots:
            if root not in {".", ""}:
                pref = root.rstrip("/") + "/"
                if not rel_s.startswith(pref):
                    continue
                sub = rel_s[len(pref) :]
            else:
                sub = rel_s

            parts = [x for x in sub.split("/") if x]
            if not parts:
                continue
            last = parts[-1]
            if not last.endswith(".py"):
                continue
            parts[-1] = last[:-3]
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if not parts:
                continue

            module_to_file.setdefault(".".join(parts), rel_s)
            break
    return module_to_file


def resolve_python_module(module_to_file: dict[str, str], module: str) -> str | None:
    cur = module.strip(".")
    while cur:
        hit = module_to_file.get(cur)
        if hit:
            return hit
        if "." not in cur:
            break
        cur = cur.rsplit(".", 1)[0]
    return None


def resolve_python_relative(*, cfg, from_rel: str, level: int, module: str | None, name: str | None = None) -> str | None:
    base = PurePosixPath(from_rel).parent
    for _ in range(max(0, int(level) - 1)):
        base = base.parent

    parts: list[str] = []
    if module:
        parts.extend([p for p in module.split(".") if p])
    if name:
        parts.extend([p for p in name.split(".") if p])

    cand = base.joinpath(*parts) if parts else base
    candidates = [cand.with_suffix(".py"), cand / "__init__.py"]
    root_res = cfg.root.resolve()
    for rel_p in candidates:
        abs_p = (cfg.root / rel_p).resolve(strict=False)
        try:
            abs_p.relative_to(root_res)
        except ValueError:
            continue
        if abs_p.exists() and abs_p.is_file():
            return normalize_rel(abs_p.relative_to(cfg.root))
    return None


def python_deps_for_file(cfg, *, from_rel: str, text: str, module_to_file: dict[str, str]) -> Iterable[Dep]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    deps: list[Dep] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = (alias.name or "").strip()
                if not mod:
                    continue
                to_rel = resolve_python_module(module_to_file, mod)
                if not to_rel:
                    continue
                deps.append(Dep(from_file=from_rel, to_file=to_rel, kind="py_import", line=int(getattr(node, "lineno", 0) or 0) or None, detail=mod))
        elif isinstance(node, ast.ImportFrom):
            level = int(getattr(node, "level", 0) or 0)
            module = getattr(node, "module", None)
            module_s = str(module).strip() if module else None

            if level > 0:
                for alias in node.names:
                    name = (alias.name or "").strip()
                    if name == "*":
                        name = None
                    to_rel = resolve_python_relative(cfg=cfg, from_rel=from_rel, level=level, module=module_s, name=name)
                    if to_rel:
                        detail = f"{'.' * level}{module_s + '.' if module_s else ''}{alias.name}".strip(".")
                        deps.append(Dep(from_file=from_rel, to_file=to_rel, kind="py_from", line=int(getattr(node, "lineno", 0) or 0) or None, detail=detail))
                continue

            if not module_s:
                continue

            resolved_any = False
            for alias in node.names:
                name = (alias.name or "").strip()
                if not name or name == "*":
                    continue
                to_rel = resolve_python_module(module_to_file, f"{module_s}.{name}")
                if to_rel:
                    deps.append(Dep(from_file=from_rel, to_file=to_rel, kind="py_from", line=int(getattr(node, "lineno", 0) or 0) or None, detail=f"{module_s}.{name}"))
                    resolved_any = True

            if resolved_any:
                continue

            to_rel = resolve_python_module(module_to_file, module_s)
            if to_rel:
                deps.append(Dep(from_file=from_rel, to_file=to_rel, kind="py_from", line=int(getattr(node, "lineno", 0) or 0) or None, detail=module_s))

    return deps


def js_aliases(cfg) -> dict[str, str]:
    arch = cfg.architecture or {}
    raw = arch.get("js_aliases")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        out[key] = value
    return out


def apply_js_alias(spec: str, aliases: dict[str, str]) -> str:
    if not aliases:
        return spec
    best_key = None
    for key in aliases:
        if spec.startswith(key) and (best_key is None or len(key) > len(best_key)):
            best_key = key
    if best_key is None:
        return spec
    prefix = aliases[best_key].rstrip("/") + "/"
    rest = spec[len(best_key) :].lstrip("/")
    return prefix + rest


def resolve_js_spec(cfg, *, from_rel: str, spec: str, aliases: dict[str, str]) -> str | None:
    spec2 = apply_js_alias(spec, aliases).replace("\\", "/")
    if not spec2:
        return None

    from_dir = PurePosixPath(from_rel).parent
    if spec2.startswith("."):
        cand = (cfg.root / from_dir / spec2).resolve(strict=False)
    else:
        if spec == spec2:
            return None
        cand = (cfg.root / spec2).resolve(strict=False)

    root_res = cfg.root.resolve()
    try:
        rel = cand.relative_to(root_res)
    except ValueError:
        return None

    if rel.suffix and (cfg.root / rel).is_file():
        return normalize_rel(rel)

    for ext in JS_EXTS:
        path = cfg.root / rel.with_suffix(ext)
        if path.is_file():
            return normalize_rel(rel.with_suffix(ext))

    p_dir = cfg.root / rel
    if p_dir.is_dir():
        for ext in JS_EXTS:
            index_file = p_dir / f"index{ext}"
            if index_file.is_file():
                return normalize_rel(rel / f"index{ext}")

    return None


def js_deps_for_file(cfg, *, from_rel: str, text: str, aliases: dict[str, str]) -> Iterable[Dep]:
    deps: list[Dep] = []
    for match in JS_IMPORT_RE.finditer(text):
        spec = (match.group("spec") or "").strip()
        if not spec:
            continue
        to_rel = resolve_js_spec(cfg, from_rel=from_rel, spec=spec, aliases=aliases)
        if not to_rel:
            continue
        deps.append(Dep(from_file=from_rel, to_file=to_rel, kind="js_import", line=line_number(text, match.start()), detail=spec))
    return deps
