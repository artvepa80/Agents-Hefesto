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
the HefestoAI version (from `pyproject.toml`), the commit the findings were
produced from, `analyzer_tree` (the git tree hash of `hefesto/` at that
commit) and `dirty` (true when `hefesto/` or `pyproject.toml` had
uncommitted changes, i.e. the findings do not match `commit`). Commit the
analyzer change first, then run `run`, so the committed file says
`dirty: false`; a test enforces it. With a squash merge the branch commit is
not on main, but `analyzer_tree` still is: if
`git rev-parse <main commit>:hefesto` prints the same hash, that commit has
the analyzer code the baseline was generated with.

The comparison matches findings by rule, file and line, and reports, per
corpus and rule, which findings are new and which were removed. Timing is
shown but never fails the comparison. Since the corpora are pinned, any
change in findings comes from HefestoAI itself.

## Updating the pins

Edit `CORPORA` in the script (commit SHA and license), run `run`, review the
`compare` output against the previous baseline, and commit both together.

CI runs `compare` in `.github/workflows/cobol-corpus-baseline.yml`
(described in [`cobol-corpus-baseline-ci.md`](cobol-corpus-baseline-ci.md)),
so a PR that changes findings must regenerate the baseline.

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
| COBOL004 | 1/81 (1%) | 35/44 (80%) |
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
- The 8 remaining COBOL004 false positives on CardDemo are a deliberate
  idiom that splits a 2-byte binary file status into two `PIC X` bytes
  (fixed in the leftovers below). A ninth, on NIST DB105A, was first labelled
  TP and corrected to FP during the leftovers: `INDEXED BY STATIC-INDEX` was
  read as `USAGE INDEX`, but both views are `PIC X(25)`. Hence 35/44, not
  the 36/44 first published.
- COBOL004 also gained 15 true positives that the old single-line matcher
  missed (`PIC X(12)` input overlaid with `PIC S9(10)V99` in COACTUPC and
  CVEXPORT.cpy).
- COBOL011 was already precise; Phase 3 groups it per program and lowers it
  to LOW so it no longer dominates reports.

## Phase 3 leftovers results

Changes: the CardDemo binary byte view is no longer a COBOL004 finding;
USAGE words are no longer matched inside data names (`REDEFINES
TWO-BYTES-BINARY`, `INDEXED BY STATIC-INDEX`); `EXEC SQL INCLUDE` members,
`.dcl` and extension-less copybooks are indexed; COPY names stop at column
72 in fixed format; continued literals are joined without the opening quote;
`copybook_paths` / `--copybook-path`.

Baseline deltas (`compare` against the Phase 3 baseline):

| Corpus | Files | COBOL findings | Change |
|---|---|---|---|
| CardDemo | 115 → 118 | 56 → 48 | COBOL004 24 → 16 (the 8 byte-view findings); 3 DCLGEN `.dcl` copybooks are now indexed and analyzed (no findings in them) |
| GenApp | 45 | 13 | none |
| zopeneditor-sample | 20 | 4 | none |
| NIST COBOL85 (not in the baseline) | - | 7,308 → 7,307 | COBOL004 DB105A:337 removed (the mislabelled finding above) |

Wall time of `hefesto analyze` grows slightly (CardDemo analyzer time
0.59 s → 0.65 s, GenApp 0.16 s → 0.19 s) from the extra copybook discovery
and format detection for the COPY index.

Precision (same labels; `leftovers` = findings that remain):

| Rule | After Phase 3 | Leftovers |
|---|---|---|
| COBOL001 | 22/22 | 22/22 |
| COBOL003 | 12/12 | 12/12 |
| COBOL004 | 35/44 (80%) | 35/35 (100%) |
| COBOL005 | 14/14 | 14/14 |
| COBOL006 | 15/15 | 15/15 |
| COBOL007 | 21/21 | 21/21 |
| COBOL008 | 1/1 | 1/1 |
| COBOL011 | 21/21 | 21/21 |
| COBOL015 | 5/5 | 5/5 |

No new finding appeared on any pinned corpus, so no new label was needed;
NIST is a random sample, so 100% there means "no false positive in the
sample", not "none at all".

### Recall on seeded issues

`tests/fixtures/cobol/recall/` holds 8 programs and 11 copybooks (a `.cpy`
COPYed by 6 programs, an extension-less copybook COPYed by 5, a DCLGEN
`.dcl` pulled in by `EXEC SQL INCLUDE`, and 8 copybooks used by `RCL08`
through `COPY ... REPLACING`) with 41 seeded issues listed in `seeds.json`,
at least 2 per rule. The 7 `RCL08` seeds (marked `after_expansion`) sit in
copybook text or are created by `REPLACING`, so they are only found with COPY
expansion; a test checks that all 7 are missed with expansion turned off. A seed counts as found when a finding of
the same rule is reported in the same file within 2 lines. Run
`python scripts/cobol_recall.py` (`--json`, `--min-recall`); regenerate the
fixture with `scripts/cobol_recall_fixture.py`.

