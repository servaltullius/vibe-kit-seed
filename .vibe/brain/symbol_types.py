#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Symbol:
    name: str
    file: str
    line: int
    kind: str
    signature: str | None
    access: str | None
    doc: str | None
    tags: list[str]
    attrs: list[str]
    exported: int
