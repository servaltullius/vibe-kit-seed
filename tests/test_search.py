from __future__ import annotations

import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import search as vibe_search  # noqa: E402
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


class TestSearch(unittest.TestCase):
    def test_exact_symbol_match_is_printed_before_fts_matches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            con = _memory_db()
            try:
                con.execute("INSERT INTO files(path,mtime,hash,loc,size) VALUES (?,?,?,?,?)", ("src/exact.py", 1.0, "a", 10, 10))
                con.execute("INSERT INTO files(path,mtime,hash,loc,size) VALUES (?,?,?,?,?)", ("src/other.py", 1.0, "b", 10, 10))
                con.execute(
                    "INSERT INTO symbols(name,file,line,kind,signature,access,doc,tags_json,attrs_json,exported_int) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("ExactMatch", "src/exact.py", 1, "function", "def ExactMatch()", "public", "exact docs", "[]", "[]", 1),
                )
                con.execute(
                    "INSERT INTO symbols(name,file,line,kind,signature,access,doc,tags_json,attrs_json,exported_int) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("ExactMatchHelper", "src/other.py", 1, "function", "def ExactMatchHelper()", "public", "helper docs", "[]", "[]", 1),
                )
                con.execute(
                    "INSERT INTO fts_symbols(name,file,doc,tags,signature,attrs) VALUES (?,?,?,?,?,?)",
                    ("ExactMatch", "src/exact.py", "exact docs", "", "def ExactMatch()", ""),
                )
                con.execute(
                    "INSERT INTO fts_symbols(name,file,doc,tags,signature,attrs) VALUES (?,?,?,?,?,?)",
                    ("ExactMatchHelper", "src/other.py", "helper docs", "", "def ExactMatchHelper()", ""),
                )
                con.execute("INSERT INTO fts_files(path,content) VALUES (?,?)", ("src/exact.py", "ExactMatch"))
                con.execute("INSERT INTO fts_files(path,content) VALUES (?,?)", ("src/other.py", "ExactMatchHelper"))
                con.commit()

                out = io.StringIO()
                err = io.StringIO()
                with (
                    patch.object(vibe_search, "connect", return_value=con),
                    patch.object(vibe_search, "load_config", return_value=_DummyCfg(root=root)),
                    redirect_stdout(out),
                    redirect_stderr(err),
                ):
                    rc = vibe_search.main(["ExactMatch", "--limit=5"])

                self.assertEqual(rc, 0)
                self.assertEqual(err.getvalue(), "")
                symbol_lines = [line for line in out.getvalue().splitlines() if line.startswith("- src/")]
                self.assertTrue(symbol_lines)
                self.assertEqual(symbol_lines[0], "- src/exact.py:def ExactMatch()")
            finally:
                con.close()

    def test_punctuation_query_uses_normalized_fts_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            con = _memory_db()
            try:
                con.execute("INSERT INTO files(path,mtime,hash,loc,size) VALUES (?,?,?,?,?)", ("src/widget.ts", 1.0, "a", 10, 10))
                con.execute(
                    "INSERT INTO fts_symbols(name,file,doc,tags,signature,attrs) VALUES (?,?,?,?,?,?)",
                    ("WidgetFactory", "src/widget.ts", "factory", "", "export function WidgetFactory()", ""),
                )
                con.execute("INSERT INTO fts_files(path,content) VALUES (?,?)", ("src/widget.ts", "Widget Factory"))
                con.commit()

                out = io.StringIO()
                err = io.StringIO()
                with (
                    patch.object(vibe_search, "connect", return_value=con),
                    patch.object(vibe_search, "load_config", return_value=_DummyCfg(root=root)),
                    redirect_stdout(out),
                    redirect_stderr(err),
                ):
                    rc = vibe_search.main(["Widget.Factory", "--limit=5"])

                self.assertEqual(rc, 0)
                self.assertNotIn("[search] fts error", err.getvalue())
                self.assertIn("src/widget.ts", out.getvalue())
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
