#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_file(src: Path, dest: Path, *, force: bool) -> None:
    if dest.exists() and not force:
        raise SystemExit(f"exists: {dest} (use --force to overwrite)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Create immutable vibe-kit seed release assets.")
    ap.add_argument("version", help="Version string (e.g. 1.2.3).")
    ap.add_argument("--out-dir", default="dist", help="Output directory (relative to repo root).")
    ap.add_argument("--force", action="store_true", help="Overwrite existing outputs.")
    args = ap.parse_args(argv)

    root = _repo_root()
    out_dir = (root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    tmp_seed = out_dir / f"VIBEKIT_SEED-{args.version}.md"
    cmd = [
        sys.executable,
        str(root / "scripts" / "vibe.py"),
        "seed",
        f"--out={tmp_seed}",
        "--force",
    ]
    subprocess.check_call(cmd, cwd=str(root))

    seed_sha = _sha256_file(tmp_seed)
    seed_name = f"VIBEKIT_SEED-{args.version}-{seed_sha}.md"
    seed_path = out_dir / seed_name
    if seed_path.exists() and not args.force:
        raise SystemExit(f"exists: {seed_path} (use --force to overwrite)")
    if seed_path.exists():
        seed_path.unlink()
    tmp_seed.rename(seed_path)

    installer_src = root / "vibekit_seed_install.py"
    installer_dst = out_dir / "vibekit_seed_install.py"
    _copy_file(installer_src, installer_dst, force=bool(args.force))

    sha_sums = out_dir / "SHA256SUMS"
    if sha_sums.exists() and not args.force:
        raise SystemExit(f"exists: {sha_sums} (use --force to overwrite)")

    installer_sha = _sha256_file(installer_dst)
    sha_sums.write_text(
        f"{seed_sha}  {seed_name}\n{installer_sha}  vibekit_seed_install.py\n",
        encoding="utf-8",
    )

    print("[release] wrote:")
    print(f"  - {seed_path}")
    print(f"  - {installer_dst}")
    print(f"  - {sha_sums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

