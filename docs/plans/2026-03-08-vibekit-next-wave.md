# 2026-03-08 vibe-kit next wave

## Goal
- Improve vibe-kit adoption and analysis quality in one coordinated pass.
- Make bootstrap/install flows easier to reproduce outside `gh`.
- Remove agent instruction drift across installer/setup/validation.
- Raise confidence in `search`, `impact`, and `summarizer` with targeted tests.
- Improve analysis quality for polyglot and monorepo-style repos.

## Non-goals
- Introduce external runtime dependencies.
- Redesign the overall CLI surface area.
- Build a fully semantic cross-language parser.
- Change default repo-local installation model.

## Affected files/modules
- `vibekit_seed_install.py`
- `scripts/setup_vibe_env.py`
- `.vibe/brain/agents_doctor.py`
- `.vibe/brain/search.py`
- `.vibe/brain/impact_analyzer.py`
- `.vibe/brain/summarizer.py`
- `.vibe/brain/indexer.py`
- `.vibe/brain/configure.py`
- `.vibe/brain/context_db.py`
- `.vibe/brain/check_boundaries.py`
- `README.md`
- `tests/*`

## Constraints
- Preserve existing repo-local installation behavior.
- Keep installer safe and deterministic; no destructive overwrite without existing flags.
- Reuse existing helpers/patterns where possible.
- Keep changes modular enough to land and test in stages.

## Milestones
1. Installer and agent UX hardening
   - Add bootstrap asset source flexibility.
   - Centralize agent template text generation.
   - Add remediation snippets to `agents doctor`.
   - Reframe README Quickstart around install success loop.

2. Analysis correctness baseline
   - Add focused tests for `search`, `impact`, and `summarizer`.
   - Improve `impact` scoring to use dependency/coupling/context signals.
   - Replace `mtime`-only recent summary logic with actual changed-file tracking.

3. Polyglot/monorepo analysis improvements
   - Extend deps indexing beyond `ProjectReference`.
   - Reuse common glob/path matching where missing.
   - Improve `configure` messaging for detected stack(s) and next actions.

## Validation
- Unit tests for installer, agent doctor, search, impact, summarizer, indexer, configure.
- Full `python3 -m unittest discover -s tests -p 'test_*.py'`
- `python3 scripts/vibe.py doctor --full`
- Release/bootstrap smoke using local assets where appropriate.

## Risks / rollback notes
- Installer CLI changes may affect bootstrap callers; keep new inputs additive.
- New deps indexing may create noisy relationships; scope to best-effort local imports only.
- Impact scoring changes may change output ordering; tests should verify stable high-level behavior, not brittle exact internals.
