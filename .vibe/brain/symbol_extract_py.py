#!/usr/bin/env python3
from __future__ import annotations

import ast

from symbol_types import Symbol


def _tags_from_text(text: str | None, critical_tags: list[str]) -> list[str]:
    if not text:
        return []
    return [tag for tag in critical_tags if tag in text]


def _decorator_names(node: ast.AST) -> list[str]:
    decorators: list[str] = []
    for decorator in getattr(node, "decorator_list", []):
        try:
            decorators.append(ast.unparse(decorator).strip())
        except Exception:
            continue
    return decorators


def _format_signature(node: ast.AST, *, prefix: str) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return prefix
    try:
        args = ast.unparse(node.args).strip()
    except Exception:
        args = "..."
    name = node.name
    sig = f"{prefix} {name}({args})"
    if node.returns is not None:
        try:
            sig += f" -> {ast.unparse(node.returns).strip()}"
        except Exception:
            pass
    return sig


def _access_for_name(name: str) -> tuple[str, int]:
    if name.startswith("_") and not name.startswith("__"):
        return "private", 0
    if name.startswith("__") and not name.endswith("__"):
        return "private", 0
    return "public", 1


def extract_symbols_py(text: str, rel_file: str, critical_tags: list[str]) -> list[Symbol]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    symbols: list[Symbol] = []

    def visit(body: list[ast.stmt], qual_prefix: list[str]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                access, exported = _access_for_name(node.name)
                name = ".".join([*qual_prefix, node.name]) if qual_prefix else node.name
                doc = ast.get_docstring(node)
                decorators = _decorator_names(node)
                symbols.append(
                    Symbol(
                        name=name,
                        file=rel_file,
                        line=int(getattr(node, "lineno", 1)),
                        kind="class",
                        signature=f"class {node.name}",
                        access=access,
                        doc=doc,
                        tags=_tags_from_text(doc, critical_tags),
                        attrs=decorators,
                        exported=exported,
                    )
                )
                visit(node.body, [*qual_prefix, node.name])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                access, exported = _access_for_name(node.name)
                in_class = bool(qual_prefix)
                kind = "method" if in_class else "function"
                if isinstance(node, ast.AsyncFunctionDef):
                    kind = f"async_{kind}"
                name = ".".join([*qual_prefix, node.name]) if qual_prefix else node.name
                doc = ast.get_docstring(node)
                decorators = _decorator_names(node)
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                symbols.append(
                    Symbol(
                        name=name,
                        file=rel_file,
                        line=int(getattr(node, "lineno", 1)),
                        kind=kind,
                        signature=_format_signature(node, prefix=prefix),
                        access=access,
                        doc=doc,
                        tags=_tags_from_text(doc, critical_tags),
                        attrs=decorators,
                        exported=exported,
                    )
                )

    visit(tree.body, [])
    return symbols
