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

Not run in CI yet: a scheduled or manual workflow is planned, but adding it
needs a push with the `workflow` scope.
