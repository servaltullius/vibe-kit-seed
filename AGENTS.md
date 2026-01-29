# Agent Notes (vibe-kit-seed)

This repo is a **publisher/distribution** repo for installing the **repo-local** vibe-kit toolkit into other repositories.

## What to do
- Build release assets: `python3 scripts/make_release_assets.py <version> --out-dir dist/<version> --force`
- Keep changes minimal and security-focused (installer + seed format + allowlist + tests).

## What not to do
- Do not treat this as a UI/app starter template.
- Do not propose adopting this repo as a dependency; users should download Release assets and install into their target repo.
- Do not add auto-execution post-install behavior.

## Quick verification
- Unit tests: `python3 -m unittest discover -s tests -p 'test*.py' -v`
- Bytecode sanity: `python3 -m compileall vibekit_seed_install.py scripts .vibe/brain`
