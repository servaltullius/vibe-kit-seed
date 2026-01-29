# vibe-kit Auto-Configure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** Add a `vibe configure` command that auto-detects a target repo’s stack and safely updates `.vibe/config.json` so `doctor`/`precommit` run the right repo-specific checks by default.

**Architecture:** Implement `.vibe/brain/configure.py` as an idempotent, dry-run-by-default config mutator. Wire it into `scripts/vibe.py configure`. Use conservative heuristics (lockfiles + package.json scripts + common project markers) and never execute arbitrary code; only write config when `--apply` is provided.

**Tech Stack:** Python 3 (stdlib only), existing vibe-kit scripts.

---

### Task 1: Add `configure` CLI wiring

**Files:**
- Modify: `scripts/vibe.py`

**Step 1: Add subcommand**
- Add a `configure` subcommand (`--apply`, `--force`) and delegate to `.vibe/brain/configure.py`.

**Step 2: Smoke-run**
- Run: `python3 scripts/vibe.py configure`
- Expected: prints a dry-run summary (no file changes).

---

### Task 2: Implement `.vibe/brain/configure.py`

**Files:**
- Create: `.vibe/brain/configure.py`

**Step 1: Detection heuristics (no writes)**
- Detect Node via `package.json`, and choose a package manager via:
  - `package.json.packageManager` (preferred)
  - else lockfiles: `bun.lock`/`bun.lockb`, `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`
- Detect TypeScript via `tsconfig.json` or presence of `*.ts`/`*.tsx` files (excluding excluded dirs).
- Detect Python typechecking via `mypy.ini` or `[tool.mypy]` in `pyproject.toml` (best-effort).

**Step 2: Config mutation rules**
- Always preserve existing user config; only set missing values unless `--force`.
- Populate (when confident):
  - `quality_gates.typecheck_cmd`
  - `quality_gates.typecheck_when_any_glob` (used by precommit)
- Ensure `checks` exists (`doctor`/`precommit` lists).
- Write a report: `.vibe/reports/configure_report.json` (even in dry-run).

**Step 3: Apply vs dry-run behavior**
- Default: show proposed changes + write report only.
- With `--apply`: write updated `.vibe/config.json`.

---

### Task 3: Make precommit respect `typecheck_when_any_glob`

**Files:**
- Modify: `.vibe/brain/precommit.py`

**Step 1: Add gating**
- If `quality_gates.typecheck_when_any_glob` is configured and any staged file matches it, run `typecheck_baseline.py`.
- Preserve existing C#/.NET behavior (run when `.cs`/`.csproj`/`.sln` staged).

**Step 2: Smoke-run**
- Run: `python3 scripts/vibe.py precommit` (in this repo it should remain fast and non-failing).

---

### Task 4: Harden custom checks runner

**Files:**
- Modify: `.vibe/brain/custom_checks.py`

**Step 1: Handle missing executables**
- Catch `OSError` / `FileNotFoundError` during `subprocess.run` and record a failed result (rc=127) instead of crashing.

---

### Task 5: Update docs and agent instructions

**Files:**
- Modify: `README.md`
- Modify: `.vibe/README.md`
- Modify: `.vibe/AGENT_CHECKLIST.md`
- Modify: `vibekit_seed_install.py`

**Step 1: Document the new flow**
- Mention running `python3 scripts/vibe.py configure --apply` after installation (optional but recommended).

**Step 2: Update generated agent instructions**
- In installer templates, add “Run configure” before “Run doctor”.

---

### Task 6: Verify

**Step 1: Python sanity**
- Run: `python3 -m compileall vibekit_seed_install.py scripts .vibe/brain`
- Expected: success

**Step 2: Unit tests**
- Run: `python3 -m unittest discover -s tests -p 'test*.py' -v`
- Expected: all PASS

