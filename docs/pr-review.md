# `hefesto pr-review`

`hefesto pr-review` analyzes only the files a pull request touches and emits
JSON findings with stable dedup keys, ready to post as inline review comments.

## How it runs

1. Parses `git diff` between base and head (`--base`; auto-detects
   `origin/main` or `GITHUB_BASE_REF`).
2. Runs the full analyzer suite on the touched files.
3. Keeps findings on changed lines (default) or all findings in the touched
   files (`--strict`).
4. Emits JSON; `--post` posts the findings through `gh` (not idempotent; use
   the deduped workflow template for repeated runs).

## Finding fields

| Field | Meaning |
|-------|---------|
| `file` | Repository-relative path. |
| `line` | Line the finding is reported on. For function-level findings (complexity, long function, deep nesting) this is the `def` line. |
| `column`, `type`, `severity`, `message`, `suggestion`, `code_snippet`, `engine`, `rule_id` | Finding details, as in `hefesto analyze`. |
| `dedup_key` | SHA256 key built from the finding and its relative path. It uses `line`, so it does not move when a function body is edited. |
| `in_hunk` | `true` when the finding touches an added line of the diff. |
| `anchor_line` | The added line an inline comment should be posted on, or `null` when `in_hunk` is `false`. |

## Line suppressions

Python findings suppressed with `# hefesto: ignore[TYPE] reason` (up to HIGH,
never CRITICAL; see `docs/ANALYSIS_RULES.md`) are not in `findings`.
`diagnostics.suppressed` counts them and `diagnostics.suppression_warnings`
lists directives that suppressed nothing.

So that a suppression cannot land unnoticed, the output lists every
suppression comment the diff adds to a `.py` file, also on stderr:

```json
"new_suppressions": [
  {"file": "pkg/cache.py", "line": 12, "types": ["PICKLE_USAGE"], "reason": "signed cache"}
]
```

A malformed one also carries `problem`. `--fail-on-new-suppressions` exits 1
when the list is not empty (after printing the JSON), so a CI job can require
a review for new suppressions.

## `anchor_line`

GitHub rejects review comments (HTTP 422) on lines outside the diff. A
function-level finding is reported on the `def` line, which a PR that only
edits the function body does not change. Such a finding counts as in the hunk
when any added line falls inside the function (from the `def` line to its last
line; decorators and deletion-only hunks do not count), and `anchor_line`
gives the line to comment on:

- line-level findings: `anchor_line` equals `line` when that line was added;
- function-level findings: the first added line inside the function;
- findings outside the diff (only visible with `--strict`): `null`.

`line` and `dedup_key` stay the same, so existing dedup state keeps working.
Long parameter lists and god classes still match on their own line only.
`hefesto analyze` output does not include `anchor_line`.

When posting, use `anchor_line` and fall back to `line` for JSON produced by
versions without the field:

```bash
line=$(jq -r '.anchor_line // .line' <<< "$finding")
```

`--post` and `examples/github-actions/hefesto-pr-review-deduped.yml` already
do this. See [`examples/github-actions/README.md`](../examples/github-actions/README.md)
for the workflow templates.
