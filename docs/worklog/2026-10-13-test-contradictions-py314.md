# 2026-10-13 — check-test-contradictions on Python 3.14

## Reproduced (HEFESTO_TELEMETRY=0, uv venvs, main b6bdc4e)
Suite: two tests `assert add(x, [1]) == 3` and `== 4`.
- Python 3.13: "Total: 1 contradiction(s)", exit 1.
- Python 3.14.8: "Test Contradiction Check: PASS", exit 0.
- `tests/validators/test_test_contradictions.py::test_extract_value_handles_lists` fails on 3.14
  (AttributeError: module 'ast' has no attribute 'Num').
Cause: `_extract_value` checked `ast.Num`/`ast.Str`/`ast.NameConstant` (removed in 3.14) after
`ast.Constant`, so any non-literal argument (a Name, a List) raised; `_parse_test_file`
had `except Exception: pass` and dropped the whole file.

## Fix
- Failing tests first (commit ddb1eb9, `tests/validators/test_test_contradictions_py314.py`):
  contradiction found with non-literal arguments; CLI exit 1; unparseable/undecodable files
  listed as skipped; an internal error exits 2 and never prints PASS.
- Only `ast.Constant`; skip only `SyntaxError`/`UnicodeDecodeError` and report the files;
  other exceptions propagate → CLI "internal error", exit 2.
- `3.14` in the lint-and-test and multilang-smoke matrices.

## Results
- tests/validators: 39 passed on 3.13 and on 3.14.
- Full suite on 3.14: 1279 passed; 1 error `test_csharp_parses_with_cold_cache`
  (`configure() got an unexpected keyword argument 'cache_dir'` with
  tree-sitter-language-pack 1.22.1), the same as on 3.13 with 1.22.1. That's the pack drift,
  not 3.14 (see the grammars CI PR).

## Not merged
Arturo decides tomorrow; otherwise it goes out in 4.17.1. Once merged, apply
`/workspace/ruleset-15985908-py314.json` (adds lint-and-test (3.14) and multilang-smoke (3.14)).
