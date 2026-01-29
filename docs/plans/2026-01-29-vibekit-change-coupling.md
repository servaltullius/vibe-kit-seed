# vibe-kit Change Coupling (Refactoring/Decoupling) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** Add a repo-local “change coupling” report (files that change together in git history) to help code review, refactoring, decoupling, and architecture checks.

**Architecture:** Implement `.vibe/brain/change_coupling.py` that reads `git log --name-only`, filters files by `.vibe/config.json` (`exclude_dirs`, `include_globs`), and emits `.vibe/reports/change_coupling.json`. Add a `python3 scripts/vibe.py coupling` command, and run it from `doctor --full` (best-effort, skip if no git). Optionally surface a small summary in `.vibe/context/LATEST_CONTEXT.md`.

**Tech Stack:** Python 3 (stdlib only), git CLI.

---

### Task 1: CLI entry

**Files:**
- Modify: `scripts/vibe.py`

**Step 1: Add subcommand**
- Add `coupling` subcommand.
- Wire to `.vibe/brain/change_coupling.py` with pass-through args.

**Step 2: Smoke-run**
- Run: `python3 scripts/vibe.py coupling`
- Expected: “SKIP” if no git, otherwise writes `.vibe/reports/change_coupling.json`.

---

### Task 2: Implement `.vibe/brain/change_coupling.py`

**Files:**
- Create: `.vibe/brain/change_coupling.py`

**Step 1: Parse commits**
- Execute `git log --name-only --pretty=format:%H --no-merges --max-count <N>`.
- Parse into a list of commits, each with a de-duplicated set of changed files.

**Step 2: Filter files**
- Exclude files under any `exclude_dirs` segment (case-insensitive).
- Include only files matching `include_globs` (fnmatch, with optional `**/` prefix handling).

**Step 3: Compute metrics**
- Pair count: how many commits changed file A and file B together.
- File commit count: how many commits touched each file.
- Optional normalized score: Jaccard = pair_count / (countA + countB - pair_count).
- “Sum of couplings” per file (architectural significance).
- Guard performance: skip commits with too many files (configurable cap).

**Step 4: Write report**
- Default output: `.vibe/reports/change_coupling.json`.
- Print a short summary (top pairs + top sum-of-couplings).

---

### Task 3: Integrate into `doctor` and context

**Files:**
- Modify: `.vibe/brain/doctor.py`
- (Optional) Modify: `.vibe/brain/summarizer.py`

**Step 1: Doctor integration**
- Run change coupling as a best-effort step during `doctor --full`.

**Step 2: Context summary (optional)**
- If report exists, surface top 3–5 pairs in `LATEST_CONTEXT.md` without bloating.

---

### Task 4: Docs and agent guidance

**Files:**
- Modify: `README.md`
- Modify: `.vibe/README.md`
- Modify: `.vibe/AGENT_CHECKLIST.md`

**Step 1: Document usage**
- Mention `python3 scripts/vibe.py coupling` and what it’s for.

---

### Task 5: Unit tests (no git required)

**Files:**
- Create: `tests/test_change_coupling.py`

**Step 1: Pure-function tests**
- Test parsing of a sample `git log --name-only` output.
- Test pair counting and Jaccard calculation on a small synthetic commit set.

---

### Task 6: Verify + ship

**Step 1: Python sanity**
- Run: `python3 -m compileall scripts .vibe/brain`
- Expected: success

**Step 2: Unit tests**
- Run: `python3 -m unittest discover -s tests -p 'test*.py' -v`
- Expected: all PASS

**Step 3: Commit + push**
- Commit with message like `feat: add change coupling report`.
- Push to `origin/main`.

