# Agent Notes (vibe-kit-seed)

This repo is a **publisher/distribution** repo for installing the **repo-local** vibe-kit toolkit into other repositories.

## 한국어 요약
- 이 repo는 `vibe-kit`을 다른 레포에 배포/설치하기 위한 **seed 배포** 저장소입니다.
- 이 repo 자체를 의존성/스타터로 “도입”하는 게 아니라, GitHub Release 자산을 받아 target repo에서 설치합니다.
- Drive 미러는 선택이며, **GitHub Releases가 소스(검증 기준)** 입니다. 미러는 항상 `SHA256SUMS`로 검증합니다.

## What to do
- Build release assets: `python3 scripts/make_release_assets.py <version> --out-dir dist/<version> --force`
- Keep changes minimal and security-focused (installer + seed format + allowlist + tests).

## Agent startup
- Read context entrypoint first: `.vibe/AGENT_CHECKLIST.md` (or `.vibe/context/LATEST_CONTEXT.md` if checklist is unavailable).
- First action command:
  - WSL/Linux: `python3 scripts/vibe.py doctor --full`
  - Windows: `scripts\vibe.cmd doctor --full`

## Release flow (maintainers)
- Follow: `RELEASE_CHECKLIST.md`
- GitHub Release assets must include exactly:
  - `VIBEKIT_SEED-<version>-<sha256>.md`
  - `vibekit_seed_install.py`
  - `SHA256SUMS`
- Do not overwrite shared mirror files (Drive): always upload new immutable files/links.

## What not to do
- Do not treat this as a UI/app starter template.
- Do not propose adopting this repo as a dependency; users should download Release assets and install into their target repo.
- Do not add auto-execution post-install behavior.

## Quick verification
- Unit tests: `python3 -m unittest discover -s tests -p 'test*.py' -v`
- Bytecode sanity: `python3 -m compileall vibekit_seed_install.py scripts .vibe/brain`
