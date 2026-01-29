# vibe-kit-seed

This repo publishes **immutable** seed release artifacts for installing **vibe-kit** into *another* repository.

- **You do not "adopt" this repo** as a dependency or starter template.
- Consumers download the Release assets and run the installer in the **target repo**.

## 한국어 요약

- `vibe-kit-seed`는 앱(UI/아키텍처) 스타터 템플릿이 아니라, `vibe-kit`을 **다른 레포에 배포/설치**하기 위한 “seed 배포” 저장소입니다.
- GitHub Releases에서 아래 3개 파일을 같은 릴리즈에서 내려받아 **target repo에서** 사용합니다:
  - `VIBEKIT_SEED-<version>-<sha>.md`
  - `vibekit_seed_install.py`
  - `SHA256SUMS`
- 설치기는 SHA256 검증 후, target repo에 `.vibe/` + `scripts/vibe.py` 등을 **파일로만 설치**합니다(기본은 dry-run, `--apply`가 있어야 실제로 씁니다).
- 설치기는 기본적으로 어떤 스크립트도 자동 실행하지 않습니다.

### vibe-kit 주요 기능 (설치 후, target repo에서 사용)

설치 후에는 target repo에서 아래처럼 사용합니다:
- 진단/요약 생성: `python3 scripts/vibe.py doctor --full`
  - 출력: `.vibe/context/LATEST_CONTEXT.md`, `.vibe/reports/*` (gitignore 권장)
- 변경 감시(선택): `python3 scripts/vibe.py watch`
- 컨텍스트 DB 검색: `python3 scripts/vibe.py search "<query>"`
- 영향도(간단) 분석: `python3 scripts/vibe.py impact <path>`
- 에이전트에 주기 위한 요약팩: `python3 scripts/vibe.py pack --scope=staged|changed|path|recent --out .vibe/context/PACK.md`
- Git hook(선택): `python3 scripts/vibe.py hooks --install` (pre-commit에 `.vibe/brain/precommit.py` 연결)

## What this is (and isn't)

Think of this as a distribution/publisher repo:
- `vibe-kit-seed` (this repo): builds and publishes the seed artifacts (`VIBEKIT_SEED-...md`, installer, `SHA256SUMS`)
- `vibe-kit` (installed into a target repo): a small **repo-local** toolkit that helps humans/agents get project context fast

What vibe-kit does (in the *target* repo after install):
- Builds a local index of the repo (SQLite) and writes summaries under `.vibe/context/`
- Produces lightweight context packs for LLMs (e.g. `.vibe/context/LATEST_CONTEXT.md`)
- Writes reports under `.vibe/reports/` (gitignored)

### vibe-kit commands (after install, in the target repo)

- `python3 scripts/vibe.py doctor --full`: scan + reports, refresh `.vibe/context/LATEST_CONTEXT.md`
- `python3 scripts/vibe.py search "<query>"`: full-text search in the local context DB
- `python3 scripts/vibe.py pack --scope=...`: generate a compact `.vibe/context/PACK.md` for an agent
- `python3 scripts/vibe.py impact <path>`: quick impact analysis for a file
- `python3 scripts/vibe.py watch`: keep context refreshed while you work (watchdog if installed; otherwise polling)
- `python3 scripts/vibe.py hooks --install`: optional git hook installer

What vibe-kit does **not** do:
- It is **not** a UI/app starter template.
- It is **not** an AI agent runner/sandbox.
- It is **not** a release/packaging system for your app (e.g. Windows EXE distribution).
- It makes **no network/API calls** by default.
- The installer **does not auto-run** any extracted scripts.

## Recommended distribution model

- **Source of truth:** GitHub Releases (tagged versions)
- **Mirror:** Google Drive (optional). Treat as untrusted; always verify against the GitHub Release SHA256.

## Install (from a GitHub Release)

1) Download these assets from the same Release:
   - `VIBEKIT_SEED-<version>-<sha>.md`
   - `vibekit_seed_install.py`
   - `SHA256SUMS`

2) Verify the seed file SHA256 matches `SHA256SUMS` (example):
   - Linux/macOS: `sha256sum -c SHA256SUMS`
   - Windows (PowerShell): `Get-FileHash .\\VIBEKIT_SEED-...md -Algorithm SHA256`

3) Install into a target repo directory (example):
   - Linux/macOS: `python3 vibekit_seed_install.py install VIBEKIT_SEED-...md --root . --expected-seed-sha256 <sha256> --apply`
   - Windows: `py vibekit_seed_install.py install VIBEKIT_SEED-...md --root . --expected-seed-sha256 <sha256> --apply`

4) After install (in the target repo), run:
   - `python3 scripts/vibe.py doctor --full`

## Create a new seed file

From this repo root:

- Recommended: `python3 scripts/make_release_assets.py <version> --out-dir dist/<version> --force`

Then publish the generated files as GitHub Release assets (see `RELEASE_CHECKLIST.md`).
