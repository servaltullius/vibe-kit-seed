# vibe-kit Improvement Backlog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve vibe-kit’s real-world usefulness by prioritizing reliability-first improvements (P0), analysis depth upgrades (P1), and platform-level expansion (P2).

**Architecture:** Treat `scripts/vibe.py` as the stable CLI facade and keep improvements in `.vibe/brain/*` modules with focused tests in `tests/`. Deliver in thin slices with TDD and repo-local defaults. Avoid new runtime dependencies unless explicitly approved.

**Tech Stack:** Python 3 (stdlib-first), `unittest`, git history mining, optional GitHub Actions for release provenance.

---

## P0 Backlog (Immediate: reliability + adoption)

### Task 1: Make `pack` resilient when scope is empty

**Files:**
- Modify: `.vibe/brain/pack.py`
- Test: `tests/test_pack.py` (new)

**Step 1:** Write failing test: `--scope=changed` with no matching files should fallback to `recent`, not exit 2.  
Run: `python3 -m unittest tests.test_pack -v`  
Expected: FAIL (current behavior returns 2).

**Step 2:** Implement fallback logic (`changed|staged -> recent`) and print explicit fallback reason.

**Step 3:** Re-run tests.  
Run: `python3 -m unittest tests.test_pack -v`  
Expected: PASS.

**Step 4:** Commit.  
`git commit -m "fix: make pack fallback to recent when scope is empty"`

### Task 2: Remove hard-coded test command from PACK output

**Files:**
- Modify: `.vibe/brain/pack.py`
- Modify: `scripts/setup_vibe_env.py`
- Modify: `.vibe/brain/context_db.py`
- Test: `tests/test_pack.py`

**Step 1:** Write failing test for command section generation (repo-aware commands only; no fixed `.NET` path).

**Step 2:** Add `context.commands` defaults in setup config and load through `VibeConfig`.

**Step 3:** Update PACK command rendering to use config + environment detection.

**Step 4:** Verify.  
Run: `python3 -m unittest tests.test_pack -v`  
Expected: PASS.

**Step 5:** Commit.  
`git commit -m "feat: make pack commands repo-aware and configurable"`

### Task 3: Add `boundaries` quickstart template + strict mode

**Files:**
- Modify: `scripts/vibe.py`
- Modify: `.vibe/brain/check_boundaries.py`
- Modify: `scripts/setup_vibe_env.py`
- Modify: `README.md`
- Test: `tests/test_boundaries.py`

**Step 1:** Write failing tests for:
- template generation command
- strict mode non-zero exit on violations.

**Step 2:** Add `vibe boundaries --init-template` to write starter rules into `.vibe/config.json`.

**Step 3:** Add explicit `--strict` behavior (exit 1 on violations regardless of best-effort mode).

**Step 4:** Verify.  
Run: `python3 -m unittest discover -s tests -p 'test*.py' -v`  
Expected: PASS.

**Step 5:** Commit.  
`git commit -m "feat: add boundaries template and strict enforcement mode"`

### Task 4: Add release provenance attestation workflow (SLSA L2 baseline)

**Files:**
- Create: `.github/workflows/release-attestation.yml`
- Modify: `RELEASE_CHECKLIST.md`
- Modify: `README.md`

**Step 1:** Add GitHub Actions workflow to generate artifact attestations for release assets.

**Step 2:** Document verification steps (`gh attestation verify ...`) in release checklist.

**Step 3:** Validate workflow YAML syntax and docs links.

**Step 4:** Commit.  
`git commit -m "chore: add release artifact attestation workflow and docs"`

---

## P1 Backlog (Near-term: analysis quality)

### Task 5: Multi-language symbol extraction (Python + TS/TSX)

**Files:**
- Modify: `.vibe/brain/indexer.py`
- Create: `.vibe/brain/symbol_extract_py.py`
- Create: `.vibe/brain/symbol_extract_ts.py`
- Test: `tests/test_indexer_symbols.py` (new)

**Verification:**
- `python3 -m unittest tests.test_indexer_symbols -v`
- `python3 scripts/vibe.py doctor --full`

### Task 6: Improve impact analysis with coupling-weighted scoring

**Files:**
- Modify: `.vibe/brain/impact_analyzer.py`
- Modify: `.vibe/brain/change_coupling.py`
- Test: `tests/test_impact_analyzer.py` (new)

**Verification:**
- `python3 -m unittest tests.test_impact_analyzer -v`
- `python3 scripts/vibe.py impact scripts/vibe.py --limit 10`

### Task 7: Extend coupling signals (ticket/author/time-window)

**Files:**
- Modify: `.vibe/brain/change_coupling.py`
- Modify: `scripts/vibe.py` (new CLI args passthrough)
- Modify: `README.md`
- Test: `tests/test_change_coupling.py`

**Verification:**
- `python3 -m unittest tests.test_change_coupling -v`
- `python3 scripts/vibe.py coupling --detect-renames`

---

## P2 Backlog (Strategic: platform expansion)

### Task 8: Expose vibe context over MCP-compatible local server

**Files:**
- Create: `scripts/vibe_mcp_server.py`
- Create: `docs/vibe-mcp.md`
- Modify: `README.md`

**Verification:**
- basic tool listing + query smoke tests in local session
- `python3 -m compileall scripts`

### Task 9: Optional vector retrieval mode for large monorepos

**Files:**
- Create: `.vibe/brain/retrieval.py`
- Modify: `.vibe/brain/search.py`
- Modify: `scripts/setup_vibe_env.py`
- Test: `tests/test_retrieval.py` (new)

**Verification:**
- `python3 -m unittest tests.test_retrieval -v`
- regression: existing `search` behavior unchanged when disabled

---

## Delivery Order and Exit Criteria

1. **Ship all P0 first** (no new runtime dependencies).
2. P0 exit criteria:
- `python3 -m unittest discover -s tests -p 'test*.py' -v` green
- `python3 scripts/vibe.py doctor --full` green
- docs updated (`README.md`, `RELEASE_CHECKLIST.md`).
3. Start P1 only after 2 real repos validate P0 workflow.
4. Start P2 only after P1 demonstrates measurable gain in search/impact relevance.
