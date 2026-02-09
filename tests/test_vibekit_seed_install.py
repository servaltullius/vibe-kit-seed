from __future__ import annotations

import base64
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import vibekit_seed_install as vsi


def _make_seed_file(path: Path, zip_members: dict[str, bytes]) -> None:
    buf = io.BytesIO()
    with ZipFile(buf, "w", compression=ZIP_DEFLATED) as z:
        for name, data in zip_members.items():
            z.writestr(name, data)

    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    path.write_text(
        "\n".join(
            [
                "# seed",
                "",
                "<!-- VIBEKIT_PAYLOAD_BASE64_BEGIN -->",
                b64,
                "<!-- VIBEKIT_PAYLOAD_BASE64_END -->",
                "",
            ]
        ),
        encoding="utf-8",
    )


class TestNormalizeMemberName(unittest.TestCase):
    def test_rejects_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            vsi._normalize_member_name("../pwn")
        with self.assertRaises(ValueError):
            vsi._normalize_member_name("a/../b")
        with self.assertRaises(ValueError):
            vsi._normalize_member_name("./a")

    def test_rejects_absolute_and_windows_drive(self) -> None:
        with self.assertRaises(ValueError):
            vsi._normalize_member_name("/etc/passwd")
        with self.assertRaises(ValueError):
            vsi._normalize_member_name("C:evil.txt")

    def test_rejects_backslashes(self) -> None:
        with self.assertRaises(ValueError):
            vsi._normalize_member_name("a\\b.txt")


class TestAllowlist(unittest.TestCase):
    def test_allows_expected_paths(self) -> None:
        self.assertTrue(vsi._is_allowed("scripts/vibe.py"))
        self.assertTrue(vsi._is_allowed(".vibe/brain/indexer.py"))

    def test_rejects_unexpected_paths(self) -> None:
        self.assertFalse(vsi._is_allowed("README.md"))
        self.assertFalse(vsi._is_allowed(".vibe/config.json"))
        self.assertFalse(vsi._is_allowed(".git/hooks/pre-commit"))


class TestInstaller(unittest.TestCase):
    def test_sha_mismatch_fails_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            seed = td_path / "VIBEKIT_SEED.md"
            root = td_path / "target"
            _make_seed_file(seed, {"scripts/vibe.py": b"print('ok')\n"})

            rc = vsi._install(
                seed_md=seed,
                root=root,
                expected_seed_sha256="0" * 64,
                force=False,
                apply=True,
                agent=None,
                run_setup=False,
            )
            self.assertEqual(rc, 2)
            self.assertFalse((root / "scripts" / "vibe.py").exists())

    def test_zip_path_traversal_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            seed = td_path / "VIBEKIT_SEED.md"
            root = td_path / "target"
            _make_seed_file(seed, {"../pwn.txt": b"nope"})
            expected = vsi._sha256_file(seed)

            rc = vsi._install(
                seed_md=seed,
                root=root,
                expected_seed_sha256=expected,
                force=False,
                apply=True,
                agent=None,
                run_setup=False,
            )
            self.assertEqual(rc, 2)
            self.assertFalse((root / "pwn.txt").exists())

    def test_unknown_paths_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            seed = td_path / "VIBEKIT_SEED.md"
            root = td_path / "target"
            _make_seed_file(seed, {"evil.txt": b"nope"})
            expected = vsi._sha256_file(seed)

            rc = vsi._install(
                seed_md=seed,
                root=root,
                expected_seed_sha256=expected,
                force=False,
                apply=True,
                agent=None,
                run_setup=False,
            )
            self.assertEqual(rc, 2)

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            seed = td_path / "VIBEKIT_SEED.md"
            root = td_path / "target"
            _make_seed_file(seed, {"scripts/vibe.py": b"print('ok')\n"})
            expected = vsi._sha256_file(seed)

            rc = vsi._install(
                seed_md=seed,
                root=root,
                expected_seed_sha256=expected,
                force=False,
                apply=False,
                agent=None,
                run_setup=False,
            )
            self.assertEqual(rc, 0)
            self.assertFalse((root / "scripts" / "vibe.py").exists())

    def test_apply_writes_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            seed = td_path / "VIBEKIT_SEED.md"
            root = td_path / "target"
            _make_seed_file(seed, {"scripts/vibe.py": b"print('ok')\n"})
            expected = vsi._sha256_file(seed)

            rc = vsi._install(
                seed_md=seed,
                root=root,
                expected_seed_sha256=expected,
                force=False,
                apply=True,
                agent=None,
                run_setup=False,
            )
            self.assertEqual(rc, 0)
            self.assertEqual((root / "scripts" / "vibe.py").read_text(encoding="utf-8"), "print('ok')\n")

    def test_agent_all_writes_all_agent_instruction_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            seed = td_path / "VIBEKIT_SEED.md"
            root = td_path / "target"
            _make_seed_file(seed, {"scripts/vibe.py": b"print('ok')\n"})
            expected = vsi._sha256_file(seed)

            rc = vsi._install(
                seed_md=seed,
                root=root,
                expected_seed_sha256=expected,
                force=False,
                apply=True,
                agent="all",
                run_setup=False,
            )
            self.assertEqual(rc, 0)
            self.assertTrue((root / "AGENTS.md").exists())
            self.assertTrue((root / "CLAUDE.md").exists())
            self.assertTrue((root / "GEMINI.md").exists())
            self.assertTrue((root / ".github" / "copilot-instructions.md").exists())
            self.assertTrue((root / ".cursor" / "rules" / "vibekit.md").exists())


