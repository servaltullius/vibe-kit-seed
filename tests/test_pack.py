from __future__ import annotations

import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import pack  # noqa: E402


@dataclass
class _DummyCfg:
    root: Path
    project_name: str = "demo"
    exclude_dirs: list[str] = field(default_factory=list)
    include_globs: list[str] = field(default_factory=list)
    max_recent_files: int = 10


def _memory_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE files (
          path TEXT PRIMARY KEY,
          loc INTEGER NOT NULL DEFAULT 0,
          mtime REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE symbols (
          name TEXT NOT NULL,
          file TEXT NOT NULL,
          line INTEGER NOT NULL,
          kind TEXT NOT NULL,
          signature TEXT,
          exported_int INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    return con


class TestPackScopeFallback(unittest.TestCase):
    def _run_pack(
        self,
        root: Path,
        argv: list[str],
        *,
        staged: list[str] | None = None,
        changed: list[str] | None = None,
        recent: list[str] | None = None,
        git_available: bool = True,
    ) -> tuple[int, str, str, Mock]:
        cfg = _DummyCfg(root=root)
        con = _memory_db()
        recent_mock = Mock(return_value=list(recent or []))
        out = io.StringIO()
        err = io.StringIO()
        with (
            patch.object(pack, "load_config", return_value=cfg),
            patch.object(pack, "connect", return_value=con),
            patch.object(pack, "_git_available", return_value=git_available),
            patch.object(pack, "_files_staged", return_value=list(staged or [])),
            patch.object(pack, "_files_changed", return_value=list(changed or [])),
            patch.object(pack, "_files_recent", recent_mock),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            rc = pack.main(argv)
        return rc, out.getvalue(), err.getvalue(), recent_mock

    def test_scope_changed_falls_back_to_recent_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
            rc, _stdout, stderr, _recent_mock = self._run_pack(
                root,
                ["--scope=changed", "--out=.vibe/context/PACK.md"],
                changed=[],
                recent=["keep.py"],
            )
            self.assertEqual(rc, 0)
            self.assertIn("scope=changed", stderr)
            self.assertIn("falling back to scope=recent", stderr)
            pack_text = (root / ".vibe" / "context" / "PACK.md").read_text(encoding="utf-8")
            self.assertIn("- Scope: `recent` (1 files)", pack_text)
            self.assertIn("`keep.py`", pack_text)

    def test_scope_staged_falls_back_to_recent_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
            rc, _stdout, stderr, _recent_mock = self._run_pack(
                root,
                ["--scope=staged", "--out=.vibe/context/PACK.md"],
                staged=[],
                recent=["keep.py"],
            )
            self.assertEqual(rc, 0)
            self.assertIn("scope=staged", stderr)
            self.assertIn("falling back to scope=recent", stderr)
            pack_text = (root / ".vibe" / "context" / "PACK.md").read_text(encoding="utf-8")
            self.assertIn("- Scope: `recent` (1 files)", pack_text)

    def test_exits_nonzero_when_scope_and_fallback_are_both_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rc, _stdout, stderr, _recent_mock = self._run_pack(
                root,
                ["--scope=changed", "--out=.vibe/context/PACK.md"],
                changed=[],
                recent=[],
            )
            self.assertEqual(rc, 2)
            self.assertIn("scope=changed", stderr)
            self.assertIn("falling back to scope=recent", stderr)
            self.assertIn("no matching files for scope", stderr)

    def test_scope_changed_keeps_behavior_when_non_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
            rc, _stdout, stderr, recent_mock = self._run_pack(
                root,
                ["--scope=changed", "--out=.vibe/context/PACK.md"],
                changed=["keep.py"],
                recent=["other.py"],
            )
            self.assertEqual(rc, 0)
            recent_mock.assert_not_called()
            self.assertNotIn("falling back to scope=recent", stderr)
            pack_text = (root / ".vibe" / "context" / "PACK.md").read_text(encoding="utf-8")
            self.assertIn("- Scope: `changed` (1 files)", pack_text)


if __name__ == "__main__":
    unittest.main()
