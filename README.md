# vibe-kit (seed distribution)

This repo publishes **immutable** `VIBEKIT_SEED*.md` release artifacts and a standalone installer script.

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

4) (Optional) After install, run:
   - `python3 scripts/vibe.py doctor --full`

## Create a new seed file

From this repo root:

- Recommended: `python3 scripts/make_release_assets.py <version> --out-dir dist/<version> --force`

Then publish the generated files as GitHub Release assets (see `RELEASE_CHECKLIST.md`).
