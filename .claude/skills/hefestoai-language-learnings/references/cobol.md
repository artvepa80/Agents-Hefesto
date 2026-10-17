# COBOL learnings

### COBOL002 flagged flag/status/length fields as credentials

- **Symptom:** COBOL002 on fields such as `WS-PASSWORD-OK-FLAG` or `PWD-LEN`.
- **Cause:** the credential-name match ignored the suffix.
- **Fix:** names ending in `-FLAG`, `-OK`, `-SW`, `-IND`, `-STATUS`, `-LEN`, `-MSG`, `-PROMPT`, ... are skipped. COBOL008 uses the same exclusions.
- **Official source:** n/a, internal behavior
- **PR/commit:** CHANGELOG 4.15.0; `docs/cobol.md`
- **Verified:** 4.15.0 (2026-10-10)
- **Status:** Fixed

### COBOL007 / COBOL015 on vendor copybooks

- **Symptom:** blast-radius or missing-copybook findings on CICS `DFH*` or DB2 `SQLCA`/`SQLDA`.
- **Cause:** vendor copybooks are never in the scanned tree.
- **Fix:** `DFH*`, IBM MQ `CMQ*`, `SQLCA` and `SQLDA` are skipped by both rules. For your own copybooks outside the tree, use `--copybook-path DIR` or `copybook_paths:`.
- **Official source:** n/a, internal behavior
- **PR/commit:** CHANGELOG 4.15.0; `docs/cobol.md`
- **Verified:** 4.15.0
- **Status:** Fixed

### Excluding COBOL016 in `.hefesto.yaml` needs the issue type name

- **Symptom:** `exclude_types: [COBOL016]` is rejected.
- **Cause:** `exclude_types` takes issue type names.
- **Fix:** `exclude_types: [COBOL_PLATFORM_DEPENDENT_LAYOUT]`.
- **Official source:** n/a, internal behavior
- **PR/commit:** `docs/cobol.md`; CHANGELOG (COBOL016 entry)
- **Verified:** 4.20.0
- **Status:** Known limitation

### Measure precision on labelled findings, recall on seeded issues

- **Symptom:** a rule change looks fine on unit tests but is noisy on real code.
- **Cause:** unit fixtures do not show precision.
- **Fix:** use the pinned corpus (`scripts/cobol_corpus_baseline.py`, `benchmark/cobol/baseline.json`) and the 440 labelled findings in `tests/fixtures/cobol/labels/phase3_labels.json`; recall with `python scripts/cobol_recall.py` (39 of 41 seeded issues; 2 documented misses).
- **Official source:** n/a, internal process
- **PR/commit:** `docs/cobol.md`; CHANGELOG 4.15.0 (COBOL Phase 3, 440 labelled findings)
- **Verified:** 2026-10-16
- **Status:** Known limitation (2 recall misses)
