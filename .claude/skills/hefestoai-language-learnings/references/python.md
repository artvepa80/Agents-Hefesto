# Python learnings

### HARDCODED_SECRET flagged mixed-case class names as AWS keys

- **Symptom:** HARDCODED_SECRET on identifiers such as `AWSEventStreamDecoder` (Anthropic SDK: 9 false positives).
- **Cause:** the `AWS[A-Z0-9]{16,}` pattern ran case-insensitively.
- **Fix:** the pattern uses the inline flag `(?-i:...)` so only all-uppercase AWS keys match.
- **Official source:** https://docs.python.org/3/library/re.html#regular-expression-syntax (inline `(?-i:...)` groups)
- **PR/commit:** CHANGELOG 4.11.2
- **Verified:** 4.11.2 (2026-04-13)
- **Status:** Fixed

### ATTRIBUTE_NAME_MISMATCH on descriptors, class attributes and method references

- **Symptom:** `self.<name>` reported as a mismatch for `padding = PaddingProperty()` (Rich: 8), and for `@reify`, `@cached_property` or a method passed as a callback (aiohttp: 15).
- **Cause:** only instance assignments counted as valid attribute names.
- **Fix:** class-level assignments and every method name defined in the class are valid `self.<name>` references.
- **Official source:** https://docs.python.org/3/howto/descriptor.html
- **PR/commit:** CHANGELOG 4.11.2
- **Verified:** 4.11.2 (2026-04-13)
- **Status:** Fixed

### R3 (RELIABILITY_SESSION_LIFECYCLE) on self-managed connections

- **Symptom:** R3 on `self._conn = sqlite3.connect(...)` with a lazy getter, and messages containing the literal `'None'`.
- **Cause:** R3 only handled `ast.Name` targets, not `ast.Attribute`.
- **Fix:** R3 accepts `self.<attr>` targets and skips them when a sibling method calls `self.<attr>.close()` (or `disconnect`/`shutdown`/`dispose`). Local connections without cleanup still fire.
- **Official source:** https://docs.python.org/3/library/ast.html#ast.Attribute
- **PR/commit:** PR #35, released in 4.13.1 (2026-05-08)
- **Verified:** 4.13.1
- **Status:** Fixed

### mypy `no-redef` on an optional import

- **Symptom:** `hefesto/analyzers/format_drift.py:82 [no-redef]`.
- **Cause:** `import black as black_module` redefined the constructor parameter `black_module`.
- **Fix:** load Black with `importlib.import_module("black")` inside `try/except ImportError`, returning `types.ModuleType`. No `# type: ignore` (if silenced, the first definition wins).
- **Official source:** https://mypy.readthedocs.io/en/stable/error_code_list.html#check-that-each-name-is-defined-once-no-redef
- **PR/commit:** #122 (`90aea1c`)
- **Verified:** 4.20.0 (2026-10-16)
- **Status:** Fixed
