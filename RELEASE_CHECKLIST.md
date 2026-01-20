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

## 3) Mirror to Google Drive (optional)

- Upload the exact same three files to a versioned folder.
- Never “replace/overwrite” an existing shared file after sharing.
- Tell users: “Drive is a mirror; verify SHA256 against the GitHub Release before installing.”

