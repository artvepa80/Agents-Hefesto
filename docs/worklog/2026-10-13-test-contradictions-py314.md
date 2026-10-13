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

## Addition (16:5x Lima): zero checked files is never PASS
- Reproduced on main (b6bdc4e…25177d5) and on the previous head eb100a5, Python 3.13 and 3.14:
  an empty directory → PASS exit 0; a directory whose only file is unparseable → PASS exit 0
  (eb100a5 already listed "Skipped 1").
- Tests first (7253959): empty directory and all-skipped → "No test files were checked",
  "N skipped", exit 2; one good file + one bad → PASS exit 0, `checked_files == 1`.
- `test_print_report_no_contradictions` asserted PASS with nothing checked; it now sets
  `checked_files = 1` (it tests the PASS text, not the zero case).
- Classifiers 3.13 and 3.14 in pyproject.toml.
- Results: tests/validators 42 passed on 3.13 and 3.14; CLI on both: exit 2 in both cases.
- ~~Note: the 100 contradictions were hidden by the 3.14 bug.~~ **Correction:** that's wrong.
  `check-test-contradictions tests` gives "Total: 100 contradiction(s)" on Python 3.13
  with main and with PyPI 4.16.0 (Python 3.13.5). They were never hidden: they are false
  positives from comparing calls whose arguments are local names (e.g. `len(issues) == 1` vs
  `len(issues) == 3` in different tests).

## Addition (17:5x Lima): conservative comparison
- Rule: compare only when the call target is an `ast.Name` (plain function) and every argument
  (positional and keyword) is a literal: `ast.Constant` or a List/Tuple of Constants. Not
  compared: names, attributes, calls, `*args`/`**kw`, dicts, methods (`obj.f`, `self.f`).
  Applied the same way to `assert f(...) == x` and to unittest `assertEqual/assertTrue/assertFalse`.
- Tests first: add(1, 2) == 3 vs == 4 still reported (also with kwargs and list/tuple
  literals); len(issues), len(result.issues), len(get()), obj.add/self.add, *args, **kw,
  [1, x], {1: 2} not reported; assertEqual follows the same rule; our own tests/ → 0.
- Results: tests/validators 56 passed on 3.13 and 3.14; full suite on 3.13: 1272 passed;
  `hefesto check-test-contradictions tests` → PASS, exit 0 (was 100, exit 1).
