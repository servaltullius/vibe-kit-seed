import contextlib
import io
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import check_boundaries as cb  # noqa: E402


class _DummyCfg:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.exclude_dirs: list[str] = []
        self.include_globs: list[str] = ["**/*.py", "**/*.ts", "**/*.js"]
        self.architecture: dict = {"python_roots": ["src", "."], "js_aliases": {}}
        self.quality_gates: dict = {}


class TestBoundaries(unittest.TestCase):
    def test_rule_match_respects_kinds(self) -> None:
        rule = cb.Rule(
            name="no_domain_to_infra",
            from_globs=["src/domain/**"],
            to_globs=["src/infra/**"],
            kinds={"py_import"},
            reason="domain must not depend on infra",
        )
        dep_ok = cb.Dep(from_file="src/domain/a.py", to_file="src/infra/b.py", kind="py_import")
        dep_wrong_kind = cb.Dep(from_file="src/domain/a.ts", to_file="src/infra/b.ts", kind="js_import")
        self.assertTrue(cb._rule_match(rule, dep_ok))
        self.assertFalse(cb._rule_match(rule, dep_wrong_kind))

    def test_python_import_resolves_to_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src" / "domain").mkdir(parents=True, exist_ok=True)
            (root / "src" / "infra").mkdir(parents=True, exist_ok=True)
            (root / "src" / "domain" / "a.py").write_text("import infra.b\n", encoding="utf-8")
            (root / "src" / "infra" / "b.py").write_text("x = 1\n", encoding="utf-8")

            cfg = _DummyCfg(root)
            py_files = ["src/domain/a.py", "src/infra/b.py"]
            module_to_file = cb._build_python_module_index(cfg, py_files)

            deps = list(
                cb._python_deps_for_file(
                    cfg,
                    from_rel="src/domain/a.py",
                    text=(root / "src" / "domain" / "a.py").read_text(encoding="utf-8"),
                    module_to_file=module_to_file,
                )
            )
            self.assertTrue(any(d.to_file == "src/infra/b.py" and d.kind == "py_import" for d in deps))

    def test_js_relative_import_resolves_to_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src" / "ui").mkdir(parents=True, exist_ok=True)
            (root / "src" / "infra").mkdir(parents=True, exist_ok=True)
            (root / "src" / "infra" / "b.ts").write_text("export const x = 1;\n", encoding="utf-8")
            a = root / "src" / "ui" / "a.ts"
            a.write_text("import { x } from '../infra/b'\n", encoding="utf-8")

            cfg = _DummyCfg(root)
            deps = list(cb._js_deps_for_file(cfg, from_rel="src/ui/a.ts", text=a.read_text(encoding="utf-8"), aliases={}))
            self.assertTrue(any(d.to_file == "src/infra/b.ts" and d.kind == "js_import" for d in deps))

    def test_strict_mode_returns_nonzero_even_with_best_effort(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src" / "domain").mkdir(parents=True, exist_ok=True)
            (root / "src" / "infra").mkdir(parents=True, exist_ok=True)
            (root / "src" / "domain" / "a.py").write_text("import infra.b\n", encoding="utf-8")
            (root / "src" / "infra" / "b.py").write_text("x = 1\n", encoding="utf-8")

            cfg = _DummyCfg(root)
            cfg.architecture = {
                "enabled": True,
                "python_roots": ["src", "."],
                "js_aliases": {},
                "rules": [
                    {
                        "name": "no_domain_to_infra",
                        "from_globs": ["src/domain/**"],
                        "to_globs": ["src/infra/**"],
                        "kinds": ["py_import", "py_from"],
                        "reason": "domain must not depend on infra",
                    }
                ],
            }
            cfg.quality_gates = {"boundary_block": False}

            files = ["src/domain/a.py", "src/infra/b.py"]

            def _fake_connect() -> sqlite3.Connection:
                con = sqlite3.connect(":memory:")
                con.row_factory = sqlite3.Row
                con.execute("CREATE TABLE files (path TEXT)")
                con.execute("CREATE TABLE deps (from_file TEXT, to_file TEXT, kind TEXT)")
                con.executemany("INSERT INTO files(path) VALUES (?)", ((p,) for p in files))
                return con

            out = root / "boundaries.json"
            md_out = root / "boundaries.md"

            with mock.patch.object(cb, "load_config", return_value=cfg), mock.patch.object(cb, "connect", side_effect=_fake_connect):
                rc_best_effort = cb.main(["--out", str(out), "--md-out", str(md_out), "--best-effort"])
                rc_strict = cb.main(["--out", str(out), "--md-out", str(md_out), "--best-effort", "--strict"])

            self.assertEqual(rc_best_effort, 0)
            self.assertEqual(rc_strict, 1)

    def test_help_documents_strict_precedence_over_best_effort(self) -> None:
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(stdout):
            cb.main(["--help"])

        self.assertEqual(cm.exception.code, 0)
        normalized_help = " ".join(stdout.getvalue().split())
        self.assertIn("ignored when --strict is set", normalized_help)


if __name__ == "__main__":
    unittest.main()
