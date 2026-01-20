# Vibe-kit Public Seed Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish vibe-kit seed artifacts safely for external users via GitHub Releases, with Drive as an untrusted mirror.

**Architecture:** Generate a single `VIBEKIT_SEED*.md` file containing a base64 zip payload. Install via a standalone `vibekit_seed_install.py` that (1) verifies the seed file SHA256 provided by the user, (2) extracts only allowlisted paths under a chosen root, (3) never auto-runs any extracted scripts.

**Tech Stack:** Python 3 standard library (`argparse`, `hashlib`, `zipfile`, `pathlib`, `unittest`).

### Task 1: Add public-facing docs and repo hygiene

**Files:**
- Create: `README.md`
- Create: `SECURITY.md`
- Create: `.gitignore`

**Steps:**
1) Write minimal install instructions that require SHA256 verification against GitHub Releases.
2) Document Drive as a mirror only (untrusted) and “new file/new link” rule for updates.

### Task 2: Implement a hardened seed installer

**Files:**
- Create: `vibekit_seed_install.py`

**Steps:**
1) Parse `VIBEKIT_SEED*.md` payload between `VIBEKIT_PAYLOAD_BASE64_BEGIN/END`.
2) Compute seed file SHA256 and compare to `--expected-seed-sha256` (required).
3) Extract zip entries safely:
   - Reject absolute paths, `..`, Windows drive prefixes, and backslashes.
   - Allowlist extracted paths to the known vibe-kit file set.
   - Always write within `--root`.
4) Do not execute any extracted code by default (no post-install hooks).

### Task 3: Update seed generator output format/instructions

**Files:**
- Modify: `scripts/vibe.py`

**Steps:**
1) Remove the embedded installer code block from the seed markdown.
2) Update the “Install” section to reference `vibekit_seed_install.py` as a separate release asset.
3) Keep payload sha256 in the header for human inspection, but rely on external `SHA256SUMS` for trust.

### Task 4: Add unit tests for installer safety checks

**Files:**
- Create: `tests/test_vibekit_seed_install.py`

**Steps:**
1) Test that unsafe zip paths (e.g. `../pwn`) are rejected.
2) Test allowlist behavior (unknown paths rejected).
3) Test SHA mismatch fails without writing files.

### Task 5: Verification

**Steps:**
1) Run: `python3 -m compileall vibekit_seed_install.py scripts`
2) Run: `python3 -m unittest discover -s tests -p 'test*.py' -v`
3) Generate a seed and do a dry-run install:
    - `python3 scripts/vibe.py seed --out /tmp/VIBEKIT_SEED-test.md --force`
    - `python3 vibekit_seed_install.py install /tmp/VIBEKIT_SEED-test.md --root /tmp/vibekit-target --expected-seed-sha256 <sha>`
