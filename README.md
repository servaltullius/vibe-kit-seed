# vibe-kit-seed

This repo publishes **immutable** seed release artifacts for installing **vibe-kit** into *another* repository.

- **You do not "adopt" this repo** as a dependency or starter template.
- Consumers download the Release assets and run the installer in the **target repo**.

## 한국어 안내 (자세히)

### 1) 이 레포는 “배포/설치”용입니다 (중요)

- `vibe-kit-seed`는 **앱(UI/아키텍처) 스타터 템플릿**이 아닙니다.
- 이 레포를 서브모듈/의존성으로 “도입”하는 방식이 아니라, **GitHub Releases에 올라간 산출물(시드/설치기/체크섬)** 을 받아서 **내 레포(target repo)** 에 설치하는 방식입니다.
- 목적은 “기술스택 고정”이 아니라, **내 레포에 맞게 커스텀 가능한 repo-local 도구(vibe-kit)** 를 심는 것입니다.

### 2) 배포 모델 (권장)

- **Source of truth:** GitHub Releases (버전 태그 + immutable assets)
- **Mirror:** Google Drive(선택). 편의용 미러이며 **항상 SHA256으로 검증**합니다.

### 3) 설치 흐름 (target repo에서)

GitHub Releases의 같은 릴리즈에서 아래 3개 파일을 내려받습니다:
- `VIBEKIT_SEED-<version>-<sha256>.md`
- `vibekit_seed_install.py`
- `SHA256SUMS`

검증:
- Linux/macOS: `sha256sum -c SHA256SUMS`
- Windows(PowerShell): `Get-FileHash .\\VIBEKIT_SEED-...md -Algorithm SHA256` (값을 `SHA256SUMS`와 비교)

설치(권장: dry-run → apply):
- dry-run: `python3 vibekit_seed_install.py install VIBEKIT_SEED-...md --root . --expected-seed-sha256 <sha256>`
- apply: `python3 vibekit_seed_install.py install VIBEKIT_SEED-...md --root . --expected-seed-sha256 <sha256> --apply`
- 참고: `--expected-seed-sha256`에는 seed 본문에 보이는 payload 해시가 아니라, `SHA256SUMS`의 seed 파일 해시(첫 컬럼)를 넣어야 합니다.
- 에이전트에게 seed를 보여줄 때는 `VIBEKIT_PAYLOAD_BASE64_BEGIN/END` 사이 payload 블록은 제외하고 상단 안내만 전달하세요.

전역 자동화(옵션):
- 최신(또는 지정 태그) 릴리즈를 자동 다운로드/검증/설치:
  - dry-run: `python3 vibekit_seed_install.py bootstrap --root .`
  - apply: `python3 vibekit_seed_install.py bootstrap --root . --apply --run-setup --post-configure --post-doctor --post-hooks --write-ci-guard --agent all`
  - 태그 고정 예시: `python3 vibekit_seed_install.py bootstrap --tag v1.2.3 --root . --apply`
- 새 레포 자동 부트스트랩(옵트인 마커 방식):
  - 전역 훅 설치: `python3 vibekit_seed_install.py install-global-hook`
  - 프로젝트 루트에 `.vibekit.auto` 파일 생성 후 첫 checkout 시 자동 bootstrap
  - 기본 동작: seed 설치 + setup/configure/doctor/hooks + `.github/workflows/vibekit-guard.yml` 작성
  - 추가 동작(기본 활성): Codex 전역 지시문(`~/.codex/AGENTS.md` 또는 `~/.codex/AGENTS.override.md`)에
    "vibe-kit 미설치 repo에서 yes/no 설치 질문" 규칙 자동 반영
    - 끄기: `python3 vibekit_seed_install.py install-global-hook --no-install-codex-prompt`
    - 억제 마커 파일명 변경: `--suppress-file .vibekit.ignore`

설치 결과(요약):
- target repo에 `.vibe/` + `scripts/vibe.py` 등이 **파일로만 설치**됩니다.
- 설치기는 기본적으로 어떤 스크립트도 **자동 실행하지 않습니다**.
- 런타임 산출물은 `.vibe/db/`, `.vibe/reports/` 등에 생성되며 보통 gitignore를 권장합니다.

