# 2026-10-06: SEC-05, escape every field in the HTML report (stored XSS)

- **Item:** SEC-05 (High) from the fix plan `plan-arreglos-hefesto` (2026-10-02),
  public-repo part. Still open in the 2026-10-06 status audit
  (`html_reporter.py:263,270,274`).
- **Branch:** `fix/sec05-html-report-xss`, cut from `main` @ `21cee2b` (v4.14.0).
- **Scope:** `hefesto/reports/html_reporter.py` (public repo). The private
  repo's part of SEC-05 (`landing-page/lib/resend.js`, `api/subscribe.js`) is
  not touched here.

## Context

`HTMLReporter._generate_issue_card` built the issue cards with f-strings and
inserted `issue.file_path` (via `location`), `issue.message` and
`issue.function_name` raw. Only `issue.suggestion` went through the
hand-rolled `_escape_html`. These values come from the repository being
analyzed: a directory named `<script>alert(1)<` containing `script>/app.py`
produces the path `…/<script>alert(1)</script>/app.py`, which ran as
script when the saved report (`--save-html`) was opened. A `"` in a value
could also break out of an attribute.

## What changed

- `hefesto/reports/html_reporter.py`
  - `_escape_html` is now a `@staticmethod` using
    `html.escape(str(value), quote=True)` (escapes `& < > " '`). `None`
    becomes `""`; other values go through `str()`.
  - Every interpolated value in the issue card is escaped: the severity
    used as a CSS class, `location` (`file_path:line[:column]`), `message`,
    `function_name`, `issue_type`, `suggestion`. The severity in the
    section header is escaped too. Enum values and numbers are escaped
    as well, as defense in depth.
  - Summary counts, duration and timestamp are numbers or formatted by
    Hefesto itself and are unchanged.
- Docs: `docs/GETTING_STARTED.md` "Output Formats → HTML" now describes the
  report truthfully (summary, issues by severity, suggestions; it had
  claimed charts, filtering and syntax highlighting), says that values are
  escaped, and warns about reports generated with ≤ v4.14.0.
- `CHANGELOG.md`: entry under `[Unreleased]` → `### Security`.

## How it was tested

- New `tests/test_html_reporter_escaping.py` (13 cases):
  - for every severity, a finding with `<script>alert(1)</script>`,
    `"><img src=x onerror=alert(1)>` and `' onmouseover='alert(1)` in the
    path, message, function name and suggestion renders only escaped text.
    Parsing the output with `html.parser` finds no `<script>` or `<img>`
    element and no `on*` attribute;
  - the card markup (`issue-card CRITICAL`, location, message, type) is
    intact, and `&` is escaped exactly once;
  - unit cases for `_escape_html` (`None`, quotes, `&`, ints);
  - end to end: `AnalyzerEngine` on a temp dir named
    `<script>alert(1)<`/`script>` with an `eval()` finding, then
    `HTMLReporter`. The path appears only escaped.
- 12 of the 13 cases fail against the old reporter (checked by stashing
  the fix).
- Existing `tests/test_operational_truth.py::test_reporters_handle_project_findings`
  still passes. Full unit suite (`-m "not integration and not slow"`) is green
  except `tests/test_version.py::test_version_drift`, which fails only in the
  local venv because of a stale editable install (4.13.1 metadata).
- `black --check`, `isort --check-only`, `flake8` and `mypy` are clean.
  `HEFESTO_TELEMETRY_ENV=dogfood hefesto analyze` on the changed files shows
  no new findings.

## What remains

- The page has no Content-Security-Policy. Adding
  `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">`
  would be a second layer, left out to keep this change minimal.
- The plan's alternative (Jinja2 with `autoescape=True`) was not used:
  `jinja2` is declared but unused (BUG-04), and `html.escape` is enough here.
- Private repo SEC-05 (HTML injection in the subscribe email, rate limit
  keyed on raw `x-forwarded-for`) is still open.
- `CHANGELOG.md`: the SEC-03 and SEC-06 PRs also add entries under
  `[Unreleased]` → `### Security`. Whichever merges second hits a trivial
  conflict; keep both entries.
