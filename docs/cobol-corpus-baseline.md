# COBOL corpus baseline

`scripts/cobol_corpus_baseline.py` measures HefestoAI on three public COBOL
code bases at pinned commits and keeps the result in
`benchmark/cobol/baseline.json`. Only the results are committed here, never
the corpus code.

| Corpus | Repository | Pinned commit | License |
|---|---|---|---|
| `carddemo` | [aws-samples/aws-mainframe-modernization-carddemo](https://github.com/aws-samples/aws-mainframe-modernization-carddemo) | `59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e` | Apache-2.0 |
| `genapp` | [cicsdev/cics-genapp](https://github.com/cicsdev/cics-genapp) | `f6f3f4b2580d31b7d8dcc31ce3e3676f4cceaaaa` | EPL-2.0 |
| `zopeneditor-sample` | [IBM/zopeneditor-sample](https://github.com/IBM/zopeneditor-sample) | `8f9835308de6159eb54f226041d5f81a780cb8eb` | Apache-2.0 |

## Run it

Needs `git` and network the first time; clones are shallow and reused when
`--workdir` points at an existing directory.

```bash
# Compare the current code against the committed baseline.
# Exit code 0 = same findings, 1 = findings changed (or a corpus/commit differs).
python scripts/cobol_corpus_baseline.py compare --workdir ~/.cache/hefesto-cobol-corpus

# Machine-readable diff, or a single corpus
python scripts/cobol_corpus_baseline.py compare --json --corpus genapp

# Regenerate the baseline after an intended change (commit the JSON with the PR)
python scripts/cobol_corpus_baseline.py run --workdir ~/.cache/hefesto-cobol-corpus
```

`compare --save run.json` keeps the fresh run; `compare --current run.json`
diffs a saved run without re-analyzing.

## What the baseline holds

For each corpus: URL, commit and license; files analyzed and LOC; findings
by rule and by severity (all languages, all severities, as reported by
`hefesto analyze --severity low --output json`); counts per file and rule;
every finding as `[rule, relative path, line]`; and timing (the analyzer's
own `duration_seconds` plus the wall time of the CLI). The top level records
the HefestoAI version (from `pyproject.toml`) and commit used.

The comparison matches findings by rule, file and line, and reports, per
corpus and rule, which findings are new and which were removed. Timing is
shown but never fails the comparison. Since the corpora are pinned, any
change in findings comes from HefestoAI itself.

## Updating the pins

Edit `CORPORA` in the script (commit SHA and license), run `run`, review the
`compare` output against the previous baseline, and commit both together.

Not run in CI yet. The workflow is ready to paste in
[`cobol-corpus-baseline-ci.md`](cobol-corpus-baseline-ci.md); it is added
through the GitHub web UI because pushing workflow files needs the
`workflow` scope.

## Phase 3 (precision tuning) results

COBOL findings per corpus, before (main `43a777e`) and after Phase 3:

| Corpus | Before | After | Main changes |
|---|---|---|---|
| CardDemo | 341 | 56 | COBOL007 257 → 15, COBOL004 44 → 24, COBOL005 24 → 2, COBOL011 2 → 1 |
| GenApp | 52 | 13 | COBOL007 29 → 2, COBOL004 17 → 0, COBOL015 +5 |
| zopeneditor-sample | 14 | 4 | COBOL007 14 → 4 |
| NIST COBOL85 (not in the baseline) | 12,385 | 7,308 | COBOL004 4,430 → 78, COBOL007 396 → 0, COBOL011 747 → 432, COBOL005 26 → 12 |

Precision on a labelled sample of 440 findings
(`tests/fixtures/cobol/labels/phase3_labels.json`; print the table with
`python scripts/cobol_label_precision.py`):

| Rule | Before | After |
|---|---|---|
| COBOL001 | 22/22 | 22/22 |
| COBOL003 | 12/12 | 12/12 |
| COBOL004 | 1/81 (1%) | 36/44 (82%) |
| COBOL005 | 12/50 (24%) | 14/14 |
| COBOL006 | 15/15 | 15/15 |
| COBOL007 | 80/123 (65%) | 21/21 |
| COBOL008 | 1/1 | 1/1 |
| COBOL011 | 22/22 | 21/21 |
| COBOL015 (new) | - | 5/5 |

How to read it:

- The sample covers every finding of each rule on CardDemo, GenApp and
  zopeneditor (except 60 of 257 CardDemo COBOL007 findings before) and a
  random sample on NIST. Labels apply the per-rule criteria stored in the
  fixture; they were applied with a helper script and spot-checked by hand.
- COBOL007's criterion is the rule's own definition (5+ programs COPY the
  copybook), so its "after" precision shows the count is right, not that
  every shared copybook is a risk.
- The 8 remaining COBOL004 false positives are CardDemo's deliberate idiom
  that splits a 2-byte binary file status into two `PIC X` bytes.
- COBOL004 also gained 15 true positives that the old single-line matcher
  missed (`PIC X(12)` input overlaid with `PIC S9(10)V99` in COACTUPC and
  CVEXPORT.cpy).
- COBOL011 was already precise; Phase 3 groups it per program and lowers it
  to LOW so it no longer dominates reports.
