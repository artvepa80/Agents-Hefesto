# HERMES Integration

How auto-analysis results feed into HERMES content generation.

## Connection Points

HefestoAI analysis results map to 3 HERMES content scenarios:

### 1. Clean Commit Post

**Trigger**: `hefesto analyze` exits 0, total_issues == 0.
**Content type**: build_in_public
**Template**:
```
[N] files, [LOC] lines scanned. Zero issues.
HefestoAI pre-commit gate: clean pass.
[Optional: language breakdown or duration stat]
#BuildInPublic
```
**Staging**: Auto-stage as candidate in content_generator.py.
Arturo reviews before publishing.

### 2. Caught-Before-Production Post

**Trigger**: Issues found, developer fixes them, then commits clean.
**Content type**: build_in_public
**Template**:
```
Caught [N] [top_severity] issues before they hit production.
[Top issue]: [1-line description in plain English].
This is why pre-commit hooks exist.
#BuildInPublic #CodeQuality
```
**Example** (from real output):
```
Caught 7 HIGH issues in hefesto/core/ before merge.
Top finding: cyclomatic complexity of 11 in analyze_path --
too many branches for reliable testing.
Refactored into 3 focused methods. Clean now.
```

### 3. Blocked Commit Post

**Trigger**: `hefesto analyze --fail-on HIGH` exits 1.
**Content type**: build_in_public (educational angle)
**Template**:
```
Pre-commit blocked my commit today.
[N] issues at [severity] or above in [path].
[Specific finding that's interesting/relatable].
Fixing before pushing. That's the point.
```
**Note**: Only post if the finding is technically interesting.
"Missing docstring" is not post-worthy. "Removed auth check
detected as dead code" is.

## Data Flow

```
hefesto analyze . --output json --quiet
  |
  v
Parse JSON: summary.total_issues, summary.critical, summary.high
  |
  v
Route:
  0 issues      -> clean commit template
  issues fixed  -> caught-before-production template
  gate failure  -> blocked commit template
  |
  v
Stage in content_generator.py --staging
  |
  v
Arturo reviews -> --approve or --reject
```

## Quality Filter for HERMES

Not every analysis result deserves a post. Filter:

- Skip if only LOW/MEDIUM issues (not interesting enough)
- Skip if same issue type was posted in last 7 days
- Skip if total issues < 3 (too small to be noteworthy)
- Post if CRITICAL found (always noteworthy)
- Post if issue count is a round milestone (50th, 100th clean commit)
- Post if a new issue type was caught for the first time

## Metrics for HERMES

These fields from JSON output are safe to share publicly:
- files_analyzed, total_issues, total_loc, duration_seconds
- Issue counts by severity (critical, high, medium, low)
- Issue types found (e.g., "3 HIGH_COMPLEXITY, 2 DEEP_NESTING")

Never share: file paths from private repos, code_snippet content,
exact line numbers in private code, metadata internals.
