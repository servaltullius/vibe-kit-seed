from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import configure as vibe_configure  # noqa: E402


class TestConfigureTypecheckRecommendation(unittest.TestCase):
    def test_node_typecheck_uses_detected_package_manager(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "demo",
                        "version": "0.0.1",
                        "packageManager": "pnpm@9.0.0",
                        "scripts": {"typecheck": "tsc --noEmit"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "tsconfig.json").write_text("{}\n", encoding="utf-8")

            package_json = json.loads((root / "package.json").read_text(encoding="utf-8"))
            pm, _ = vibe_configure._detect_package_manager(root, package_json)
            cmd, when_globs, _meta = vibe_configure._pick_typecheck_recommendation(
                root=root,
                exclude_dirs=set(),
                package_json=package_json,
                pm=pm,
            )

            self.assertEqual(cmd, ["pnpm", "run", "typecheck"])
            self.assertEqual(when_globs, ["**/*.ts", "**/*.tsx"])

    def test_dotnet_project_recommendation_is_generated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Demo.sln").write_text("Microsoft Visual Studio Solution File\n", encoding="utf-8")
            cmd, when_globs, meta = vibe_configure._pick_typecheck_recommendation(
                root=root,
                exclude_dirs=set(),
                package_json=None,
                pm=None,
            )

            self.assertIsNotNone(cmd)
            assert cmd is not None
            self.assertEqual(cmd[0], "dotnet")
            self.assertEqual(cmd[1], "build")
            self.assertEqual(cmd[2], "Demo.sln")
            self.assertIn("**/*.sln", when_globs or [])
            self.assertTrue(meta.get("dotnet_present"))

    def test_maven_recommendation_is_generated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
            cmd, when_globs, meta = vibe_configure._pick_typecheck_recommendation(
                root=root,
                exclude_dirs=set(),
                package_json=None,
                pm=None,
            )

            self.assertEqual(cmd, ["mvn", "-q", "-DskipTests", "compile"])
            self.assertIn("pom.xml", when_globs or [])
            self.assertTrue(meta.get("maven_present"))

    def test_gradle_recommendation_prefers_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
            cmd, when_globs, meta = vibe_configure._pick_typecheck_recommendation(
                root=root,
                exclude_dirs=set(),
                package_json=None,
                pm=None,
            )

            self.assertEqual(cmd, ["./gradlew", "-q", "classes"])
            self.assertIn("build.gradle.kts", when_globs or [])
            self.assertTrue(meta.get("gradle_present"))
            self.assertTrue(meta.get("gradle_has_wrapper"))

    def test_pyright_recommendation_is_generated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pyproject.toml").write_text("[tool.pyright]\npythonVersion='3.11'\n", encoding="utf-8")
            cmd, when_globs, meta = vibe_configure._pick_typecheck_recommendation(
                root=root,
                exclude_dirs=set(),
                package_json=None,
                pm=None,
            )

            self.assertEqual(cmd, ["pyright"])
            self.assertIn("pyproject.toml", when_globs or [])
            self.assertTrue(meta.get("pyright_present"))

    def test_main_reports_polyglot_detected_stacks_and_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".vibe").mkdir(parents=True, exist_ok=True)
            (root / ".vibe" / "config.json").write_text(
                json.dumps(
                    {
                        "project_name": "demo",
                        "exclude_dirs": [],
                        "include_globs": ["**/*.py", "**/*.ts", "**/*.go"],
                        "quality_gates": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "demo",
                        "packageManager": "pnpm@9.0.0",
                        "scripts": {"typecheck": "tsc --noEmit"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "tsconfig.json").write_text("{}\n", encoding="utf-8")
            (root / "go.mod").write_text("module demo\n", encoding="utf-8")

            out = io.StringIO()
            with redirect_stdout(out), patch.object(vibe_configure, "_repo_root", return_value=root):
                rc = vibe_configure.main(["--apply"])

            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("[configure] detected stacks: node/pnpm, go", text)
            self.assertIn("polyglot/monorepo signals found", text)
            self.assertIn("recommended typecheck: pnpm run typecheck", text)
            self.assertIn("next: Run `python3 scripts/vibe.py doctor --full`", text)

    def test_main_reports_monorepo_hints(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".vibe").mkdir(parents=True, exist_ok=True)
            (root / ".vibe" / "config.json").write_text(
                json.dumps(
                    {
                        "project_name": "demo",
                        "exclude_dirs": [],
                        "include_globs": ["**/*.py", "**/*.ts"],
                        "quality_gates": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "pnpm-workspace.yaml").write_text("packages:\n  - apps/*\n", encoding="utf-8")
            (root / "package.json").write_text(
                json.dumps({"name": "root", "packageManager": "pnpm@9.0.0", "scripts": {"typecheck": "tsc --noEmit"}}) + "\n",
                encoding="utf-8",
            )
            (root / "apps" / "web").mkdir(parents=True, exist_ok=True)
            (root / "apps" / "web" / "package.json").write_text(json.dumps({"name": "web"}) + "\n", encoding="utf-8")
            (root / "tsconfig.json").write_text("{}\n", encoding="utf-8")

            out = io.StringIO()
            with redirect_stdout(out), patch.object(vibe_configure, "_repo_root", return_value=root):
                rc = vibe_configure.main([])

            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("[configure] monorepo hints:", text)
            self.assertIn("pnpm-workspace", text)
            self.assertIn("multiple-package-json(2)", text)

    def test_count_named_files_uses_repo_walk_helper(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files = [
                root / "package.json",
                root / "apps" / "web" / "package.json",
                root / "node_modules" / "left-pad" / "package.json",
            ]

            with patch.object(vibe_configure, "walk_repo_files", return_value=iter(files)) as mocked_walk:
                count = vibe_configure._count_named_files(root, {"node_modules"}, {"package.json"})

            self.assertEqual(count, 3)
            mocked_walk.assert_called_once_with(root, {"node_modules"})


if __name__ == "__main__":
    unittest.main()
