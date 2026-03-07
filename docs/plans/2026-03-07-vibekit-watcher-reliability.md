# vibe-kit Watcher Reliability Plan

## Goal
- Make `python3 scripts/vibe.py watch` useful across repo stacks by tracking files based on `include_globs`.
- Improve polling fallback so new files and deleted files are reflected instead of only tracking the initial snapshot.

## Non-goals
- Do not redesign the whole indexing pipeline.
- Do not add new runtime dependencies.
- Do not change `doctor`, `pack`, or symbol extraction behavior in this slice.

## Affected Files
- `.vibe/brain/watcher.py`
- `tests/test_watcher.py`
- `README.md`

## Constraints
- Keep the existing CLI surface stable.
- Preserve `exclude_dirs` behavior.
- Prefer repo config over hard-coded language assumptions.
- Keep polling mode simple and stdlib-only.

## Milestones
1. Replace hard-coded watch suffix filtering with config-driven matching.
2. Add polling snapshot reconciliation for create, modify, move, and delete cases.
3. Add focused unit tests for tracking decisions and polling diff behavior.
4. Update README to describe the broader watch behavior.

## Validation
- `python3 -m unittest tests.test_watcher -v`
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `python3 scripts/vibe.py doctor --full`

## Risks / Rollback
- Broader file tracking could produce noisier refreshes if matching is too permissive.
- Polling reconciliation must avoid queuing excluded files or stale deleted paths.
- Rollback is straightforward: revert watcher-specific changes only.
