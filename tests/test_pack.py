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
    context_commands: dict[str, str] = field(default_factory=dict)


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


class TestPackCommandHints(unittest.TestCase):
    def _run_pack(
        self,
        root: Path,
        *,
        context_commands: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        cfg = _DummyCfg(root=root, context_commands=dict(context_commands or {}))
        con = _memory_db()
        out = io.StringIO()
        err = io.StringIO()
        with (
            patch.object(pack, "load_config", return_value=cfg),
            patch.object(pack, "connect", return_value=con),
            patch.object(pack, "_git_available", return_value=True),
            patch.object(pack, "_files_staged", return_value=["keep.py"]),
            patch.object(pack, "_files_recent", return_value=["keep.py"]),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            rc = pack.main(["--scope=staged", "--out=.vibe/context/PACK.md"])
        return rc, out.getvalue(), err.getvalue()

    def test_pack_commands_use_repo_aware_defaults_without_hardcoded_project_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
            (root / "scripts").mkdir(parents=True, exist_ok=True)
            (root / "scripts" / "vibe.py").write_text("# stub\n", encoding="utf-8")
            rc, _stdout, _stderr = self._run_pack(root)
            self.assertEqual(rc, 0)
            pack_text = (root / ".vibe" / "context" / "PACK.md").read_text(encoding="utf-8")
            self.assertIn("## Commands", pack_text)
            self.assertIn("- Doctor: `python3 scripts/vibe.py doctor --full`", pack_text)
            self.assertIn("- Search: `python3 scripts/vibe.py search <query>`", pack_text)
            self.assertIn("- Tests: `python3 -m unittest discover -s tests -p 'test*.py' -v`", pack_text)
            self.assertIn(
                "- Treat runtime placeholders/tokens as a contract (`<...>`, `{0}`, `%s`, `__TOKEN__`).",
                pack_text,
            )
            self.assertNotIn("tests/XTranslatorAi.Tests/XTranslatorAi.Tests.csproj", pack_text)
            self.assertNotIn("__XT_*__", pack_text)

    def test_pack_commands_can_be_overridden_by_context_commands_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
            rc, _stdout, _stderr = self._run_pack(
                root,
                context_commands={
                    "doctor": "make doctor",
                    "tests": "make test",
                    "search": "make search QUERY=<query>",
                },
            )
            self.assertEqual(rc, 0)
            pack_text = (root / ".vibe" / "context" / "PACK.md").read_text(encoding="utf-8")
            self.assertIn("- Doctor: `make doctor`", pack_text)
            self.assertIn("- Tests: `make test`", pack_text)
            self.assertIn("- Search: `make search QUERY=<query>`", pack_text)

    def test_pack_tests_hint_falls_back_when_tests_key_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
            (root / "package.json").write_text("{}", encoding="utf-8")
            rc, _stdout, _stderr = self._run_pack(
                root,
                context_commands={
                    "doctor": "python3 scripts/vibe.py doctor --full",
                    "search": "python3 scripts/vibe.py search <query>",
                },
            )
            self.assertEqual(rc, 0)
            pack_text = (root / ".vibe" / "context" / "PACK.md").read_text(encoding="utf-8")
            self.assertIn("- Tests: `npm test`", pack_text)

    def test_pack_tests_hint_uses_package_manager_field_without_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
            (root / "package.json").write_text(
                '{"name":"demo","version":"0.0.1","packageManager":"pnpm@9.0.0"}',
                encoding="utf-8",
            )
            rc, _stdout, _stderr = self._run_pack(
                root,
                context_commands={
                    "doctor": "python3 scripts/vibe.py doctor --full",
                    "search": "python3 scripts/vibe.py search <query>",
                },
            )
            self.assertEqual(rc, 0)
            pack_text = (root / ".vibe" / "context" / "PACK.md").read_text(encoding="utf-8")
            self.assertIn("- Tests: `pnpm test`", pack_text)

    def test_pack_tests_hint_falls_back_when_tests_key_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
            (root / "go.mod").write_text("module example.com/demo\n", encoding="utf-8")
            rc, _stdout, _stderr = self._run_pack(
                root,
                context_commands={
                    "doctor": "custom doctor",
                    "tests": "   ",
                    "search": "custom search",
                },
            )
            self.assertEqual(rc, 0)
            pack_text = (root / ".vibe" / "context" / "PACK.md").read_text(encoding="utf-8")
            self.assertIn("- Tests: `go test ./...`", pack_text)


if __name__ == "__main__":
    unittest.main()
