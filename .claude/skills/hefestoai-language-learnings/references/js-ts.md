# JavaScript / TypeScript learnings

### EVAL_USAGE matched `eval(` / `exec(` as text

- **Symptom:** EVAL_USAGE on `/re/.exec(s)`, on a project's own `exec(...)` method, and on the words in comments and strings (JavaScript, TypeScript, Java).
- **Cause:** the non-Python detector matched text, not calls.
- **Fix:** `hefesto.analyzers.eval_calls` walks the tree-sitter tree: `eval(...)` (also on `window`/`globalThis`/`self`), and `exec` only from `child_process` or Cypress `cy.exec`; Java `Runtime.exec` and `ScriptEngine.eval`.
- **Official source:** https://nodejs.org/api/child_process.html#child_processexeccommand-options-callback
- **PR/commit:** CHANGELOG 4.15.1
- **Verified:** 4.15.1 (2026-10-11)
- **Status:** Fixed

### Vendored and minified JavaScript is skipped by default

- **Symptom:** a JS tree reports "0 files analyzed", or the warning says "N files skipped as vendored (use --include-vendored)".
- **Cause:** discovery skips `*.min.js`/`*-min.js`, `vendor/`, `bower_components/`, `jspm_packages/`, and `lib/`, `plugins/`, `third_party/` under `static/`, `assets/`, `public/` or `wwwroot/`.
- **Fix:** expected behavior. Use `--include-vendored` to analyze them, or name the file on the command line.
- **Official source:** n/a, internal behavior
- **PR/commit:** CHANGELOG 4.16.0
- **Verified:** 4.16.0 (2026-10-12)
- **Status:** Known limitation (by design)

### Tests that need a JavaScript parser only run in multilang-smoke

- **Symptom:** a tree-sitter test (for example `test_include_vendored_analyzes_them`) is skipped in `lint-and-test`.
- **Cause:** `lint-and-test` has no JavaScript parser; the grammars are installed in `multilang-smoke`, which prefetches 6 grammars with retries into `TREE_SITTER_LANGUAGE_PACK_CACHE_DIR`.
- **Fix:** check `multilang-smoke` (it reports skipped tests) before assuming such a test ran.
- **Official source:** https://docs.pytest.org/en/stable/how-to/skipping.html
- **PR/commit:** #97; CHANGELOG 4.17.0
- **Verified:** 4.17.0 (2026-10-14)
- **Status:** Known limitation
