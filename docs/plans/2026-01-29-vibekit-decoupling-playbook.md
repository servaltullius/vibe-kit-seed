# vibe-kit Decoupling Playbook Templates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** For each top `boundary_leaks` item in `vibe coupling`, auto-generate concrete refactoring/decoupling “playbook templates” (issue/PR-ready steps) and write a human-friendly Markdown report.

**Architecture:** Extend `.vibe/brain/change_coupling.py` to (1) attach structured `playbooks` to each `boundary_leaks` item, (2) render a `.vibe/reports/decoupling_suggestions.md` file summarizing top clusters/leaks/hubs with actionable steps. Keep everything repo-local, deterministic, and bounded in size.

**Tech Stack:** Python 3 (stdlib only).

---

### Task 1: Add playbook generation for boundary leaks

**Files:**
- Modify: `.vibe/brain/change_coupling.py`

**Step 1: Implement playbook builder**
- Add a function like `_build_boundary_leak_playbooks(a, b, ...) -> list[dict]`.
- Each playbook should include:
  - `title`
  - `when_to_use`
  - `steps` (3–6 bullets)
  - `acceptance` (2–4 bullets)
  - `safety_checks` (2–4 bullets)

**Step 2: Attach to boundary leak entries**
- Add `playbooks` to each boundary leak dict.

---

### Task 2: Render Markdown suggestions report

**Files:**
- Modify: `.vibe/brain/change_coupling.py`

**Step 1: Add renderer**
- Add `render_decoupling_suggestions_md(payload) -> str`.
- Include sections:
  - Top clusters (module candidates)
  - Top boundary leaks (with playbooks)
  - Top hubs (short guidance)

**Step 2: Write file**
- Write `.vibe/reports/decoupling_suggestions.md` on each run (gitignored).
- Add `decoupling_suggestions_md_path` to JSON for discoverability.

---

### Task 3: Surface link in LATEST_CONTEXT

**Files:**
- Modify: `.vibe/brain/summarizer.py`

**Step 1: Add a short note**
- If `.vibe/reports/decoupling_suggestions.md` exists, mention it under Hotspots/change coupling lines.

---

### Task 4: Tests

**Files:**
- Modify: `tests/test_change_coupling.py`

**Step 1: Add failing test**
- Verify that a computed boundary leak includes a non-empty `playbooks` list with required keys.

**Step 2: Run**
- Run: `python3 -m unittest discover -s tests -p 'test*.py' -v`
- Expected: PASS.

---

### Task 5: Verify + ship

**Step 1: Smoke-run**
- Run: `python3 scripts/vibe.py coupling --group-by dir --dir-depth 2 --top 5`
- Expected: writes `.vibe/reports/change_coupling.json` and `.vibe/reports/decoupling_suggestions.md`.

**Step 2: Commit + push**
- Commit with message like `feat: add decoupling playbook templates`.
- Push to `origin/main`.