class TestBootstrapHelpers(unittest.TestCase):
    def test_parse_sha256sums_parses_expected_format(self) -> None:
        content = (
            "a" * 64
            + "  VIBEKIT_SEED-1.2.2-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md\n"
            + "b" * 64
            + "  vibekit_seed_install.py\n"
        )
        parsed = vsi._parse_sha256sums(content)
        self.assertIn("vibekit_seed_install.py", parsed)
        self.assertEqual(parsed["vibekit_seed_install.py"], "b" * 64)

    def test_parse_sha256sums_rejects_invalid_line(self) -> None:
        with self.assertRaises(ValueError):
            vsi._parse_sha256sums("not-a-valid-line\n")

    def test_resolve_release_assets_returns_seed_and_expected_sha(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            seed = base / "VIBEKIT_SEED-1.2.2-sample.md"
            installer = base / "vibekit_seed_install.py"
            seed.write_text("seed", encoding="utf-8")
            installer.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            seed_sha = hashlib.sha256(seed.read_bytes()).hexdigest()
            installer_sha = hashlib.sha256(installer.read_bytes()).hexdigest()
            (base / "SHA256SUMS").write_text(
                f"{seed_sha}  {seed.name}\n{installer_sha}  vibekit_seed_install.py\n",
                encoding="utf-8",
            )

            assets = vsi._resolve_release_assets(base)
            self.assertEqual(assets.seed_md, seed)
            self.assertEqual(assets.seed_sha256, seed_sha)
            self.assertEqual(assets.installer_path, installer)

    def test_global_hook_script_uses_marker_and_bootstrap(self) -> None:
        script = vsi._build_global_post_checkout_hook_script(
            python_executable="/usr/bin/python3",
            installer_script="/opt/vibekit_seed_install.py",
            release_repo="servaltullius/vibe-kit-seed",
            release_tag=None,
            marker_file=".vibekit.auto",
            agent="codex",
        )
        self.assertIn(".vibekit.auto", script)
        self.assertIn("bootstrap", script)
        self.assertIn("--repo", script)
        self.assertIn("servaltullius/vibe-kit-seed", script)
        self.assertIn("--post-configure", script)
        self.assertIn("--post-doctor", script)
        self.assertIn("--write-ci-guard", script)

    def test_ci_guard_workflow_includes_agents_doctor_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            written = vsi._write_ci_guard_workflow(root, force=False, apply=True)
            self.assertTrue(written)
            wf = root / ".github" / "workflows" / "vibekit-guard.yml"
            self.assertTrue(wf.exists())
            content = wf.read_text(encoding="utf-8")
            self.assertIn("python3 scripts/vibe.py doctor --full", content)
            self.assertIn("python3 scripts/vibe.py agents doctor --fail", content)

    def test_build_global_codex_prompt_block_contains_install_question_and_actions(self) -> None:
        block = vsi._build_global_codex_vibekit_prompt_block(
            installer_script="/opt/vibekit_seed_install.py",
            release_repo="servaltullius/vibe-kit-seed",
            release_tag="v1.2.3",
            marker_file=".vibekit.auto",
            suppress_file=".vibekit.ignore",
        )
        self.assertIn("이 프로젝트에 vibe-kit이 없습니다. 지금 설치할까요? (yes/no)", block)
        self.assertIn("python3 /opt/vibekit_seed_install.py bootstrap", block)
        self.assertIn("--repo servaltullius/vibe-kit-seed", block)
        self.assertIn("--tag v1.2.3", block)
        self.assertIn("Create `.vibekit.auto`", block)
        self.assertIn("Create `.vibekit.ignore`", block)

    def test_install_codex_prompt_prefers_override_when_non_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "AGENTS.override.md").write_text("# override\n", encoding="utf-8")
            (home / "AGENTS.md").write_text("# base\n", encoding="utf-8")

            changed, target = vsi._install_codex_global_prompt(
                codex_home=home,
                installer_script="/opt/vibekit_seed_install.py",
                release_repo="servaltullius/vibe-kit-seed",
                release_tag="v1.2.3",
                marker_file=".vibekit.auto",
                suppress_file=".vibekit.ignore",
                force=False,
            )

            self.assertTrue(changed)
            self.assertEqual(target, home / "AGENTS.override.md")
            txt = (home / "AGENTS.override.md").read_text(encoding="utf-8")
            self.assertIn("Vibe-kit Auto-Prompt (Missing in Repo)", txt)

    def test_install_codex_prompt_falls_back_to_agents_when_override_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "AGENTS.override.md").write_text("\n", encoding="utf-8")
            (home / "AGENTS.md").write_text("# base\n", encoding="utf-8")

            changed, target = vsi._install_codex_global_prompt(
                codex_home=home,
                installer_script="/opt/vibekit_seed_install.py",
                release_repo="servaltullius/vibe-kit-seed",
                release_tag="v1.2.3",
                marker_file=".vibekit.auto",
                suppress_file=".vibekit.ignore",
                force=False,
            )

            self.assertTrue(changed)
            self.assertEqual(target, home / "AGENTS.md")
            txt = (home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Vibe-kit Auto-Prompt (Missing in Repo)", txt)

    def test_install_codex_prompt_is_idempotent_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "AGENTS.md").write_text("# base\n", encoding="utf-8")

            changed1, target1 = vsi._install_codex_global_prompt(
                codex_home=home,
                installer_script="/opt/vibekit_seed_install.py",
                release_repo="servaltullius/vibe-kit-seed",
                release_tag="v1.2.3",
                marker_file=".vibekit.auto",
                suppress_file=".vibekit.ignore",
                force=False,
            )
            changed2, target2 = vsi._install_codex_global_prompt(
                codex_home=home,
                installer_script="/opt/vibekit_seed_install.py",
                release_repo="servaltullius/vibe-kit-seed",
                release_tag="v1.2.3",
                marker_file=".vibekit.auto",
                suppress_file=".vibekit.ignore",
                force=False,
            )

            self.assertTrue(changed1)
            self.assertFalse(changed2)
            self.assertEqual(target1, target2)
            txt = (home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(txt.count("Vibe-kit Auto-Prompt (Missing in Repo)"), 1)

    def test_install_codex_prompt_force_replaces_legacy_block_without_markers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            legacy = (
                "# base\n\n"
                "## Vibe-kit Auto-Prompt (Missing in Repo)\n"
                "- legacy text\n\n"
                "## Another Section\n"
                "- keep me\n"
            )
            (home / "AGENTS.md").write_text(legacy, encoding="utf-8")

            changed, target = vsi._install_codex_global_prompt(
                codex_home=home,
                installer_script="/opt/vibekit_seed_install.py",
                release_repo="servaltullius/vibe-kit-seed",
                release_tag="v1.2.3",
                marker_file=".vibekit.auto",
                suppress_file=".vibekit.ignore",
                force=True,
            )

            self.assertTrue(changed)
            self.assertEqual(target, home / "AGENTS.md")
            txt = (home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(txt.count("Vibe-kit Auto-Prompt (Missing in Repo)"), 1)
            self.assertIn("<!-- vibekit:auto-prompt:start -->", txt)
            self.assertIn("## Another Section", txt)


if __name__ == "__main__":
    unittest.main()
