# vibe-kit Boundary Guard (Architecture Rules) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a repo-local `vibe boundaries` command that detects “boundary leaks” (illegal dependencies across architectural layers) using configurable rules in `.vibe/config.json`, and surfaces results in `doctor` + `LATEST_CONTEXT`.

**Architecture:** Implement a lightweight dependency scanner (stdlib-only) for:
- `.csproj` ProjectReference edges (already indexed in `deps` table)
- Python imports (AST-based best-effort resolution to repo files)
- JS/TS imports (regex-based best-effort resolution for relative/aliased imports)

Then evaluate dependencies against config-driven **deny rules** (`architecture.rules`) and write:
- `.vibe/reports/boundaries.json` (machine-readable)
- `.vibe/reports/boundaries.md` (human-readable)

Default behavior: **skip** when no rules configured; optionally fail the run if `quality_gates.boundary_block=true`.

**Tech Stack:** Python 3 (stdlib only), existing vibe-kit DB (`.vibe/db/context.sqlite`).

---

### Task 1: Add config plumbing for `architecture`

**Files:**
- Modify: `.vibe/brain/context_db.py`
- Modify: `scripts/setup_vibe_env.py`

**Step 1: Extend `VibeConfig`**
- Add `architecture: dict[str, Any]` to `VibeConfig` and populate in `load_config()`.

**Step 2: Add default `architecture` section**
- In `DEFAULT_CONFIG` add:
  - `architecture.enabled` (false)
  - `architecture.rules` (empty list)
  - `architecture.python_roots` (e.g. `["src", "."]`)
  - `architecture.js_aliases` (empty dict)

**Step 3: Run basic sanity**
- Run: `python3 -m compileall scripts .vibe/brain`
- Expected: no errors.

---

### Task 2: Implement boundary checker

**Files:**
- Create: `.vibe/brain/check_boundaries.py`

**Step 1: Add dependency extraction**
- Read ProjectReference deps from sqlite (`deps` table).
- For `.py`, parse imports with `ast` and resolve to local files when possible.
- For `.js/.ts/.jsx/.tsx`, find import specifiers with regex and resolve local targets (relative imports + optional alias map).

**Step 2: Add rule evaluation**
- Read `cfg.architecture["rules"]`:
  - each rule: `{name, enabled, from_globs, to_globs, kinds?, reason?}`
- Emit violations with enough context (`from`, `to`, `kind`, `line` if available, `rule`, `reason`).

**Step 3: Write reports**
- Always write `.vibe/reports/boundaries.json`.
- Also write `.vibe/reports/boundaries.md` for quick reading.

**Step 4: Exit code**
- If violations exist and `quality_gates.boundary_block=true`, exit 1; else exit 0.

---

### Task 3: Wire into CLI + doctor + summary

**Files:**
- Modify: `scripts/vibe.py`
- Modify: `.vibe/brain/doctor.py`
- Modify: `.vibe/brain/summarizer.py`

**Step 1: Add `vibe boundaries`**
- Add a subcommand that runs `.vibe/brain/check_boundaries.py`.

**Step 2: Run during `doctor`**
- Add a `doctor` step for boundaries (should skip by default if no rules).

**Step 3: Surface in LATEST_CONTEXT**
- If `.vibe/reports/boundaries.json` has violations, add a short bullet and a pointer to `.vibe/reports/boundaries.md`.

---

### Task 4: Documentation touch-ups

**Files:**
- Modify: `.vibe/README.md`
- Modify: `.vibe/AGENT_CHECKLIST.md`
- Modify: `README.md`

**Step 1: Mention `boundaries`**
- Add `python3 scripts/vibe.py boundaries` in the “주요 명령/What vibe-kit does” lists.

**Step 2: Add a tiny config example**
- Show a minimal `architecture.rules` example.

---

### Task 5: Tests

**Files:**
- Create: `tests/test_boundaries.py`

**Step 1: Unit test rule matching**
- Provide a small synthetic deps list and verify the deny rule flags exactly the intended edge.

**Step 2: Run**
- Run: `python3 -m unittest discover -s tests -p 'test*.py' -v`
- Expected: PASS.

---

### Task 6: Verify + ship

**Step 1: Smoke-run**
- Run: `python3 scripts/vibe.py boundaries`
- Expected: “skipped (no rules configured)” in this repo, and a report file written.

**Step 2: Commit + push**
- Commit with message like: `feat: add boundary rule checker`
- Push to `origin/main`.

