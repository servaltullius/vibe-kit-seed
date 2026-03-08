from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import indexer  # noqa: E402
from context_db import VibeConfig, ensure_schema  # noqa: E402


def _cfg(root: Path) -> VibeConfig:
    return VibeConfig(
        project_name="demo",
        root=root,
        exclude_dirs=[],
        include_globs=["**/*.py", "**/*.ts", "**/*.csproj"],
        critical_tags=["@critical", "CRITICAL:"],
        latest_file=root / ".vibe" / "context" / "LATEST_CONTEXT.md",
        max_recent_files=10,
        context_commands={},
        checks={},
        quality_gates={},
        placeholders={},
        profiling={},
        architecture={"python_roots": ["src", "."], "js_aliases": {"@app/": "src/"}},
    )


def _memory_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    ensure_schema(con)
    return con


class TestIndexerDeps(unittest.TestCase):
    def test_scan_all_indexes_python_and_ts_deps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src" / "domain").mkdir(parents=True, exist_ok=True)
            (root / "src" / "infra").mkdir(parents=True, exist_ok=True)
            (root / "src" / "ui").mkdir(parents=True, exist_ok=True)
            (root / "src" / "domain" / "a.py").write_text("from infra import b\n", encoding="utf-8")
            (root / "src" / "infra" / "b.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "src" / "ui" / "main.ts").write_text("import { thing } from '@app/infra/web'\n", encoding="utf-8")
            (root / "src" / "infra" / "web.ts").write_text("export const thing = 1;\n", encoding="utf-8")

            cfg = _cfg(root)
            con = _memory_db()
            try:
                for path in sorted(root.rglob("*")):
                    if path.is_file():
                        indexer.index_file(path, cfg, con=con)
                indexer._rebuild_deps(con, cfg, [p for p in root.rglob("*") if p.is_file()])

                rows = con.execute("SELECT from_file,to_file,kind FROM deps ORDER BY from_file,to_file,kind").fetchall()
                triples = {(r["from_file"], r["to_file"], r["kind"]) for r in rows}
                self.assertIn(("src/domain/a.py", "src/infra/b.py", "py_from"), triples)
                self.assertIn(("src/ui/main.ts", "src/infra/web.ts", "js_import"), triples)
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
