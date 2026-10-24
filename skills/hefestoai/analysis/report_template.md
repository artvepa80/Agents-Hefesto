# Commit Quality Report Template

Use this format after every `hefesto analyze` run.

## Template

```markdown
## HefestoAI Analysis -- [YYYY-MM-DD HH:MM UTC]

**Scope**: [paths analyzed]
**Files**: [N] | **Issues**: [N] | **LOC**: [N] | **Duration**: [N]s
**Gate**: [PASSED/FAILED] (threshold: [--fail-on value or "none"])

### Critical (must fix before commit)
- [TYPE] in [file:line] ([function]) -- [1-line fix]

### High (should fix before merge)
- [TYPE] in [file:line] ([function]) -- [1-line fix]

### Medium (fix when convenient)
- [TYPE] in [file:line] ([function]) -- [1-line fix]

### Summary
[Total] issues: [N critical], [N high], [N medium], [N low]
Action: [commit blocked / commit clean / issues noted]
```

## Real Example (from hefesto/core/)

```markdown
## HefestoAI Analysis -- 2026-02-28 19:45 UTC

**Scope**: hefesto/core/
**Files**: 20 | **Issues**: 23 | **LOC**: 2585 | **Duration**: 0.33s
**Gate**: PASSED (threshold: none)

### Critical (must fix before commit)
(none)

### High (should fix before merge)
- HIGH_COMPLEXITY in analyzer_engine.py:102 (analyze_path) -- extract method
- HIGH_COMPLEXITY in analyzer_engine.py:216 (_analyze_file) -- extract method
- DEEP_NESTING in analyzer_engine.py:216 (_analyze_file) -- early returns
- HIGH_COMPLEXITY in parsers/parser_factory.py:32 (get_parser) -- dispatch table
- GOD_CLASS in models.py:25 (HefestoConfig) -- split into sub-configs
- LONG_FUNCTION in models.py:25 (HefestoConfig) -- extract validators
- LONG_FUNCTION in models.py:313 (ScopeGatingConfig) -- extract validators

### Medium (fix when convenient)
- HIGH_COMPLEXITY x4 (drift_runner, language_detector, parsers)
- LONG_FUNCTION x5 (drift_runner, ast, languages, providers)
- LONG_PARAMETER_LIST x3 (providers)
- INCOMPLETE_TODO x4

### Summary
23 issues: 0 critical, 7 high, 16 medium, 0 low
Action: commit clean (no gate threshold set)
```

## Clean Commit Summary (for HERMES)

When gate passes with 0 issues:
```
[N] files analyzed, 0 issues -- clean commit
```

When issues found and fixed before commit:
```
Caught [N] issues before production -- [top issue type] in [file]
```

When gate blocks commit:
```
Pre-commit blocked: [N] [severity]+ issues in [file(s)]
```
