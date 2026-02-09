import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def _load_vibe_module():
    spec = importlib.util.spec_from_file_location("vibe_cli_under_test", ROOT / "scripts" / "vibe.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load scripts/vibe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_config(root: Path, *, rules: list[dict]) -> None:
    cfg = {
        "project_name": "tmp",
        "root": ".",
        "exclude_dirs": [],
        "include_globs": ["**/*.py", "**/*.ts", "**/*.js"],
        "critical_tags": ["@critical", "CRITICAL:"],
        "context": {"latest_file": ".vibe/context/LATEST_CONTEXT.md", "max_recent_files": 12, "commands": {}},
        "checks": {"doctor": [], "precommit": []},
        "quality_gates": {"boundary_block": False},
        "architecture": {"enabled": True, "rules": rules, "python_roots": ["src", "."], "js_aliases": {}},
    }
    vibe_dir = root / ".vibe"
    vibe_dir.mkdir(parents=True, exist_ok=True)
    (vibe_dir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TestVibeBoundariesCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vibe = _load_vibe_module()

    def test_boundaries_init_template_populates_rules_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_config(root, rules=[])

            with mock.patch.object(self.vibe, "_repo_root", return_value=root), mock.patch.object(self.vibe, "_run", return_value=0):
                rc1 = self.vibe.main(["boundaries", "--init-template"])
                first = json.loads((root / ".vibe" / "config.json").read_text(encoding="utf-8"))
                rc2 = self.vibe.main(["boundaries", "--init-template"])
                second = json.loads((root / ".vibe" / "config.json").read_text(encoding="utf-8"))

            self.assertEqual(rc1, 0)
            self.assertEqual(rc2, 0)
            self.assertTrue(first["architecture"]["rules"])
            self.assertEqual(first["architecture"]["rules"], second["architecture"]["rules"])

    def test_boundaries_strict_flag_is_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_config(root, rules=[])

            with mock.patch.object(self.vibe, "_repo_root", return_value=root), mock.patch.object(self.vibe, "_run", return_value=0) as run_mock:
                rc = self.vibe.main(["boundaries", "--strict"])

            self.assertEqual(rc, 0)
            self.assertTrue(run_mock.called)
            forwarded_args = run_mock.call_args[0][1]
            self.assertIn("--strict", forwarded_args)

    def test_agents_doctor_flag_is_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_config(root, rules=[])

            with mock.patch.object(self.vibe, "_repo_root", return_value=root), mock.patch.object(self.vibe, "_run", return_value=0) as run_mock:
                rc = self.vibe.main(["agents", "doctor", "--fail"])

            self.assertEqual(rc, 0)
            self.assertTrue(run_mock.called)
            called_script = run_mock.call_args[0][0]
            forwarded_args = run_mock.call_args[0][1]
            self.assertTrue(str(called_script).endswith("agents_doctor.py"))
            self.assertIn("--fail", forwarded_args)


if __name__ == "__main__":
    unittest.main()
