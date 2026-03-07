# vibe-kit Shared Repo Detection Plan

## Goal
- Remove duplicated repo stack detection logic across `configure`, `pack`, and nearby checks.
- Keep user-facing behavior stable while making future stack support easier to extend.

## Non-goals
- Do not redesign the whole typecheck baseline workflow.
- Do not change CLI flags or config schema.
- Do not add new dependencies.

## Affected Files
- `.vibe/brain/repo_detect.py`
- `.vibe/brain/configure.py`
- `.vibe/brain/pack.py`
- `.vibe/brain/typecheck_baseline.py`
- `tests/test_configure.py`
- `tests/test_pack.py`
- `tests/test_repo_detect.py`

## Constraints
- Preserve current package manager and test command behavior.
- Keep existing tests readable and focused.
- Prefer thin wrappers in legacy modules where tests already depend on private helpers.

## Milestones
1. Extract shared helpers for package manager, dotnet target, and stack file detection.
2. Switch `configure` to use the shared helpers without changing recommendation outputs.
3. Switch `pack` test-command hints to use the same shared helpers.
4. Reuse the shared dotnet target selection in `typecheck_baseline`.
5. Add focused unit tests for shared detection and run full regression checks.

## Validation
- `python3 -m unittest discover -s tests -p 'test_repo_detect.py' -v`
- `python3 -m unittest tests.test_configure -v` or discover equivalent
- `python3 -m unittest tests.test_pack -v` or discover equivalent
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `python3 scripts/vibe.py doctor --full`

## Risks / Rollback
- Shared helpers can accidentally change detection precedence.
- Refactor can break private-helper tests if compatibility wrappers are removed too aggressively.
- Rollback is low risk because the change is module-local and dependency-free.
