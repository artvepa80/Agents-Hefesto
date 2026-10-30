# Patterns that often indicate drift

This page is guidance only. "Semantic drift" is not a finding type: Hefesto
has no `SEMANTIC_DRIFT` issue type and does not check whether a change matches
its author's intent.

Semantic drift is when a code change compiles, passes tests and looks clean
to a linter, but quietly changes what the program does: an authorization
check, an invariant, a contract or a business rule.

Some of the findings Hefesto does report often show up next to that kind of
change. Treat them as places to look, not as proof of drift.

## Findings worth a second look

These run in the free tier on Python files:

- **INCOMPLETE_TODO** (LOW): a `TODO`, `FIXME`, `HACK` or `XXX` comment. After
  an AI refactor it can mark work the assistant noticed and skipped.
- **BARE_EXCEPT** (MEDIUM): a bare `except:` that catches every exception and
  can hide a behavior change.
- **ASSERT_IN_PRODUCTION** (MEDIUM): an `assert` guarding an invariant. Python
  removes asserts when run with `-O`, so the check silently disappears.

### Phase 1 — ML Semantic Analysis (local embeddings, PRO only, HEFESTO_TIER=professional|omega)

**DUPLICATE_CODE** flags two Python functions that are nearly the same, which
can mean one copy was updated and the other was not. It uses local
`sentence-transformers` embeddings (no external AI provider, no code leaves
the machine). It runs only when `hefesto-ai[pro]` is installed and
`HEFESTO_TIER` is `professional` or `omega`; otherwise it is skipped.

## Example

```
[LOW] INCOMPLETE_TODO at payments/processor.py:142
  TODO found: restore idempotency check after refactor
  Suggestion: Either complete the TODO or create a tracked issue and remove the comment
```

The TODO is the finding. Whether the refactor dropped a check that mattered
is something a person has to confirm by reading the diff.

## What to do with these findings

1. **INCOMPLETE_TODO**: read the comment; it says what was skipped. Implement
   it, or confirm the removal was intentional and track it in an issue.
2. **BARE_EXCEPT**: catch specific exception types.
3. **ASSERT_IN_PRODUCTION**: replace with an explicit check that raises.
4. **DUPLICATE_CODE**: unify the two functions or document why they differ.

## CI gate

```bash
# Fail on any HIGH or CRITICAL finding. There is no drift-specific filter:
# --fail-on applies to every finding type.
hefesto analyze . --fail-on HIGH --exclude tests/
```

Exit code 1 = gate failure (findings at or above the threshold).
Exit code 0 = clean.
