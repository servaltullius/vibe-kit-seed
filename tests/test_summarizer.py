from __future__ import annotations

import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import summarizer  # noqa: E402
from context_db import ensure_schema  # noqa: E402


@dataclass
class _DummyCfg:
    root: Path
    latest_file: Path
    max_recent_files: int = 10


def _memory_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    ensure_schema(con)
    return con


class TestSummarizer(unittest.TestCase):
    def test_uses_recent_change_log_for_changed_and_deleted_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            latest = root / ".vibe" / "context" / "LATEST_CONTEXT.md"
            cfg = _DummyCfg(root=root, latest_file=latest)

            con = _memory_db()
            con.execute("INSERT INTO files(path,mtime,hash,loc,size) VALUES (?,?,?,?,?)", ("src/live.py", 10.0, "h1", 20, 200))
            con.execute("INSERT INTO recent_changes(path,changed_at,kind) VALUES (?,?,?)", ("src/live.py", 10.0, "changed"))
            con.execute("INSERT INTO recent_changes(path,changed_at,kind) VALUES (?,?,?)", ("src/gone.py", 9.0, "deleted"))
            con.commit()

            out = io.StringIO()
            with patch.object(summarizer, "load_config", return_value=cfg), patch.object(summarizer, "connect", return_value=con), redirect_stdout(out):
                rc = summarizer.main([])

            self.assertEqual(rc, 0)
            rendered = latest.read_text(encoding="utf-8")
            self.assertIn("src/live.py (loc=20, changed)", rendered)
            self.assertIn("src/gone.py (loc=-, deleted)", rendered)

    def test_falls_back_to_mtime_when_recent_log_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            latest = root / ".vibe" / "context" / "LATEST_CONTEXT.md"
            cfg = _DummyCfg(root=root, latest_file=latest)

            con = _memory_db()
            con.execute("INSERT INTO files(path,mtime,hash,loc,size) VALUES (?,?,?,?,?)", ("src/recent.py", 20.0, "h2", 5, 50))
            con.commit()

            with patch.object(summarizer, "load_config", return_value=cfg), patch.object(summarizer, "connect", return_value=con):
                rc = summarizer.main(["--full"])

            self.assertEqual(rc, 0)
            rendered = latest.read_text(encoding="utf-8")
            self.assertIn("src/recent.py", rendered)


if __name__ == "__main__":
    unittest.main()
