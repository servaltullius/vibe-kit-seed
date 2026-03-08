#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from context_db import connect, is_excluded, load_config, normalize_rel
from dep_extractors import (
    Dep,
    build_python_module_index as build_python_dep_index,
    js_aliases as load_js_aliases,
    js_deps_for_file as extract_js_deps_for_file,
    python_deps_for_file as extract_python_deps_for_file,
)
from path_globs import matches_include_globs


@dataclass(frozen=True)
class Rule:
    name: str
    from_globs: list[str]
    to_globs: list[str]
    kinds: set[str] | None
    reason: str | None


def _matches_glob(rel_posix: str, glob: str) -> bool:
    return matches_include_globs(rel_posix, [glob])


def _matches_any(rel_posix: str, globs: list[str]) -> bool:
    for g in globs:
        if _matches_glob(rel_posix, g):
            return True
    return False


def _build_python_module_index(cfg, py_files: list[str]) -> dict[str, str]:
    return build_python_dep_index(cfg, py_files)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def _get_indexed_files(cfg) -> list[str]:
    con = connect()
    try:
        rows = con.execute("SELECT path FROM files ORDER BY path").fetchall()
        return [str(r["path"]) for r in rows if r and r["path"]]
    finally:
        con.close()


def _iter_files_by_glob(cfg, include_globs: list[str]) -> list[str]:
    root = cfg.root
    out: list[str] = []
    for pattern in include_globs:
        for p in root.glob(pattern):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            if is_excluded(rel, cfg.exclude_dirs):
                continue
            out.append(normalize_rel(rel))
    # de-dup + sort
    return sorted({p: None for p in out}.keys())


def _python_deps_for_file(cfg, *, from_rel: str, text: str, module_to_file: dict[str, str]) -> Iterable[Dep]:
    return extract_python_deps_for_file(cfg, from_rel=from_rel, text=text, module_to_file=module_to_file)


def _build_python_module_index(cfg, py_files: list[str]) -> dict[str, str]:
    return build_python_dep_index(cfg, py_files)


def _js_aliases(cfg) -> dict[str, str]:
    return load_js_aliases(cfg)


def _js_deps_for_file(cfg, *, from_rel: str, text: str, aliases: dict[str, str]) -> Iterable[Dep]:
    return extract_js_deps_for_file(cfg, from_rel=from_rel, text=text, aliases=aliases)


def _parse_rules(cfg) -> tuple[list[Rule], list[dict[str, Any]]]:
    arch = cfg.architecture or {}
    raw_rules = arch.get("rules")
    if not isinstance(raw_rules, list):
        return [], []

    rules: list[Rule] = []
    invalid: list[dict[str, Any]] = []

    for i, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            invalid.append({"index": i, "reason": "rule must be an object"})
            continue
        enabled = raw.get("enabled", True)
        if enabled is not True:
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            invalid.append({"index": i, "reason": "missing name"})
            continue

        from_globs_raw = raw.get("from_globs")
        to_globs_raw = raw.get("to_globs")
        if not (isinstance(from_globs_raw, list) and from_globs_raw):
            invalid.append({"index": i, "name": name, "reason": "missing from_globs"})
            continue
        if not (isinstance(to_globs_raw, list) and to_globs_raw):
            invalid.append({"index": i, "name": name, "reason": "missing to_globs"})
            continue

        from_globs = [str(x) for x in from_globs_raw if isinstance(x, str) and x.strip()]
        to_globs = [str(x) for x in to_globs_raw if isinstance(x, str) and x.strip()]
        if not from_globs or not to_globs:
            invalid.append({"index": i, "name": name, "reason": "empty from_globs/to_globs"})
            continue

        kinds_raw = raw.get("kinds")
        kinds: set[str] | None = None
        if isinstance(kinds_raw, list) and kinds_raw:
            kinds = {str(x) for x in kinds_raw if isinstance(x, str) and x.strip()}
            if not kinds:
                kinds = None

        reason = None
        if raw.get("reason") is not None:
            reason = str(raw.get("reason") or "").strip() or None

        rules.append(Rule(name=name, from_globs=from_globs, to_globs=to_globs, kinds=kinds, reason=reason))

    return rules, invalid


