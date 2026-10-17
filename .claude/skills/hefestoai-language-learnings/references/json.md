# JSON learnings

### `config.json` with secrets reported "Found 0 file(s)"

- **Symptom:** up to 4.19.0, `hefesto analyze config.json` analyzed 0 files, even with secrets inside.
- **Cause:** `JsonAnalyzer` shipped as a module, but no `LanguageSpec` routed `*.json` to it.
- **Fix:** 4.20.0 dispatches JSON (and eight more formats). After the release, `config.json` with fake secrets gives "Found 1 file(s)" and 2 CRITICAL `HARDCODED_SECRET` with rule id J001.
- **Official source:** n/a, internal behavior
- **PR/commit:** #124 (`4bb568f`), released in 4.20.0 (`ea260bc`); `docs/worklog/2026-10-16-release-4.20.0.md`
- **Verified:** 4.20.0 from PyPI in a fresh venv (2026-10-16)
- **Status:** Fixed

### JSON rule ids are J001, J002, J004, J005 (no J003)

- **Symptom:** docs or tests that expect J003.
- **Cause:** J003 does not exist.
- **Fix:** list J001, J002, J004 and J005. JSON secret keys match whole tokens, so `author` and dependency names are not secrets.
- **Official source:** n/a, internal behavior
- **PR/commit:** CHANGELOG 4.20.0 (Documentation, Upgrading)
- **Verified:** 4.20.0
- **Status:** Fixed

### A `.json` file can be routed to another analyzer

- **Symptom:** a JSON file gets CloudFormation/ARM findings instead of J00x.
- **Cause:** shared suffixes are classified by content: `*.tf.json` stays Terraform; `$schema` with `deploymentTemplate.json` is ARM; `AWSTemplateFormatVersion` or `Resources` with `AWS::` types is CloudFormation. Generated lockfiles (`package-lock.json`, ...) are skipped in directory walks.
- **Fix:** expected. Name a lockfile on the command line to analyze it.
- **Official source:** n/a, internal behavior; precedence in `docs/design/devops-analyzers-wiring.md`
- **PR/commit:** #124, CHANGELOG 4.20.0
- **Verified:** 4.20.0
- **Status:** Known limitation (by design)


### Deeply nested JSON was dropped and the gate passed

- **Symptom:** 4.20.0 printed "Found 2 file(s)", "Files analyzed: 1" and "Gate passed" (exit 0 with `--fail-on critical`) over a `config.json` with a hardcoded password next to an array nested 5000 levels deep. No warning.
- **Cause:** the recursive checks in `JsonAnalyzer` raised `RecursionError` (on 3.10/3.11 `json.loads` itself raises), and `AnalyzerEngine._analyze_file` swallowed every exception with `except Exception: return None`.
- **Fix:** `RecursionError` falls back to the regex analysis. Any file that still cannot be analyzed is listed as not analyzed (text, `meta.not_analyzed`, SARIF notification) and fails `--fail-on` unless `--allow-not-analyzed`. Never catch an analyzer exception without recording the file.
- **Official source:** https://docs.python.org/3/library/sys.html#sys.setrecursionlimit
- **PR/commit:** #132
- **Verified:** 4.20.0 from PyPI vs the #132 branch, Python 3.13.5 (2026-10-16)
- **Status:** Fixed in #132 (unreleased)

### JSON analysis cost about 3 s per MB

- **Symptom:** a 3.88 MB JSON file took 13.65 s in 4.20.0; 25 MB took 75 s.
- **Cause:** `key_has_pattern` re-tokenized every pattern and every key on each call (`_tokens` ran 1.18 million times at 1 MB).
- **Fix:** memoize tokenization per key and per pattern list (bounded LRU). Guard it with a call count, not a wall clock. Do not add a size cap: it brings back silent skips.
- **Official source:** https://docs.python.org/3/library/functools.html#functools.lru_cache
- **PR/commit:** #132
- **Verified:** same machine and fixtures, 13.65 s → 0.64 s at 3.88 MB, findings identical (2026-10-16)
- **Status:** Fixed in #132 (unreleased)
