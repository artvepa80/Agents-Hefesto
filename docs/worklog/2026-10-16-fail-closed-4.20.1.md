# 2026-10-16 — 4.20.1: fail closed on files that could not be analyzed; JSON key-matching cost

PR: #132 (runtime under GH-8: opened 2026-10-16 Lima, not merged that day). No tag, release or PyPI.

## Reproduced with hefesto-ai from PyPI (Linux, 8 vCPU Xeon, Python 3.13.5)

- 4.20.0, `config.json` with a password next to a 5000-level array: "Found 2 file(s)", "Files analyzed: 1", "Gate passed: no CRITICAL+ issues", exit 0 under `--fail-on critical`. The flat file gives J001, exit 1.
- 4.19.0 skips `*.json` (Found 1 file), so both defects are new in 4.20.0.
- JSON timings, 4.20.0 → branch: 0.95 MB 2.73 → 0.29 s; 1.93 MB 5.38 → 0.41 s; 3.88 MB 13.65 → 0.64 s; 24.98 MB 74.95 → 4.29 s. Findings identical on these fixtures.
- Profile at 1 MB on 4.20.0: `key_has_pattern` 94,500 calls, `_tokens` 1,181,250 calls, `re._compile` 3,544,039 calls.

## Root causes

- `AnalyzerEngine._analyze_file` ended in `except Exception: return None`, with no record. `JsonAnalyzer` walks recursively; on Python 3.13 `json.loads` accepts depth 5000 but `_check_secrets` raises `RecursionError` (cutoff between depth 990 and 1000). On 3.10/3.11 `json.loads` itself raises.
- Other silent drops found: deep CloudFormation JSON, the JSON content classifier at very deep nesting, files that are not valid UTF-8.
- `key_match.key_has_pattern` re-tokenized every pattern and key on every call.

## Shipped in #132

Not-analyzed record (text, `meta.not_analyzed`, SARIF `error` notification, stderr warning); latin-1 fallback for files that are not valid UTF-8, listed as "decoded with fallback"; `--fail-on` fails on it, before the zero-files rule; `--allow-not-analyzed` and the Action input `allow_not_analyzed` opt out; regex fallback on `RecursionError`; memoized key matching with a call-count test.

## Deferred

Iterative walks; cloud analyzers (ARM, Serverless, Helm, CloudFormation) that return `[]` on invalid input; deep YAML losing secrets (already in 4.19.0); parser failures still do not fail the gate.

## Decision on files that are not valid UTF-8 (Arturo, 2026-10-17 06:42 Lima)

Replaces the open question (and the 2026-10-16 22:14 note) on `read_error`. A file that is not valid UTF-8 is read with a fallback encoding and analyzed; it is listed as "decoded with fallback" in text, JSON (`meta.decoded_with_fallback`) and SARIF (`warning` notification). The gate fails only when a file really cannot be analyzed (option (c), `--allow-not-analyzed` opts out).

- Fallback: `latin-1`. Source: https://docs.python.org/3/library/codecs.html, "Encodings and Unicode": latin-1 maps code points 0–255 to bytes 0x0–0xff, so any byte sequence decodes, one character per byte (line numbers kept), ASCII unchanged. `errors="replace"` (U+FFFD, "Error Handlers" table) was rejected: it destroys the bytes it replaces.
- Limit: non-ASCII text may be wrong (a UTF-16 file reads as noise); that is why each file is listed, and SARIF uses `warning`, not `note`.
- `read_error` now means an `OSError` on read only.
- Tests: `tests/test_decode_fallback.py` (latin-1 `config.json` with a password → `HARDCODED_SECRET`, exit 1 under `--fail-on CRITICAL`; listing in text, JSON, SARIF and stderr; `analyze_files`; CRLF line numbers) and `test_os_error_on_read_is_still_read_error`.
