from __future__ import annotations


DEFAULT_CONTEXT_HINT = ".vibe/AGENT_CHECKLIST.md"
FALLBACK_CONTEXT_HINT = ".vibe/context/LATEST_CONTEXT.md"
DEFAULT_CONFIGURE_COMMAND = "python3 scripts/vibe.py configure --apply"
DEFAULT_DOCTOR_COMMAND = "python3 scripts/vibe.py doctor --full"
WINDOWS_DOCTOR_COMMAND = "scripts\\vibe.cmd doctor --full"


def required_context_hints() -> list[str]:
    return [DEFAULT_CONTEXT_HINT, FALLBACK_CONTEXT_HINT]


def required_doctor_hints() -> list[str]:
    return [DEFAULT_DOCTOR_COMMAND, WINDOWS_DOCTOR_COMMAND]


def render_agent_checklist() -> str:
    return """# AGENT_CHECKLIST (vibe-kit)

## Quick start (do this first)
- Install success loop:
  - `python3 scripts/vibe.py configure --apply`
  - `python3 scripts/vibe.py doctor --full`
  - `python3 scripts/vibe.py agents doctor --fail`
- Read: `.vibe/context/LATEST_CONTEXT.md`
- (Recommended once, after install) Auto-configure for this repo: `python3 scripts/vibe.py configure --apply`
- If you run only one command:
  - (WSL/Linux) `python3 scripts/vibe.py doctor --full`
  - (Windows) `scripts\\vibe.cmd doctor --full`

## Before coding
- Read: `.vibe/agent_memory/DONT_DO_THIS.md`
- Check impact for shared/core files: `python3 scripts/vibe.py impact <path>`
- Find entry points fast:
  - `python3 scripts/vibe.py search "<keyword>"`
- (Optional) Detect boundary violations (architecture rules): `python3 scripts/vibe.py boundaries`
- (Optional) Find logical coupling from git history: `python3 scripts/vibe.py coupling`
  - Useful options: `--detect-renames`, `--max-churn-per-commit 5000`
  - Decoupling playbooks: `.vibe/reports/decoupling_suggestions.md`
- (Optional) Configure repo-specific checks in `.vibe/config.json` (`checks.doctor`, `checks.precommit`).
- (Optional) Make a compact context pack for an agent:
  - `python3 scripts/vibe.py pack --scope=staged|changed|path|recent --out .vibe/context/PACK.md`
- (Optional) Validate agent entrypoints are wired:
  - `python3 scripts/vibe.py agents doctor`
  - CI/strict mode: `python3 scripts/vibe.py agents doctor --fail`

## While coding
- Keep changes small and localized.
- Treat placeholders/tokens as runtime contracts (e.g. `<...>`, `{0}`, `%s`) and update tests if you change them.

## Before finishing
- Run: `python3 scripts/vibe.py doctor --full` (or at least `python3 scripts/vibe.py doctor`)
- Run the repo's normal tests/lint (e.g. `pytest`, `npm test`, `dotnet test`, etc.)
"""


def render_agent_template(agent: str) -> tuple[str, str]:
    agent_key = agent.lower().strip()
    shared = (
        "## Quick start\n"
        f"- Read: `{DEFAULT_CONTEXT_HINT}`\n"
        f"- Read: `{FALLBACK_CONTEXT_HINT}`\n"
        f"- (Once) Run: `{DEFAULT_CONFIGURE_COMMAND}`\n"
        f"- Run: `{DEFAULT_DOCTOR_COMMAND}`\n"
    )
    repo_rules = (
        "\n## Repo rules\n"
        "- Avoid repo-wide formatting and unrelated cleanup refactors.\n"
        "- Treat placeholders/tokens as runtime contracts (e.g. `<...>`, `{0}`, `%s`).\n"
        "- Prefer small, localized edits; keep behavior stable.\n"
    )
    templates: dict[str, tuple[str, str]] = {
        "codex": (
            "AGENTS.md",
            "# Agent Notes\n\n"
            + shared
            + repo_rules,
        ),
        "claude": (
            "CLAUDE.md",
            "# Project Instructions\n\n"
            + shared
            + repo_rules,
        ),
        "copilot": (
            ".github/copilot-instructions.md",
            "# Copilot Instructions\n\n"
            + shared
            + repo_rules,
        ),
        "cursor": (
            ".cursor/rules/vibekit.md",
            "# Cursor Rules (vibe-kit)\n\n"
            + shared
            + repo_rules,
        ),
        "gemini": (
            "GEMINI.md",
            "# Gemini Instructions\n\n"
            + shared
            + repo_rules,
        ),
    }
    if agent_key not in templates:
        raise KeyError(agent_key)
    return templates[agent_key]


def render_agents_doctor_remediation(rel_path: str) -> str:
    return (
        f"[agents-doctor] FIX: {rel_path} add these lines:\n"
        f"  - Read: `{DEFAULT_CONTEXT_HINT}`\n"
        f"  - Run: `{DEFAULT_DOCTOR_COMMAND}`\n"
        "  Example:\n"
        f"    - Read: `{DEFAULT_CONTEXT_HINT}`\n"
        f"    - Run: `{DEFAULT_DOCTOR_COMMAND}`"
    )
