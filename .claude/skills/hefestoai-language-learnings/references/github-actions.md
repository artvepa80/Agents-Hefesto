# GitHub Actions learnings

### Actions on the deprecated Node 20 runtime

- **Symptom:** Node 20 deprecation annotations on workflow runs.
- **Cause:** GitHub is moving runners to Node 24.
- **Fix:** first Node 24 majors: `actions/checkout` v5, `actions/setup-python` v6, `actions/upload-artifact` v6 (v5 still defaulted to Node 20), `actions/cache` v5; `codecov/codecov-action` v5 is composite.
- **Official source:** https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
- **PR/commit:** #127 (`fc9d072`)
- **Verified:** 2026-10-16
- **Status:** Fixed

### checkout v6 changes how credentials persist; release.yml depends on them

- **Symptom:** risk only: a checkout bump to v6 could break the "Move floating v4 tag" step.
- **Cause:** checkout v6 "Persist creds to a separate file", and `release.yml` pushes `refs/tags/v4` with the persisted credentials.
- **Fix:** stay on checkout v5, which keeps v4's credential behavior. Test any v6 move on `release.yml` separately.
- **Official source:** https://github.com/actions/checkout/releases/tag/v6.0.0
- **PR/commit:** #127 PR body
- **Verified:** 2026-10-16
- **Status:** Workaround

### ubuntu-latest moves to Ubuntu 26.04

- **Symptom:** notices about the `ubuntu-latest` migration starting Oct 19.
- **Cause:** runner-images rolls out 26.04 as `ubuntu-latest` from Oct 19 to Nov 19, 2026.
- **Fix:** stay on `ubuntu-latest`; the 26.04 image has every Python in our matrices. Pin `ubuntu-24.04` only if a job breaks.
- **Official source:** https://github.com/actions/runner-images/issues/14748
- **PR/commit:** #127 (`fc9d072`)
- **Verified:** 2026-10-16
- **Status:** Open (watch the rollout)

### Workflow pushes need the `workflow` scope

- **Symptom:** push rejected: "refusing to allow an OAuth App to create or update workflow ... without `workflow` scope".
- **Cause:** the `gh` OAuth token lacked the `workflow` scope.
- **Fix:** the owner grants it or pushes; agents do not request broader scopes themselves.
- **Official source:** https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
- **PR/commit:** #127 (`fc9d072`)
- **Verified:** 2026-10-16
- **Status:** Workaround

### Pinned Action refs keep old bugs

- **Symptom:** `uses: artvepa80/Agents-Hefesto@v4.15.0` still analyzes 0 files under `build`/`dist`/`venv` paths after the fix.
- **Cause:** `action.yml` installs hefesto-ai from the Action's own checkout, not from PyPI.
- **Fix:** use the floating `@v4` (moved forward only by `release.yml`) or a fixed exact tag.
- **Official source:** n/a, internal behavior (`action.yml`)
- **PR/commit:** CHANGELOG 4.15.1, 4.16.0
- **Verified:** 4.16.0
- **Status:** Fixed