### vibe-kit 주요 기능 (설치 후, target repo에서 사용)

설치 후에는 target repo에서 아래처럼 사용합니다:
- (권장) 레포 자동 설정(한 번): `python3 scripts/vibe.py configure --apply`
- 진단/요약 생성: `python3 scripts/vibe.py doctor --full`
  - 출력: `.vibe/context/LATEST_CONTEXT.md`, `.vibe/reports/*` (gitignore 권장)
- 변경 감시(선택): `python3 scripts/vibe.py watch`
- 컨텍스트 DB 검색: `python3 scripts/vibe.py search "<query>"`
- 영향도(간단) 분석: `python3 scripts/vibe.py impact <path>`
- (설계/경계 점검) 아키텍처 경계 위반 체크: `python3 scripts/vibe.py boundaries` (config-driven)
  - 시작 템플릿 생성(안전/멱등): `python3 scripts/vibe.py boundaries --init-template`
  - 엄격 모드(위반 시 항상 non-zero): `python3 scripts/vibe.py boundaries --strict`
- (설계/디커플링 도움) 변경 결합(change coupling): `python3 scripts/vibe.py coupling`
  - (옵션) 리네임/이동 보정: `python3 scripts/vibe.py coupling --detect-renames`
  - (옵션) 포맷팅/대량 수정 커밋 노이즈 완화: `python3 scripts/vibe.py coupling --max-churn-per-commit 5000`
  - playbooks 문서: `.vibe/reports/decoupling_suggestions.md`
- 에이전트에 주기 위한 요약팩: `python3 scripts/vibe.py pack --scope=staged|changed|path|recent --out .vibe/context/PACK.md`
- 에이전트 지시문 진입점 점검: `python3 scripts/vibe.py agents doctor`
  - CI/게이트용: `python3 scripts/vibe.py agents doctor --fail`
- Git hook(선택): `python3 scripts/vibe.py hooks --install` (pre-commit에 `.vibe/brain/precommit.py` 연결)
- 레포별 커스텀(선택): `.vibe/config.json`에서 `exclude_dirs`, `include_globs`, `quality_gates`, `checks` 등을 조정

### 4) 레포별 커스텀의 핵심

- `vibe-kit`은 “우리 레포 구조/스택”에 맞게 설정을 바꿔 쓰는 것이 전제입니다.
- 기본 커스텀 포인트:
  - 스캔 범위: `exclude_dirs`, `include_globs`
  - 품질 게이트: `quality_gates.*`
  - 커맨드 기반 체크: `checks.doctor`, `checks.precommit`
  - 경계 규칙(금지 의존성): `architecture.rules` (예: domain이 infra를 직접 import 못 하게)

### 5) (유지보수자용) 새 릴리즈 만드는 법

이 레포에서 릴리즈 산출물 생성:
- `python3 scripts/make_release_assets.py <version> --out-dir dist/<version> --force`

그 다음:
- GitHub Release를 만들고(태그 포함) 위 3개 파일을 assets로 업로드
- `SHA256SUMS` 내용을 릴리즈 노트에 그대로 붙여 넣기
- Drive 미러를 쓸 경우: Drive는 미러, GitHub Release SHA256이 검증 기준임을 공지 (자세한 템플릿은 `RELEASE_CHECKLIST.md`)

## What this is (and isn't)

Think of this as a distribution/publisher repo:
- `vibe-kit-seed` (this repo): builds and publishes the seed artifacts (`VIBEKIT_SEED-...md`, installer, `SHA256SUMS`)
- `vibe-kit` (installed into a target repo): a small **repo-local** toolkit that helps humans/agents get project context fast

What vibe-kit does (in the *target* repo after install):
- Builds a local index of the repo (SQLite) and writes summaries under `.vibe/context/`
- Produces lightweight context packs for LLMs (e.g. `.vibe/context/LATEST_CONTEXT.md`)
- Writes reports under `.vibe/reports/` (gitignored)

### vibe-kit commands (after install, in the target repo)

- `python3 scripts/vibe.py configure --apply`: auto-detect repo stack and update `.vibe/config.json` (recommended once)
  - typecheck recommendation auto-detection supports common stacks (`dotnet`, `node` with package manager, `go`, `rust`, `maven`, `gradle`, `mypy`/`pyright` when configured)
