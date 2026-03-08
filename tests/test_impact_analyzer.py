from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import impact_analyzer  # noqa: E402
from context_db import ensure_schema  # noqa: E402


@dataclass
class _DummyCfg:
    root: Path
    exclude_dirs: list[str] = field(default_factory=list)


def _memory_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    ensure_schema(con)
    return con


class TestImpactAnalyzer(unittest.TestCase):
    def test_prefers_dependency_and_coupling_signals_over_symbol_noise(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".vibe" / "reports").mkdir(parents=True, exist_ok=True)
            (root / ".vibe" / "reports" / "change_coupling.json").write_text(
                json.dumps(
                    {
                        "pairs": [
                            {"a": "src/core.py", "b": "src/api.py", "count": 4, "jaccard": 0.6},
                            {"a": "src/core.py", "b": "docs/notes.md", "count": 1, "jaccard": 0.1},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            con = _memory_db()
            try:
                con.execute("INSERT INTO files(path,mtime,hash,loc,size) VALUES (?,?,?,?,?)", ("src/core.py", 1.0, "a", 10, 10))
                con.execute("INSERT INTO files(path,mtime,hash,loc,size) VALUES (?,?,?,?,?)", ("src/api.py", 1.0, "b", 10, 10))
                con.execute("INSERT INTO files(path,mtime,hash,loc,size) VALUES (?,?,?,?,?)", ("docs/notes.md", 1.0, "c", 10, 10))
                con.execute(
                    "INSERT INTO symbols(name,file,line,kind,signature,access,doc,tags_json,attrs_json,exported_int) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("SharedService", "src/core.py", 1, "class", "class SharedService", "public", "@critical core", '["@critical"]', "[]", 1),
                )
                con.execute("INSERT INTO deps(from_file,to_file,kind) VALUES (?,?,?)", ("src/api.py", "src/core.py", "py_import"))
                con.execute("INSERT INTO fts_files(path,content) VALUES (?,?)", ("src/api.py", "SharedService"))
                con.execute("INSERT INTO fts_files(path,content) VALUES (?,?)", ("docs/notes.md", "SharedService"))
                con.commit()

                out = io.StringIO()
                with (
                    patch.object(impact_analyzer, "connect", return_value=con),
                    patch.object(impact_analyzer, "load_config", return_value=_DummyCfg(root=root)),
                    redirect_stdout(out),
                ):
                    rc = impact_analyzer.main(["src/core.py", "--limit=5"])

                self.assertEqual(rc, 0)
                lines = [line for line in out.getvalue().splitlines() if line.startswith("- ")]
                impacted = [line for line in lines if "(score=" in line]
                self.assertTrue(impacted)
                self.assertIn("src/api.py", impacted[0])
                self.assertIn("depends-on-target", impacted[0])
                self.assertIn("coupling:4", impacted[0])
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
