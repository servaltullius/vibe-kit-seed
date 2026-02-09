# Release checklist (vibe-kit seed)

## 1) Build release assets

From repo root:

- `python3 scripts/make_release_assets.py <version> --out-dir dist/<version> --force`

This produces:
- `dist/<version>/VIBEKIT_SEED-<version>-<sha256>.md`
- `dist/<version>/vibekit_seed_install.py`
- `dist/<version>/SHA256SUMS`

## 2) Publish GitHub Release (source of truth)

1) Create a new tag (e.g. `v1.2.3`) and GitHub Release.
2) Upload the three files above as Release assets.
3) Paste `SHA256SUMS` contents into the Release notes.

## 3) Generate provenance attestation (recommended)

Use the workflow `.github/workflows/release-attestation.yml` (safe/manual trigger).

1) In Actions, run `release-attestation` via `workflow_dispatch` with `version=<version>`.
2) The workflow rebuilds `dist/<version>/` using `scripts/make_release_assets.py`.
3) It attests the 3 release files with `actions/attest-build-provenance@v3`.
4) It uploads `release-assets-<version>` as a workflow artifact for maintainer download.

Verification examples (consumer side, after downloading assets):

- `gh attestation verify ./VIBEKIT_SEED-<version>-<sha256>.md -R <owner>/<repo>`
- `gh attestation verify ./vibekit_seed_install.py -R <owner>/<repo>`
- `gh attestation verify ./SHA256SUMS -R <owner>/<repo>`
- Optional JSON output: `gh attestation verify ./SHA256SUMS -R <owner>/<repo> --format json`

## 4) Mirror to Google Drive (optional)

- Upload the exact same three files to a **versioned** folder (e.g. `v1.2.3/`):
  - `VIBEKIT_SEED-<version>-<sha256>.md`
  - `vibekit_seed_install.py`
  - `SHA256SUMS`
- Never “replace/overwrite” an existing shared file after sharing (treat mirrors as immutable).
- Tell users: “Drive is a mirror; GitHub Releases is the source of truth; verify SHA256 before installing.”

### Copy/paste announcement (Korean)

```
vibe-kit-seed 미러(Drive) 공유합니다. (GitHub Releases가 진짜 소스, Drive는 미러)

1) GitHub Release(소스/검증 기준):
   - <GITHUB_RELEASE_URL>

2) Drive Mirror(편의용 다운로드):
   - <DRIVE_FOLDER_URL>

3) 다운로드 파일(같은 버전 폴더에서 3개):
   - VIBEKIT_SEED-<version>-<sha256>.md
   - vibekit_seed_install.py
   - SHA256SUMS

4) SHA256 검증(반드시 수행):
   - Linux/macOS: 같은 폴더에서 `sha256sum -c SHA256SUMS`
   - Windows(PowerShell):
     - `Get-FileHash .\\VIBEKIT_SEED-...md -Algorithm SHA256`
     - `Get-FileHash .\\vibekit_seed_install.py -Algorithm SHA256`
     - 결과 Hash를 SHA256SUMS의 첫 컬럼(해시)과 비교

5) 설치(검증 후, target repo에서):
   - dry-run: `python3 vibekit_seed_install.py install VIBEKIT_SEED-...md --root . --expected-seed-sha256 <sha256>`
   - apply:   `python3 vibekit_seed_install.py install VIBEKIT_SEED-...md --root . --expected-seed-sha256 <sha256> --apply`
```