- `python3 scripts/vibe.py doctor --full`: scan + reports, refresh `.vibe/context/LATEST_CONTEXT.md`
- `python3 scripts/vibe.py search "<query>"`: full-text search in the local context DB
- `python3 scripts/vibe.py pack --scope=...`: generate a compact `.vibe/context/PACK.md` for an agent
- `python3 scripts/vibe.py impact <path>`: quick impact analysis for a file
- `python3 scripts/vibe.py boundaries`: boundary/architecture rule checker (config-driven)
  - `python3 scripts/vibe.py boundaries --init-template`: write starter `architecture.rules` template into `.vibe/config.json` (safe/idempotent)
  - `python3 scripts/vibe.py boundaries --strict`: return non-zero on any violation, even with `--best-effort`
- `python3 scripts/vibe.py coupling`: change coupling report (files that tend to change together; useful for refactoring/decoupling)
- `python3 scripts/vibe.py watch`: keep context refreshed while you work (watchdog if installed; otherwise polling)
- `python3 scripts/vibe.py hooks --install`: optional git hook installer
- Customize per-repo settings in `.vibe/config.json` (`exclude_dirs`, `include_globs`, `quality_gates`, `checks`, etc.)

What vibe-kit does **not** do:
- It is **not** a UI/app starter template.
- It is **not** an AI agent runner/sandbox.
- It is **not** a release/packaging system for your app (e.g. Windows EXE distribution).
- It makes **no network/API calls** by default.
- The installer **does not auto-run** any extracted scripts.

## Recommended distribution model

- **Source of truth:** GitHub Releases (tagged versions)
- **Mirror:** Google Drive (optional). Treat as untrusted; always verify against the GitHub Release SHA256.

### Release provenance attestation

This repo supports GitHub artifact provenance attestation for release assets via `.github/workflows/release-attestation.yml` (`actions/attest-build-provenance@v3`).
The workflow attests the exact files uploaded to GitHub Releases (trigger: `release.published`), and `workflow_dispatch` can attest an existing release by `release_tag`.

Consumers can verify downloaded assets with GitHub CLI:
- `gh attestation verify ./VIBEKIT_SEED-<version>-<sha256>.md -R <owner>/<repo> --signer-workflow github.com/<owner>/<repo>/.github/workflows/release-attestation.yml`
- `gh attestation verify ./vibekit_seed_install.py -R <owner>/<repo> --signer-workflow github.com/<owner>/<repo>/.github/workflows/release-attestation.yml`
- `gh attestation verify ./SHA256SUMS -R <owner>/<repo> --signer-workflow github.com/<owner>/<repo>/.github/workflows/release-attestation.yml`

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
   - Note: `--expected-seed-sha256` must be the seed file hash from `SHA256SUMS` (not the internal payload hash shown inside the seed body).
   - If sharing with an AI agent, provide only the instruction/header section and exclude the base64 payload block between `VIBEKIT_PAYLOAD_BASE64_BEGIN/END`.

4) Optional global automation:
   - One-shot bootstrap from Releases (download + checksum verify + install):
     - `python3 vibekit_seed_install.py bootstrap --root . --apply --run-setup --post-configure --post-doctor --post-hooks --write-ci-guard --agent all`
     - Pin a specific tag: `python3 vibekit_seed_install.py bootstrap --tag v1.2.3 --root . --apply`
   - Install global opt-in hook for future repos:
     - `python3 vibekit_seed_install.py install-global-hook`
     - Add `.vibekit.auto` at repo root to enable auto-bootstrap on first checkout.
     - Default: also installs global Codex prompt for missing vibe-kit repos (disable with `--no-install-codex-prompt`).

5) After install (in the target repo), run:
   - (recommended once) `python3 scripts/vibe.py configure --apply`
   - `python3 scripts/vibe.py doctor --full`

## Create a new seed file

From this repo root:

- Recommended: `python3 scripts/make_release_assets.py <version> --out-dir dist/<version> --force`

Then publish the generated files as GitHub Release assets (see `RELEASE_CHECKLIST.md`).
