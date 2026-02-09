from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import agents_doctor  # noqa: E402


@dataclass
class _DummyCfg:
    root: Path
    exclude_dirs: list[str] = field(default_factory=list)


class TestAgentsDoctor(unittest.TestCase):
    def test_passes_when_agents_file_contains_required_vibe_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "AGENTS.md").write_text(
                "# Agent Notes\n\n"
                "- Read: `.vibe/AGENT_CHECKLIST.md`\n"
                "- Run: `python3 scripts/vibe.py doctor --full`\n",
                encoding="utf-8",
            )
            out = io.StringIO()
            with patch.object(agents_doctor, "load_config", return_value=_DummyCfg(root=root)), redirect_stdout(out):
                rc = agents_doctor.main([])

            self.assertEqual(rc, 0)
            self.assertIn("[agents-doctor] OK", out.getvalue())

    def test_fails_with_flag_when_required_vibe_entrypoint_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "AGENTS.md").write_text("# Agent Notes\n\n- Keep changes small.\n", encoding="utf-8")
            out = io.StringIO()
            with patch.object(agents_doctor, "load_config", return_value=_DummyCfg(root=root)), redirect_stdout(out):
                rc = agents_doctor.main(["--fail"])

            self.assertEqual(rc, 1)
            self.assertIn("[agents-doctor] WARN", out.getvalue())
            self.assertIn("python3 scripts/vibe.py doctor --full", out.getvalue())


if __name__ == "__main__":
    unittest.main()
