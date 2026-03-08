#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from context_db import connect, load_config, normalize_rel


def _risk_score(impact_files: int, is_critical: bool) -> int:
    score = impact_files * 2
    if is_critical:
        score *= 5
    return score


def _read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _fts_query(name: str) -> str:
    # Avoid FTS5 syntax errors on dotted namespaces (e.g. A.B.C).
    q = re.sub(r"[^A-Za-z0-9_]+", " ", name).strip()
    return q


def _score(impacted: dict[str, int], path: str, delta: int) -> None:
    if not path or delta == 0:
        return
    impacted[path] = impacted.get(path, 0) + delta


def _load_coupling_edges(cfg_root: Path, rel_s: str) -> list[dict[str, int | float | str]]:
    payload = _read_json(cfg_root / ".vibe" / "reports" / "change_coupling.json")
    if not isinstance(payload, dict):
        return []
    raw_pairs = payload.get("pairs")
    if not isinstance(raw_pairs, list):
        return []
    out: list[dict[str, int | float | str]] = []
    for row in raw_pairs:
        if not isinstance(row, dict):
            continue
        a = row.get("a")
        b = row.get("b")
        count = row.get("count")
        if not isinstance(a, str) or not isinstance(b, str) or not isinstance(count, int):
            continue
        if a == rel_s:
            out.append({"path": b, "count": count, "jaccard": float(row.get("jaccard") or 0.0)})
        elif b == rel_s:
            out.append({"path": a, "count": count, "jaccard": float(row.get("jaccard") or 0.0)})
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Impact analysis (deps + coupling + symbol heuristics).")
    parser.add_argument("path", help="Target file path (repo-relative).")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args(argv)

    cfg = load_config()
    target_path = Path(args.path)
    root_res = cfg.root.resolve()
    if target_path.is_absolute():
        target_path = target_path.resolve(strict=False)
    else:
        target_path = (cfg.root / target_path).resolve(strict=False)
    try:
        rel = target_path.relative_to(root_res)
    except ValueError:
        print(f"[impact] refuse: outside repo root: {target_path}", file=sys.stderr)
        return 2
    rel_s = normalize_rel(rel)

    con = connect()
    try:
        syms = con.execute(
            "SELECT name, exported_int, tags_json FROM symbols WHERE file = ? ORDER BY exported_int DESC, name LIMIT 50",
            (rel_s,),
        ).fetchall()
        names = [r["name"] for r in syms if r["name"]]
        is_critical = any(r["tags_json"] and r["tags_json"] != "[]" for r in syms)

        impacted: dict[str, int] = {}
        reasons: dict[str, list[str]] = {}

        def add_reason(path: str, reason: str) -> None:
            reasons.setdefault(path, [])
            if reason not in reasons[path]:
                reasons[path].append(reason)

        # Direct graph signal from the indexed dependency table.
        inbound = con.execute("SELECT from_file FROM deps WHERE to_file = ?", (rel_s,)).fetchall()
        outbound = con.execute("SELECT to_file FROM deps WHERE from_file = ?", (rel_s,)).fetchall()
        for r in inbound:
            p = str(r["from_file"])
            if p == rel_s:
                continue
            _score(impacted, p, 6)
            add_reason(p, "depends-on-target")
        for r in outbound:
            p = str(r["to_file"])
            if p == rel_s:
                continue
            _score(impacted, p, 2)
            add_reason(p, "target-depends-on")

        # Symbol-name search remains as a weaker fallback/augmentation signal.
        for n in names[:20]:
            q = _fts_query(str(n))
            if not q:
                continue
            rows = con.execute(
                "SELECT path FROM fts_files WHERE fts_files MATCH ? LIMIT 200",
                (q,),
            ).fetchall()
            for r in rows:
                p = str(r["path"])
                if p == rel_s:
                    continue
                _score(impacted, p, 1)
                add_reason(p, f"symbol:{n}")

        # Git-history coupling is useful for polyglot repos even when imports are sparse.
        for edge in _load_coupling_edges(cfg.root, rel_s):
            p = str(edge["path"])
            if p == rel_s:
                continue
            delta = max(1, min(10, int(edge["count"])))
            _score(impacted, p, delta)
            add_reason(p, f"coupling:{edge['count']}")

        ranked = sorted(impacted.items(), key=lambda kv: (-kv[1], kv[0]))
        top = ranked[: args.limit]
    finally:
        con.close()

    score = _risk_score(len(impacted), is_critical)
    print(f"Impact for: {rel_s}")
    print(f"- impacted_files: {len(impacted)}")
    print(f"- critical: {is_critical}")
    print(f"- risk_score: {score}")
    if score > 50:
        print("- NOTE: consider a checkpoint before large changes.")

    if top:
        print("\nTop impacted files:")
        for p, n in top:
            why = ", ".join(reasons.get(p, [])[:3])
            suffix = f" [{why}]" if why else ""
            print(f"- {p} (score={n}){suffix}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
