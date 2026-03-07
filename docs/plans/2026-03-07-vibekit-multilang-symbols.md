# vibe-kit Multi-language Symbol Extraction Plan

## Goal
- Expand symbol extraction beyond C# so `search`, `pack`, `impact`, and summaries become more useful in Python and TS/TSX repositories.

## Non-goals
- Do not build a full parser for every language.
- Do not redesign dependency extraction in this slice.
- Do not add third-party parsing libraries.

## Affected Files
- `.vibe/brain/symbol_types.py`
- `.vibe/brain/symbol_extract_py.py`
- `.vibe/brain/symbol_extract_ts.py`
- `.vibe/brain/indexer.py`
- `tests/test_indexer_symbols.py`
- `README.md`

## Constraints
- Use stdlib only.
- Preserve current symbol schema.
- Keep extraction best-effort and resilient to imperfect source files.
- Prefer top-level and high-value symbols over exhaustive language coverage.

## Milestones
1. Introduce a shared `Symbol` dataclass for all extractors.
2. Add Python extraction using `ast` for classes, functions, methods, docstrings, and decorators.
3. Add TS/TSX extraction for common top-level declarations and JSDoc comments.
4. Wire extractors into `indexer.py` for `.py`, `.ts`, `.tsx`, and keep existing C# behavior.
5. Add integration-style tests and update README wording.

## Validation
- `python3 -m unittest discover -s tests -p 'test_indexer_symbols.py' -v`
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `python3 scripts/vibe.py doctor --full`

## Risks / Rollback
- Regex-based TS extraction may miss edge cases or over-match uncommon syntax.
- Python AST extraction will skip files with syntax errors by design.
- Rollback is straightforward because extraction is isolated to indexer helpers.
