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
        include_globs=["**/*.py", "**/*.ts", "**/*.tsx"],
        critical_tags=["@critical", "CRITICAL:"],
        latest_file=root / ".vibe" / "context" / "LATEST_CONTEXT.md",
        max_recent_files=10,
        context_commands={},
        checks={},
        quality_gates={},
        placeholders={},
        profiling={},
        architecture={},
    )


def _memory_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    ensure_schema(con)
    return con


class TestIndexerPythonSymbols(unittest.TestCase):
    def test_indexes_python_symbols_with_docstrings_and_decorators(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "app.py"
            source.write_text(
                'def decorator(fn):\n'
                '    return fn\n'
                '\n'
                '@decorator\n'
                'def helper(value: int) -> int:\n'
                '    """@critical helper path."""\n'
                '    return value\n'
                '\n'
                'class Service:\n'
                '    """Service docs."""\n'
                '\n'
                '    def run(self, task: str) -> str:\n'
                '        """Run task."""\n'
                '        return task\n',
                encoding="utf-8",
            )

            cfg = _cfg(root)
            con = _memory_db()
            try:
                changed = indexer.index_file(source, cfg, con=con)
                self.assertTrue(changed)

                rows = con.execute(
                    "SELECT name, kind, signature, doc, tags_json, attrs_json, exported_int FROM symbols ORDER BY line"
                ).fetchall()
                names = [row["name"] for row in rows]
                self.assertIn("helper", names)
                self.assertIn("Service", names)
                self.assertIn("Service.run", names)

                helper = next(row for row in rows if row["name"] == "helper")
                self.assertEqual(helper["kind"], "function")
                self.assertIn("@critical", helper["tags_json"])
                self.assertIn("decorator", helper["attrs_json"])
                self.assertEqual(helper["exported_int"], 1)
            finally:
                con.close()


class TestIndexerTypeScriptSymbols(unittest.TestCase):
    def test_indexes_typescript_symbols_with_jsdoc(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "src" / "widget.ts"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                '/** @critical important widget */\n'
                'export function makeWidget(name: string) {\n'
                '  return name;\n'
                '}\n'
                '\n'
                '// component docs\n'
                'export const Widget = (props: {label: string}) => props.label;\n'
                '\n'
                'interface InternalShape {\n'
                '  label: string;\n'
                '}\n',
                encoding="utf-8",
            )

            cfg = _cfg(root)
            con = _memory_db()
            try:
                changed = indexer.index_file(source, cfg, con=con)
                self.assertTrue(changed)

                rows = con.execute(
                    "SELECT name, kind, doc, tags_json, exported_int FROM symbols ORDER BY line"
                ).fetchall()
                names = [row["name"] for row in rows]
                self.assertIn("makeWidget", names)
                self.assertIn("Widget", names)
                self.assertIn("InternalShape", names)

                fn = next(row for row in rows if row["name"] == "makeWidget")
                self.assertEqual(fn["kind"], "function")
                self.assertIn("@critical", fn["tags_json"])
                self.assertEqual(fn["exported_int"], 1)

                internal = next(row for row in rows if row["name"] == "InternalShape")
                self.assertEqual(internal["exported_int"], 0)
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
