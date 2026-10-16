# Tooling and CI learnings

### Bare `ruff check` disagrees with CI's Flake8

- **Symptom:** `ruff check` without config reported 1957 findings while CI was green.
- **Cause:** Ruff's defaults (line-length 88, other rules, whole tree) are not `.flake8` (100, `extend-ignore = E203, W503`, only `hefesto tests`).
- **Fix:** `[tool.ruff]` line-length 100, py310, `select = E, W, F`, ignore `E203`, `E226`, `E24`, `extend-exclude = ["scripts", "examples"]`. Ruff rejects selectors it does not implement (`E121`, `W503`, ...).
- **Official source:** https://docs.astral.sh/ruff/configuration/ ; https://flake8.pycqa.org/en/latest/user/options.html
- **PR/commit:** #122 (`90aea1c`); `docs/worklog/2026-10-16-prepush-ruff-mypy.md`
- **Verified:** 4.20.0
- **Status:** Fixed

### A run with 0 files used to pass

- **Symptom:** "No issues found!" on a path where nothing was analyzed (wrong path, all excluded).
- **Cause:** an empty run was reported as clean.
- **Fix:** since 4.16.0 the report says "No files were analyzed", warns on stderr, and `--fail-on` fails with exit 1. Use `--allow-no-files` (or the Action's `allow_no_files: 'true'`) when empty is intended.
- **Official source:** n/a, internal behavior
- **PR/commit:** CHANGELOG 4.16.0
- **Verified:** 4.16.0
- **Status:** Fixed

### Excludes matched the analyzed path itself

- **Symptom:** analyzing `app-build/` or a checkout under `~/venv/project` analyzed 0 files.
- **Cause:** exclude names were matched as substrings of the absolute path.
- **Fix:** excludes match whole path components below the analyzed path (`path_is_excluded`).
- **Official source:** n/a, internal behavior
- **PR/commit:** CHANGELOG 4.15.1
- **Verified:** 4.15.1
- **Status:** Fixed

### Swarm Gate run shows "cancelled" (private repo)

- **Symptom:** a Swarm Gate run ends `cancelled` after ~10-25 s, sometimes with no job.
- **Cause:** `swarm-gate.yml` uses a concurrency group with `cancel-in-progress: true`; back-to-back merges cancel the older run.
- **Fix:** expected if a later run on the same ref succeeded. See `docs/CI_TROUBLESHOOTING.md` in the private repo.
- **Official source:** https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs
- **PR/commit:** private `docs/CI_TROUBLESHOOTING.md`
- **Verified:** 2026-10-16
- **Status:** Known limitation (by design)

### Merge conflict blocks update-branch and merge

- **Symptom:** `update_pull_request_branch` returns 422 "merge conflict between base and head"; merge returns 405.
- **Cause:** concurrent merges to main touched the same files (usually `CHANGELOG.md`).
- **Fix:** merge main into the branch with a normal `git merge`, resolve, push a new commit. No rebase, no force-push.
- **Official source:** https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/addressing-merge-conflicts/resolving-a-merge-conflict-using-the-command-line
- **PR/commit:** handoff `cursor-mcp-dogfood-2026-10-16.md` (private #164)
- **Verified:** 2026-10-16
- **Status:** Workaround
