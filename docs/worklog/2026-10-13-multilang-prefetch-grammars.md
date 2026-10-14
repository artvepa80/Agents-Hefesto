# 2026-10-13 — multilang-smoke: prefetch grammars

- `get_parser` used to download grammars on first use. A network blip mid-step looked like
  a language failure, with no clear "download failed" step.
- New step before the smoke: `tree_sitter_language_pack.download([javascript, typescript,
  java, go, rust, csharp])`, 3 attempts, backoff 2/4 s, cache under
  `$RUNNER_TEMP/tslp-cache` via `TREE_SITTER_LANGUAGE_PACK_CACHE_DIR`. Failures exit with
  `::error::Grammar prefetch failed after 3 attempts: ...`.
- Smoke and "Unit tests that need the grammars" set the same env var so they do not download.
- Docs only for the behaviour; no product code. Do not merge without Arturo's OK.
