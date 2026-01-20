# Security

## Threat model (what we defend against)

- Mirrors (Google Drive, etc.) are mutable: a shared file can be replaced after the link is distributed.
- “Helpful” agents can execute commands automatically when given an install doc.
- Zip extraction is dangerous if paths are not validated (e.g. `../` traversal).

## Guarantees and non-goals

- Releases should be immutable: consumers can pin to a tag and verify SHA256.
- The installer **does not auto-run** any scripts after extracting files.
- The installer rejects unsafe zip entry paths and only extracts known allowlisted files.

## Operator guidance (publishers)

- Publish `VIBEKIT_SEED-<version>-<sha>.md`, `vibekit_seed_install.py`, and `SHA256SUMS` in the same GitHub Release.
- If you use a Drive mirror, mirror exact assets only; updates must be **new files/new links**.

## User guidance (consumers)

- Prefer downloading from GitHub Releases.
- If using a mirror, verify SHA256 against the GitHub Release before installing.
- Review the extracted files before running any of them in your repo.

