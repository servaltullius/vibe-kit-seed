from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vibe as vibe_cli  # noqa: E402


class TestSeedMarkdownTemplate(unittest.TestCase):
    def test_seed_template_clarifies_filename_and_hash_usage(self) -> None:
        md = vibe_cli._seed_render_markdown(b"payload-bytes", ["scripts/vibe.py"])

        self.assertIn("VIBEKIT_SEED-<version>-<sha256>.md", md)
        self.assertIn("<seed-file>", md)
        self.assertIn("<seed-file-sha256>", md)
        self.assertIn("not for `--expected-seed-sha256`", md)
        self.assertIn("from `SHA256SUMS`", md)

        self.assertIn("Agent-safe sharing (important)", md)
        self.assertIn("VIBEKIT_PAYLOAD_BASE64_BEGIN/END", md)

        self.assertNotIn("install VIBEKIT_SEED.md", md)
        self.assertNotIn("Get-FileHash .\\VIBEKIT_SEED.md", md)


if __name__ == "__main__":
    unittest.main()
