# Agent Notes

## Quick Start
- Read: `.vibe/AGENT_CHECKLIST.md`
- Read: `.vibe/context/LATEST_CONTEXT.md`
- Run: `python3 scripts/vibe.py doctor --full`

## Repo Rules
- Prefer small, localized changes that keep behavior stable.
- Avoid repo-wide formatting and unrelated cleanup refactors.
- Treat placeholders and tokens as runtime contracts unless the task explicitly changes them.
- When working on vibe-kit behavior, check `.vibe/reports/` outputs before and after changes when helpful.