| Rule | Main (Phase 3) | Leftovers | COPY expansion (41 seeds) |
|---|---|---|---|
| COBOL001 | 2/2 | 2/2 | 2/2 |
| COBOL002 | 2/3 | 2/3 | 2/3 |
| COBOL003 | 2/2 | 2/2 | 2/2 |
| COBOL004 | 2/2 | 2/2 | 3/3 |
| COBOL005 | 2/2 | 2/2 | 3/3 |
| COBOL006 | 2/2 | 2/2 | 2/2 |
| COBOL007 | 1/2 | 2/2 | 2/2 |
| COBOL008 | 3/4 | 3/4 | 4/5 |
| COBOL009 | 1/3 | 3/3 | 3/3 |
| COBOL010 | 2/2 | 2/2 | 2/2 |
| COBOL011 | 2/2 | 2/2 | 3/3 |
| COBOL012 | 2/2 | 2/2 | 3/3 |
| COBOL013 | 2/2 | 2/2 | 3/3 |
| COBOL014 | 2/2 | 2/2 | 3/3 |
| COBOL015 | 1/2 | 2/2 | 2/2 |
| **All** | **28/34 (82%)** | **32/34 (94%)** | **39/41 (95%)** |

The two misses are seeds marked `known_limit` (the test fails if one
starts being found, so the docs get updated):

- COBOL008: a secret whose value contains a credential word
  (`'secretAdmin2024'`) is skipped on purpose, to avoid placeholder false
  positives such as `'PASSWORD'`.
- COBOL002: a literal that reaches a password field through another field
  (`MOVE WS-K1 TO WS-DB-PASSWORD`) needs data-flow analysis.

The seeds were written by the same team that wrote the rules, against the
documented rule definitions, so this measures that each rule does what it
says on typical code, not recall on unknown real-world code.

## Phase 4 (performance)

No finding changed on any pinned corpus or on NIST (7,307), so the labels
are unchanged; the baseline was regenerated for the analyzer commit and the
timings. Analyzer time with `compare`: CardDemo 0.65 s → 0.42 s, GenApp
0.19 s → 0.10 s, zopeneditor-sample 0.12 s → 0.11 s. Nested `COPY` now
counts transitively for COBOL007 (none of the pinned corpora crosses the
5-program threshold through a nested copybook), and COBOL015 also checks a
copybook's own `COPY` statements (none missing on the pinned corpora).

Synthetic scale numbers come from `scripts/cobol_perf_bench.py` (see the
README, COBOL section): about 8 s per million lines.

## COPY ... REPLACING expansion

Programs are now analyzed with their `COPY` / `EXEC SQL INCLUDE` statements
replaced by the copybook text (REPLACING applied; see the README, COBOL
section). On the pinned corpora:

| Corpus | Programs with an expanded COPY | COPYs expanded | with REPLACING | not expanded |
|---|---|---|---|---|
| CardDemo | 40 of 44 | 291 | 40 (`CSSETATY`, `==(TESTVAR1)==` idiom) | 64 vendor (DFH*, SQLCA) |
| GenApp | 26 of 31 | 35 | 0 | 8 vendor, 5 not in the repo |
| zopeneditor-sample | 5 of 5 | 22 | 11 (`==:TAG:==` idiom) | 0 |

No finding changed (rule, file, line) on any pinned corpus or on NIST
(7,307), so the labels and the precision table are unchanged; the baseline
was regenerated for the analyzer commit and timings. Two effects were
reviewed:

- **COBOL004, CardDemo `COTRTLIC.cbl:434`** (`01 FILLER REDEFINES CTRTLIAI`)
  appeared once the BMS map copybook `COTRTLI` was expanded: the program
  overlays the generated input map to index its 7 screen rows. The overlay
  follows the generated layout, so it is not the corruption risk the rule is
  about; COBOL004 now skips a REDEFINES of a BMS symbolic input map (every
  binary field is an `xxxL` length field with its `xxxI` field in the same
  group), like it already skipped the generated `xxxO REDEFINES xxxI`.
- **COBOL001, CardDemo `COACTUPC.cbl:973`** (same finding, same line): the
  count in the message goes from 51 to 66 GO TOs, because the procedure
  copybook `CSUTLDPY` (date validation, 15 GO TOs) is now part of the
  program.

Analyzer time in the regenerated baseline (expansion included): CardDemo
0.42 s → 0.50 s, GenApp 0.10 s → 0.15 s, zopeneditor-sample 0.11 s →
0.12 s; the extra time is reading and expanding the copybooks (a second
`compare` run measured CardDemo at 0.47 s and GenApp at 0.15 s).
On the synthetic benchmark (`scripts/cobol_perf_bench.py`, 2 COPYs per
program, one with REPLACING) the project stays under 8 s per million lines.
