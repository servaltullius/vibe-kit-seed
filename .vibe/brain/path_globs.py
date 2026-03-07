#!/usr/bin/env python3
from __future__ import annotations

from pathlib import PurePosixPath


def matches_include_globs(rel_posix: str, include_globs: list[str]) -> bool:
    if not include_globs:
        return True

    path = PurePosixPath(rel_posix)
    for pattern in include_globs:
        if path.match(pattern):
            return True
        if pattern.startswith("**/") and path.match(pattern[3:]):
            return True
    return False
