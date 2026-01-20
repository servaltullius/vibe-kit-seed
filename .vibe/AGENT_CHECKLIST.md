# AGENT_CHECKLIST (vibe-kit)

## Quick start (do this first)
- Read: `.vibe/context/LATEST_CONTEXT.md`
- If you run only one command:
  - (WSL/Linux) `python3 scripts/vibe.py doctor --full`
  - (Windows) `scripts\\vibe.cmd doctor --full`

## Before coding
- Read: `.vibe/agent_memory/DONT_DO_THIS.md`
- Check impact for shared/core files: `python3 scripts/vibe.py impact <path>`
- Find entry points fast:
  - `python3 scripts/vibe.py search TranslationService`
  - `python3 scripts/vibe.py search PlaceholderMasker`

## While coding
- Keep changes small and localized.
- For placeholder/token logic, add/adjust tests under `tests/XTranslatorAi.Tests`.
- When validating xTranslator outputs: `python3 scripts/vibe.py qa <file.xml>`

## Before finishing
- Run: `python3 scripts/vibe.py doctor --full` (or at least `python3 scripts/vibe.py doctor`)
- Run tests (core): `dotnet test tests/XTranslatorAi.Tests/XTranslatorAi.Tests.csproj -c Release`
