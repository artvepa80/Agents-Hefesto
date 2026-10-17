# 2026-10-16 — GitHub Actions off Node 20 (#127)

Sanitized worklog, added 2026-10-16 so that the `github-actions` entries of the
`hefestoai-language-learnings` skill have an in-repo source.

## Push blocked by the `workflow` scope

The first push of branch `ci/node24-actions` (commit `da312ae`) was rejected:

> refusing to allow an OAuth App to create or update workflow `.github/workflows/action-smoke.yml`
> without `workflow` scope

The `gh` OAuth token used for the push did not have the `workflow` scope. Broader scopes were not
requested by the agent; the repository owner provided a token with that scope and the branch was
pushed. Reference: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps

## Change

- `actions/checkout` v4 → v5, `actions/setup-python` v5 → v6, `actions/upload-artifact` v4 → v6,
  `actions/cache` v4 → v5, `codecov/codecov-action` v4 → v5 (composite).
  `github/codeql-action/upload-sarif@v4` already runs on Node 24.
- `release.yml`: only the two `uses:` lines changed.
- Runners stay on `ubuntu-latest`: runner-images#14748 rolls Ubuntu 26.04 out as `ubuntu-latest`
  from Oct 19 to Nov 19, 2026, and the 26.04 image has every Python version in the matrices.

## Result

- Local before push: guard PASS, ruff PASS, mypy OK, pytest 1460 passed / 11 skipped.
- #127 opened at head `da312ae`, 18/18 checks green, squash-merged as `fc9d072`.
- CI on `main` at `fc9d072`: CI, Push on main, README Parity, Capabilities Parity, COBOL corpus
  baseline, Action Smoke Test and Multilang Extra Smoke all passed.
