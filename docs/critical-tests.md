# Critical-test regression guard (`critical_tests`)

> **Preview.** This release adds the config section and the comparator core.
> Nothing runs the check on pull requests yet: `hefesto pr-review`
> integration, rename detection and `block` enforcement are planned for later
> releases. A config without `critical_tests` behaves exactly as before.

A test suite can stay green while a change deletes, skips or empties the tests
that protect a requirement. The `critical_tests` section names those tests so
Hefesto can compare them between the base and head of a pull request.

## Configuration

Add the section to the repository's root `.hefesto.yaml` (or `.hefesto.yml`):

```yaml
critical_tests:
  enforcement: warn            # optional: warn (default) or block
  entries:
    - id: authorization        # unique within the section
      requirement: "Users must not access resources they do not own."
      tests:
        - tests/test_authorization.py::test_denies_unauthorized_access
        - tests/test_authorization.py::TestAdmin::test_admin_only
      enforcement: block       # optional: overrides the section value
```

| Key | Required | Meaning |
|-----|----------|---------|
| `enforcement` | no | Default for every entry: `warn` (default) or `block`. |
| `entries` | yes | At least one entry. |
| `entries[].id` | yes | Unique, non-empty string. |
| `entries[].requirement` | yes | What the tests protect, in plain words. |
| `entries[].tests` | yes | At least one pytest node ID: `path.py::test` or `path.py::Class::test`. |
| `entries[].enforcement` | no | `warn` or `block`; defaults to the section value. |

Rules:

- Node IDs are repository-relative with `/` separators (`./` is dropped).
  Absolute paths, `..`, `\` and `[param]` suffixes are rejected: list the test
  function, and every parametrized case is covered by it.
- Unknown keys anywhere in the section are an error, as are duplicate ids and
  the same node ID listed twice in one entry. The same test may appear in
  several entries.
- `hefesto analyze` validates the section (an invalid one exits 2, like any
  config error) and otherwise ignores it. `exclude` does not apply to the
  tests listed here.

## What the comparator reports

`hefesto.critical_tests.comparator.compare_tests(base_source, head_source,
qualnames)` compares one test file's base and head sources (`head_source` is
`None` when the file was deleted). It does not run git or the tests. For each
mapped test that exists in the base:

| Kind | When | Warn-only |
|------|------|-----------|
| `DELETED` | No definition in the head: the function or file was removed, or the test was renamed. | no |
| `SKIPPED` | A new `skip`/`skipif`/`xfail` marker, `unittest.skip*`, `pytest.skip()`/`pytest.xfail()`/`self.skipTest()` call, `pytestmark`, or `__test__ = False`, at function, class or module level. | only when every new marker is a `skipif` on the platform alone (`sys.platform`, `os.name`, `platform.system()`, `platform.machine()`) |
| `TRIVIALIZED` | The base had assertions and the head has none that can run. | no |
| `ASSERTS_REDUCED` | Fewer assertions than the base, but at least one. | always: a lower count is a reason to review, not a proven regression |

Each change carries a `rule_id` (`CT_DELETED`, `CT_SKIPPED`, `CT_TRIVIALIZED`,
`CT_ASSERTS_REDUCED`).

Counted as assertions: `assert` statements (not `assert <constant>`),
`pytest.raises`/`pytest.warns`/`pytest.deprecated_call` (as a call or in
`with`), and calls whose name starts with `assert` (`self.assertEqual`,
`mock.assert_called_once_with`), `check_` or `verify_`. Not counted: anything
after a top-level `return`, the body of `if False:` (or another falsy
constant), and nested functions or classes.

When a name is defined more than once in a module or class, the last
definition is used, as in Python. Formatting-only changes produce no report.

## Limits

- Python and pytest only.
- The comparator cannot tell a rename from a deletion; rename detection is
  planned with the `pr-review` integration.
- It counts assertions; it does not judge whether a changed assertion is
  weaker.
- The config file is not a security boundary on its own. Enforcement is meant
  to read the policy from the base branch, and changes to `.hefesto.yaml`
  should require review (for example with CODEOWNERS and branch protection).