def _rule_match(rule: Rule, dep: Dep) -> bool:
    if rule.kinds is not None and dep.kind not in rule.kinds:
        return False
    return _matches_any(dep.from_file, rule.from_globs) and _matches_any(dep.to_file, rule.to_globs)


def render_boundaries_md(payload: dict[str, Any]) -> str:
    ts = payload.get("timestamp")
    ts_s = ""
    if isinstance(ts, (int, float)):
        ts_s = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))

    lines: list[str] = []
    lines.append("# Boundary violations (architecture rules)\n")
    if ts_s:
        lines.append(f"- Generated: `{ts_s}`")
    if payload.get("skipped"):
        reason = payload.get("reason") or "skipped"
        lines.append(f"- Status: skipped ({reason})\n")
        return "\n".join(lines).rstrip() + "\n"

    total = int(payload.get("stats", {}).get("violations", 0) or 0)
    lines.append(f"- Violations: `{total}`\n")

    by_rule = payload.get("by_rule")
    if isinstance(by_rule, list) and by_rule:
        lines.append("## By rule\n")
        for r in by_rule[:20]:
            if not isinstance(r, dict):
                continue
            lines.append(f"- `{r.get('rule')}`: {r.get('count')}")
        lines.append("")

    violations = payload.get("violations")
    if isinstance(violations, list) and violations:
        lines.append("## Violations (top)\n")
        for v in violations[:50]:
            if not isinstance(v, dict):
                continue
            rule = v.get("rule") or "rule"
            frm = v.get("from") or ""
            to = v.get("to") or ""
            kind = v.get("kind") or ""
            line = v.get("line")
            loc = f":{line}" if isinstance(line, int) and line > 0 else ""
            detail = v.get("detail")
            detail_s = f" ({detail})" if detail else ""
            lines.append(f"- `{frm}{loc}` -> `{to}` [{kind}] via `{rule}`{detail_s}")
        lines.append("")

    lines.append("## Tips\n")
    lines.append("- Prefer a narrow boundary (facade/port) instead of cross-importing internals.")
    lines.append("- For shared types/contracts, extract a small stable `contracts/` module to stop ripple edits.")
    lines.append("- Re-run `python3 scripts/vibe.py boundaries` after refactors to confirm violations decrease.\n")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Architecture boundary rule checker (config-driven).")
    ap.add_argument("--out", default=".vibe/reports/boundaries.json")
    ap.add_argument("--md-out", default=".vibe/reports/boundaries.md")
    ap.add_argument("--max-violations", type=int, default=200)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Fail when any boundary violation exists (takes precedence over --best-effort).",
    )
    ap.add_argument(
        "--best-effort",
        action="store_true",
        help="Never fail the process (exit 0); ignored when --strict is set.",
    )
    args = ap.parse_args(argv)

    cfg = load_config()
    out_path = cfg.root / str(args.out)
    md_out_path = cfg.root / str(args.md_out)

    arch = cfg.architecture or {}
    if arch.get("enabled") is False:
        payload = {
            "ok": True,
            "skipped": True,
            "reason": "architecture.enabled=false",
            "timestamp": time.time(),
            "out_path": str(args.out),
            "md_path": str(args.md_out),
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_out_path.parent.mkdir(parents=True, exist_ok=True)
        md_out_path.write_text(render_boundaries_md(payload), encoding="utf-8")
        print(f"[boundaries] SKIP: {payload['reason']}")
        print(f"[boundaries] wrote: {out_path}")
        print(f"[boundaries] wrote: {md_out_path}")
        return 0

    rules, invalid_rules = _parse_rules(cfg)
    if not rules:
        payload = {
            "ok": True,
            "skipped": True,
            "reason": "no architecture.rules configured",
            "timestamp": time.time(),
            "out_path": str(args.out),
            "md_path": str(args.md_out),
            "invalid_rules": invalid_rules,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_out_path.parent.mkdir(parents=True, exist_ok=True)
        md_out_path.write_text(render_boundaries_md(payload), encoding="utf-8")
        print(f"[boundaries] SKIP: {payload['reason']}")
        print(f"[boundaries] wrote: {out_path}")
        print(f"[boundaries] wrote: {md_out_path}")
        return 0

    # Prefer indexed file list (doctor runs indexer first); fall back to glob scan.
    try:
        files = _get_indexed_files(cfg)
    except Exception:
        files = []
    if not files:
        files = _iter_files_by_glob(cfg, cfg.include_globs)

    # Filter down to candidate "from" files to keep scans fast.
    from_globs_all = sorted({g for r in rules for g in r.from_globs})
    candidate_from = [f for f in files if _matches_any(f, from_globs_all)]

    # Build python module index only for python candidates; resolve targets in full python set.
    py_files = [f for f in files if f.endswith(".py")]
    module_to_file = build_python_dep_index(cfg, py_files)
    aliases = _js_aliases(cfg)

    violations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add_violation(rule: Rule, dep: Dep) -> None:
        key = (rule.name, dep.kind, dep.from_file, dep.to_file)
        if key in seen:
            return
        seen.add(key)
        violations.append(
            {
                "rule": rule.name,
                "reason": rule.reason,
                "from": dep.from_file,
                "to": dep.to_file,
                "kind": dep.kind,
                "line": dep.line,
                "detail": dep.detail,
            }
        )

    # 1) ProjectReference deps (high-level C# project boundaries).
    con = connect()
    try:
        rows = con.execute("SELECT from_file,to_file,kind FROM deps").fetchall()
    finally:
        con.close()
    for r in rows:
        dep = Dep(from_file=str(r["from_file"]), to_file=str(r["to_file"]), kind=str(r["kind"]))
        if dep.from_file == dep.to_file:
            continue
        for rule in rules:
            if _rule_match(rule, dep):
                add_violation(rule, dep)
        if len(violations) >= int(args.max_violations):
            break

    # 2) Code-level deps (Python + JS/TS).
    for from_rel in candidate_from:
        if len(violations) >= int(args.max_violations):
            break
        abs_p = cfg.root / from_rel
        if not abs_p.exists() or not abs_p.is_file():
            continue
        text = _read_text(abs_p)
        if text is None:
            continue

        deps: list[Dep] = []
        suf = abs_p.suffix.lower()
        if suf == ".py":
            deps = list(_python_deps_for_file(cfg, from_rel=from_rel, text=text, module_to_file=module_to_file))
        elif suf in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}:
            deps = list(_js_deps_for_file(cfg, from_rel=from_rel, text=text, aliases=aliases))

        for dep in deps:
            if dep.from_file == dep.to_file:
                continue
            rel_p = Path(dep.to_file)
            if is_excluded(rel_p, cfg.exclude_dirs):
                continue
            for rule in rules:
                if _rule_match(rule, dep):
                    add_violation(rule, dep)
            if len(violations) >= int(args.max_violations):
                break

    by_rule_counts: dict[str, int] = {}
    for v in violations:
        by_rule_counts[str(v.get("rule"))] = by_rule_counts.get(str(v.get("rule")), 0) + 1
    by_rule = [{"rule": k, "count": int(v)} for k, v in sorted(by_rule_counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    payload = {
        "ok": True,
        "skipped": False,
        "timestamp": time.time(),
        "out_path": str(args.out),
        "md_path": str(args.md_out),
        "rules": [{"name": r.name, "from_globs": r.from_globs, "to_globs": r.to_globs, "kinds": sorted(r.kinds) if r.kinds else None} for r in rules],
        "invalid_rules": invalid_rules,
        "stats": {
            "rules": len(rules),
            "files_seen": len(files),
            "files_scanned": len(candidate_from),
            "violations": len(violations),
        },
        "by_rule": by_rule,
        "violations": violations,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_out_path.parent.mkdir(parents=True, exist_ok=True)
    md_out_path.write_text(render_boundaries_md(payload), encoding="utf-8")

    print(f"[boundaries] wrote: {out_path}")
    print(f"[boundaries] wrote: {md_out_path}")
    if violations:
        print(f"[boundaries] violations={len(violations)} (showing top {min(len(violations), 10)})")
        for v in violations[:10]:
            frm = v.get("from")
            to = v.get("to")
            rule = v.get("rule")
            line = v.get("line")
            loc = f":{line}" if isinstance(line, int) and line > 0 else ""
            print(f"- {frm}{loc} -> {to} ({rule})")
    else:
        print("[boundaries] ok: no violations")

    if violations and args.strict:
        return 1
    block = bool(cfg.quality_gates.get("boundary_block", False))
    if violations and block and not args.best_effort:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
