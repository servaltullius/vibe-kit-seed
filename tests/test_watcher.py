from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import watcher  # noqa: E402


@dataclass
class _DummyCfg:
    root: Path
    exclude_dirs: list[str] = field(default_factory=list)
    include_globs: list[str] = field(default_factory=list)


class TestWatcherShouldTrack(unittest.TestCase):
    def test_should_track_uses_include_globs_instead_of_fixed_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            py_file = root / "src" / "main.py"
            root_md = root / "README.md"
            txt_file = root / "notes.txt"
            py_file.parent.mkdir(parents=True, exist_ok=True)
            py_file.write_text("print('ok')\n", encoding="utf-8")
            root_md.write_text("# demo\n", encoding="utf-8")
            txt_file.write_text("skip\n", encoding="utf-8")

            cfg = _DummyCfg(root=root, include_globs=["**/*.py", "**/*.md"])

            self.assertTrue(watcher._should_track(py_file, cfg))
            self.assertTrue(watcher._should_track(root_md, cfg))
            self.assertFalse(watcher._should_track(txt_file, cfg))

    def test_should_track_respects_exclude_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ignored = root / "node_modules" / "lib.js"
            ignored.parent.mkdir(parents=True, exist_ok=True)
            ignored.write_text("export {};\n", encoding="utf-8")

            cfg = _DummyCfg(root=root, exclude_dirs=["node_modules"], include_globs=["**/*.js"])

            self.assertFalse(watcher._should_track(ignored, cfg))

    def test_should_track_matches_indexer_glob_semantics_for_single_star(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "src" / "nested" / "file.ts"
            nested.parent.mkdir(parents=True, exist_ok=True)
            nested.write_text("export const x = 1;\n", encoding="utf-8")

            cfg = _DummyCfg(root=root, include_globs=["src/*.ts"])

            self.assertFalse(watcher._should_track(nested, cfg))


class TestWatcherPollingDiff(unittest.TestCase):
    def test_diff_tracked_files_reports_changed_and_deleted(self) -> None:
        previous = {
            Path("/repo/a.py"): 1.0,
            Path("/repo/b.py"): 2.0,
        }
        current = {
            Path("/repo/a.py"): 3.0,
            Path("/repo/c.py"): 1.0,
        }

        changed, has_deleted = watcher._diff_tracked_files(previous, current)

        self.assertEqual(changed, [Path("/repo/a.py"), Path("/repo/c.py")])
        self.assertTrue(has_deleted)

    def test_classify_tracked_files_separates_modified_and_created(self) -> None:
        previous = {
            Path("/repo/a.py"): 1.0,
            Path("/repo/b.py"): 2.0,
        }
        current = {
            Path("/repo/a.py"): 3.0,
            Path("/repo/c.py"): 1.0,
        }

        modified, created, has_deleted = watcher._classify_tracked_files(previous, current)

        self.assertEqual(modified, [Path("/repo/a.py")])
        self.assertEqual(created, [Path("/repo/c.py")])
        self.assertTrue(has_deleted)

    def test_reconcile_tracked_files_detects_new_modified_and_deleted_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            existing = root / "src" / "keep.py"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("x = 1\n", encoding="utf-8")

            cfg = _DummyCfg(root=root, include_globs=["**/*.py"])
            tracked = watcher._collect_tracked_files(cfg)

            original_mtime = existing.stat().st_mtime
            existing.write_text("x = 2\n", encoding="utf-8")
            os.utime(existing, (original_mtime + 5, original_mtime + 5))

            created_file = root / "src" / "new.py"
            created_file.write_text("y = 1\n", encoding="utf-8")
            os.utime(created_file, (original_mtime + 10, original_mtime + 10))

            deleted = root / "src" / "old.py"
            deleted.write_text("z = 1\n", encoding="utf-8")
            tracked[deleted] = original_mtime
            deleted.unlink()

            current, modified, created, has_deleted = watcher._reconcile_tracked_files(cfg, tracked)

            self.assertIn(existing, current)
            self.assertIn(created_file, current)
            self.assertIn(existing, modified)
            self.assertIn(created_file, created)
            self.assertTrue(has_deleted)


if __name__ == "__main__":
    unittest.main()
