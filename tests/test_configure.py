from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
