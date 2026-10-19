# 2026-10-19 — pr-review: function-level findings count when the body changes (draft PR, not merged)

## Request
Code Gate triage, finding 4 (P1). Plan approved by Arturo 2026-10-19 09:58 Lima ("sigamos con tu plan"). Merge needs Arturo's OK (GH-8: not the day it opens).

## Bug
`hefesto/pr_review/orchestrator.py` compared only `issue.line` with the diff's added lines. Complexity, long-function and deep-nesting findings are reported on the `def` line (`complexity.py:50`, `code_smells.py`), so a PR that changed a function's body without touching its `def` line never surfaced them in default mode. PR #146 raised `load_upsell_state` from complexity 10 (MEDIUM) to 11 (HIGH) through body edits (hunks `+129,6` and `+157,23`, `def` at 125) and `pr-review` reported nothing.

## Fix
- `AnalysisIssue.end_line` (optional, not in `to_dict`, so `analyze` JSON/SARIF output is unchanged). Set from the AST node's `line_end` for HIGH_COMPLEXITY / VERY_HIGH_COMPLEXITY, LONG_FUNCTION and DEEP_NESTING.
- `_hunk_anchor(issue, added_lines)`: `issue.line` if it was added; otherwise the first added line in `[line, end_line]`; otherwise `None`. `in_hunk = anchor is not None`.
- Finding JSON: new key `anchor_line` (int, or `null` when `in_hunk` is false). `line` and `dedup_key` unchanged.
- `--post` and the deduped workflow template post on `anchor_line`, falling back to `line`.

## Edge cases (tests in `tests/test_pr_review_function_span.py`)
| Case | Result |
|---|---|
| Body edit, `def` untouched (#146 shape, 10 → 11) | in hunk, `line` = def, `anchor_line` = first added line |
| Edit after or above the function | not in hunk |
| Hunk only in a multi-line signature | in hunk (signature is inside the span) |
| Edit only on a decorator line | not in hunk: Python's AST starts the function at `def`; decorators do not change these metrics |
| Body edit in a decorated function | in hunk, `line` = def line (not the decorator) |
| Edit inside a nested function | both outer and inner surface (outer complexity counts inner branches) |
| Edit in outer, outside inner's span | only outer |
| Deletion-only hunk inside the body | not in hunk: no new-side line to anchor on, and deleting lines cannot raise these metrics |

Not covered on purpose: LONG_PARAMETER_LIST (signature-level) and GOD_CLASS (class-level; any edit in a large class would surface it). Both still use the line-only match.

## Contract
`anchor_line` is a new key in the OSS → Pro finding schema (`tests/test_pr_review_schema_contract.py`, which now also checks the real serializer). Pro's `_DETERMINISTIC_KEYS` and `_finding()` fixture should add it.
