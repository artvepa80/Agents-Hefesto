# Fix Suggestions by Issue Category

## Complexity

**HIGH_COMPLEXITY** / **VERY_HIGH_COMPLEXITY**
- Extract conditional branches into named helper functions
- Use early returns to reduce nesting
- Replace nested if/else chains with dispatch tables or strategy pattern
- Real example: `analyzer_engine.py:analyze_path` (complexity=11) --
  extract DevOps language dispatch into `_dispatch_devops_analyzer()`

## Code Smells

**LONG_FUNCTION** -- Break into focused subfunctions. Each function should
do one thing. Real example: `drift_runner.py:run` (53 lines, threshold=50).

**DEEP_NESTING** -- Invert conditions with early returns. Real example:
`analyzer_engine.py:_analyze_file` (nesting level 6, threshold 4).

**DEAD_CODE** -- Verify with git blame. If recently orphaned by AI refactor,
restore the caller. If intentionally unused, delete entirely.

**DUPLICATE_CODE** -- Extract shared logic into a common function.

**GOD_CLASS** -- Split responsibilities into separate classes.

**INCOMPLETE_TODO** -- Resolve the TODO or document why it stays.

**MAGIC_NUMBER** -- Extract into named constant with clear intent.

**LONG_PARAMETER_LIST** -- Group into a config dataclass or dict.

## Security

**HARDCODED_SECRET** -- Move to environment variable or secrets manager.
**SQL_INJECTION_RISK** -- Use parameterized queries, never f-strings.
**EVAL_USAGE** -- Replace with ast.literal_eval or structured parsing.
**PICKLE_USAGE** -- Use JSON or msgpack for untrusted data.
**ASSERT_IN_PRODUCTION** -- Replace with if/raise (asserts stripped with -O).
**BARE_EXCEPT** -- Catch specific exceptions: `except (ValueError, KeyError)`.

## Reliability Drift (R1-R5)

**R1 RELIABILITY_UNBOUNDED_GLOBAL** -- Move mutable into function scope
or use `lru_cache(maxsize=N)`.

**R2 RELIABILITY_UNBOUNDED_CACHE** -- Set explicit maxsize on `@lru_cache`.

**R3 RELIABILITY_SESSION_LIFECYCLE** -- Use `with Session() as s:` pattern.

**R4 RELIABILITY_LOGGING_HANDLER_DUP** -- Configure handlers at module level.

**R5 RELIABILITY_THREAD_IN_REQUEST** -- Use `ThreadPoolExecutor(max_workers=N)`.

## Best Practices

**MISSING_DOCSTRING** -- Add one-line summary for public functions.
**POOR_NAMING** -- Use descriptive names: `process_data` not `pd`.
**STYLE_VIOLATION** -- Run formatter (black/ruff) to auto-fix.

## DevOps (YAML, Shell, Dockerfile, Terraform, SQL)

See [issue_types.md](../issue_types.md) for the full list.
General pattern: each DevOps issue includes a suggestion field
with the specific fix. Follow it directly.
