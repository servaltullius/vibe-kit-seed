from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import repo_detect  # noqa: E402


class TestRepoDetectPackageManager(unittest.TestCase):
    def test_detect_package_manager_prefers_package_manager_field(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
            package_json = {"packageManager": "yarn@4.0.0"}

            pm, source = repo_detect.detect_package_manager(root, package_json)

            self.assertEqual(pm, "yarn")
            self.assertEqual(source, "packageManager field")

    def test_detect_package_manager_uses_lockfile_when_field_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

            pm, source = repo_detect.detect_package_manager(root, None)

            self.assertEqual(pm, "pnpm")
            self.assertEqual(source, "lockfile")


class TestRepoDetectDotnetTarget(unittest.TestCase):
    def test_pick_dotnet_target_prefers_solution_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Demo.sln").write_text("Microsoft Visual Studio Solution File\n", encoding="utf-8")
            project = root / "src" / "Demo.Core.csproj"
            project.parent.mkdir(parents=True, exist_ok=True)
            project.write_text("<Project />\n", encoding="utf-8")

            target = repo_detect.pick_dotnet_target(root, exclude_dirs=[], prefer_solution=True)

            self.assertEqual(target, root / "Demo.sln")

    def test_pick_dotnet_target_prefers_project_when_solution_not_requested(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Demo.sln").write_text("Microsoft Visual Studio Solution File\n", encoding="utf-8")
            core = root / "src" / "Demo.Core.csproj"
            tests = root / "tests" / "Demo.Tests.csproj"
            core.parent.mkdir(parents=True, exist_ok=True)
            tests.parent.mkdir(parents=True, exist_ok=True)
            core.write_text("<Project />\n", encoding="utf-8")
            tests.write_text("<Project />\n", encoding="utf-8")

            target = repo_detect.pick_dotnet_target(root, exclude_dirs=[], prefer_solution=False)

            self.assertEqual(target, core)


class TestRepoDetectConfigFiles(unittest.TestCase):
    def test_has_pytest_config_reads_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts='-q'\n", encoding="utf-8")

            self.assertTrue(repo_detect.has_pytest_config(root))

    def test_has_gradle_files_detects_nested_gradle_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_file = root / "android" / "build.gradle.kts"
            build_file.parent.mkdir(parents=True, exist_ok=True)
            build_file.write_text("plugins {}\n", encoding="utf-8")

            self.assertTrue(repo_detect.has_gradle_files(root, exclude_dirs=[]))


if __name__ == "__main__":
    unittest.main()
