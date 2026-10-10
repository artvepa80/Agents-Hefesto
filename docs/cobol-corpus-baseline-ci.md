# COBOL corpus baseline: CI job to add by hand

The box that prepares these PRs cannot push files under `.github/workflows/`
(the token has no `workflow` scope), so this job is added through the GitHub
web UI. Create `.github/workflows/cobol-corpus-baseline.yml` on `main`
(**Add file → Create new file**) and paste the YAML below unchanged.

What it does:

- Runs `scripts/cobol_corpus_baseline.py compare` against the committed
  `benchmark/cobol/baseline.json` on pull requests that touch the COBOL
  analyzer, the baseline script or the baseline itself, weekly (Monday 06:00
  UTC) and on demand.
- Fails when the findings change. Fix the change or, if it is intended,
  regenerate the baseline with `run` and commit the JSON in the same PR.
- Uploads the fresh run (`cobol-corpus-run.json`) as an artifact either way,
  so the diff can be inspected without re-running it locally.
- Clones the three pinned corpora (shallow, about 17 MB in total) into a
  cached directory. Read-only permissions; no secrets are used.

```yaml
name: COBOL corpus baseline

on:
  pull_request:
    branches: [ main ]
    paths:
      - "hefesto/analyzers/devops/cobol_*.py"
      - "hefesto/core/analyzer_engine.py"
      - "scripts/cobol_corpus_baseline.py"
      - "benchmark/cobol/**"
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: cobol-corpus-${{ github.ref }}
  cancel-in-progress: true

jobs:
  corpus-baseline:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      HEFESTO_TELEMETRY: "0"
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install HefestoAI
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .

      - name: Cache pinned corpora
        uses: actions/cache@v4
        with:
          path: ~/.cache/hefesto-cobol-corpus
          key: cobol-corpus-${{ hashFiles('scripts/cobol_corpus_baseline.py') }}

      - name: Compare against the committed baseline
        run: |
          python scripts/cobol_corpus_baseline.py compare \
            --workdir ~/.cache/hefesto-cobol-corpus \
            --save cobol-corpus-run.json

      - name: Upload the fresh run
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: cobol-corpus-run
          path: cobol-corpus-run.json
          if-no-files-found: ignore
```

After adding it, open any PR that touches `hefesto/analyzers/devops/` to see
the job run once; the first run clones the corpora and later runs reuse the
cache (the cache key changes only when the pins in the script change).
