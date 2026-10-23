# Semantic Drift Detection

## Definition

Semantic drift is when a code change compiles, passes tests, and looks clean
to traditional linters — but silently alters the intended behavior of the
program. Authorization logic, invariants, contracts, security posture, or
business rules change without anyone noticing.

Traditional tools catch syntax errors and style violations.
HefestoAI catches meaning changes.

## How HefestoAI Detects It

### Phase 0 — Deterministic Static Analysis

HefestoAI's static analyzers flag patterns that commonly cause semantic drift:

- **INCOMPLETE_TODO**: A TODO/FIXME/HACK comment left by an AI refactor —
  indicates the AI acknowledged unfinished work but proceeded anyway.
- **DEAD_CODE**: Functions or variables that became unreachable after
  refactoring — often the original correct implementation.
- **BARE_EXCEPT**: Broad exception handlers that swallow errors silently,
  hiding behavioral changes.
- **ASSERT_IN_PRODUCTION**: Assertions that guard invariants but get
  stripped in optimized builds.

### Phase 1 — ML Semantic Analysis (PRO/OMEGA)

Uses function-level embeddings to detect semantic duplication:
two functions that do nearly the same thing but diverged over time.
This catches copy-paste drift where one copy gets updated and the other doesn't.

Runs only when `HEFESTO_TIER=professional` or `HEFESTO_TIER=omega`.

## Real-World Example: The TODO That Saved K

An AI assistant refactored a payment module. The code compiled, tests passed,
PR looked clean. HefestoAI flagged:

```
INCOMPLETE_TODO (MEDIUM) at payments/processor.py:142
  Message: TODO/FIXME comment indicates incomplete implementation
  Code: # TODO: restore idempotency check after refactor
  Suggestion: Resolve the TODO before committing
```

The AI had removed an idempotency check that had existed for 8 months.
Without it, duplicate charges would have gone to production.
Traditional linters saw clean code. HefestoAI caught the behavioral gap.

## What the Output Looks Like

```
hefesto analyze src/ --fail-on HIGH

HEFESTO ANALYSIS PIPELINE
==================================================

Running static analyzers...
   Found 3 potential issue(s)

[MEDIUM] INCOMPLETE_TODO at src/auth.py:89
  TODO/FIXME comment indicates incomplete implementation
  Code: # FIXME: verify token expiry was removed during refactor
  Suggestion: Resolve the TODO before committing

[HIGH] DEAD_CODE at src/auth.py:45
  Function 'verify_token_expiry' appears to be unused
  Suggestion: Remove if intentionally dead, or restore caller
```

## How to Fix Detected Drift

1. **INCOMPLETE_TODO**: Read the TODO text. It tells you what the AI skipped.
   Implement the missing logic or confirm removal was intentional.

2. **DEAD_CODE**: Check git blame. If the function was recently made dead by
   an AI refactor, the caller was likely removed by accident. Restore it.

3. **BARE_EXCEPT**: Replace with specific exception types. If the AI added
   a catch-all to "handle errors gracefully," it's hiding real failures.

4. **Semantic duplicates** (Phase 1): Two functions doing almost the same
   thing means one diverged. Unify them or document why they differ.

## CI Gate for Drift

```bash
# Block merges if any HIGH+ semantic drift indicators are found
hefesto analyze . --fail-on HIGH --exclude tests/
```

Exit code 1 = gate failure (issues found at or above threshold).
Exit code 0 = clean.
