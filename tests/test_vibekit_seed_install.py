from __future__ import annotations

import base64
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


if __name__ == "__main__":
    unittest.main()

