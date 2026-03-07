#!/usr/bin/env python3
from __future__ import annotations

import re

from symbol_types import Symbol


DECL_RE = re.compile(
    r"^\s*(?P<export>export\s+)?(?P<default>default\s+)?(?:(?P<async>async)\s+)?"
    r"(?P<kind>function|class|interface|type|enum|const|let|var)\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"(?P<rest>.*)$",
    re.MULTILINE,
)


def _line_number(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def _tags_from_text(text: str | None, critical_tags: list[str]) -> list[str]:
    if not text:
        return []
    return [tag for tag in critical_tags if tag in text]


def _extract_preceding_comment(lines: list[str], decl_line_idx: int) -> str | None:
    doc_lines: list[str] = []
    i = decl_line_idx - 1
    in_block = False
    while i >= 0:
        raw = lines[i].rstrip()
        stripped = raw.strip()
        if not stripped:
            if doc_lines:
                break
            i -= 1
            continue
        if stripped.startswith("//"):
            doc_lines.append(stripped[2:].strip())
            i -= 1
            continue
        if stripped.endswith("*/"):
            in_block = True
            cleaned = stripped[:-2].strip()
            if cleaned.startswith("/**"):
                cleaned = cleaned[3:].strip()
                if cleaned:
                    doc_lines.append(cleaned.lstrip("*").strip())
                break
            if cleaned:
                doc_lines.append(cleaned.lstrip("*").strip())
            i -= 1
            continue
        if in_block:
            cleaned = stripped
            if cleaned.startswith("/**"):
                cleaned = cleaned[3:].strip()
                if cleaned:
                    doc_lines.append(cleaned.lstrip("*").strip())
                break
            doc_lines.append(cleaned.lstrip("*").strip())
            i -= 1
            continue
        break
    doc_lines = [line for line in reversed(doc_lines) if line]
    if not doc_lines:
        return None
    return "\n".join(doc_lines).strip()


def _signature(kind: str, name: str, rest: str, is_async: bool) -> str:
    compact_rest = " ".join(rest.strip().split())
    if kind == "function":
        prefix = "export " if rest.strip().startswith("{") else ""
        async_prefix = "async " if is_async else ""
        return f"{async_prefix}function {name}{compact_rest}".strip()
    if kind in {"class", "interface", "type", "enum"}:
        return f"{kind} {name}{compact_rest}".strip()
    if kind in {"const", "let", "var"}:
        return f"{kind} {name}{compact_rest}".strip()
    return f"{kind} {name}".strip()


def extract_symbols_ts(text: str, rel_file: str, critical_tags: list[str]) -> list[Symbol]:
    lines = text.splitlines()
    symbols: list[Symbol] = []
    seen: set[tuple[str, int]] = set()

    for match in DECL_RE.finditer(text):
        kind = match.group("kind")
        name = match.group("name")
        rest = match.group("rest") or ""
        line = _line_number(text, match.start())
        exported = 1 if match.group("export") else 0
        access = "public" if exported else "private"
        if kind in {"let", "var"} and "=>" not in rest and "function" not in rest:
            continue
        if kind == "const" and "=>" not in rest and "function" not in rest:
            continue
        if (name, line) in seen:
            continue
        seen.add((name, line))
        doc = _extract_preceding_comment(lines, line - 1)
        attrs: list[str] = []
        if exported:
            attrs.append("export")
        if match.group("default"):
            attrs.append("default")
        if match.group("async"):
            attrs.append("async")
        symbol_kind = kind
        if kind in {"const", "let", "var"}:
            symbol_kind = "variable"
        symbols.append(
            Symbol(
                name=name,
                file=rel_file,
                line=line,
                kind=symbol_kind,
                signature=_signature(kind, name, rest, is_async=bool(match.group("async"))),
                access=access,
                doc=doc,
                tags=_tags_from_text(doc, critical_tags),
                attrs=attrs,
                exported=exported,
            )
        )

    return symbols
