# 2026-10-17 — release.yml: fail the run when PyPI publish fails

CI-only change to `.github/workflows/release.yml`. The file is release-critical
(GH-8): not merged the same calendar day (America/Lima) it is opened, and
merging needs Arturo's OK. No tag, no GitHub Release, and the workflow was
not run.

## What was wrong

`Publish to PyPI` set `continue-on-error: true` (commit `5e517f1`, 2026-02-13:
"so workflow does not fail"). A failed `twine upload` left `steps.pypi.outcome`
as `failure` and `steps.pypi.conclusion` as `success`. The next steps still
saw `success()`, so the run stayed green, `gh release create` still ran, and
`Move floating v4 tag` still force-moved `v4`. The status step only printed a
warning ("Check token and PyPI account email verification.").

That `continue-on-error` also hid a re-run where the files were already on
PyPI (`File already exists`). The commit did not name that case; it was a
side effect of ignoring every upload error.

## Change

- Removed `continue-on-error` from `Publish to PyPI`.
- Upload command is `python -m twine upload --skip-existing dist/*`.
  `--skip-existing` continues only when a file is already on PyPI. Any other
  upload error (token, email verification, network) fails the step and the job.
  The workflow still uses Twine with `TWINE_USERNAME` / `TWINE_PASSWORD`. It
  does not switch to `pypa/gh-action-pypi-publish` and does not use Trusted
  Publishing.
- `PyPI publish status`, `Create GitHub Release`, and `Move floating v4 tag`
  set `if: success()`. GitHub's default for a step with no status check is
  `success()` ("Returns true when all previous steps have succeeded"):
  https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#success
  They do not run after a failed upload
  (`continue-on-error` was what let them run:
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepscontinue-on-error).
  A missing `PYPI_API_TOKEN` still skips the upload
  (`if: env.TWINE_PASSWORD != ''`); the status step warns, and the release
  and the `v4` move still run, as before.
- The status step's non-success, non-skipped branch now prints `::error::`
  and exits 1. With `continue-on-error` gone that branch is not reached; it
  no longer warns and continues.
- Triggers, `permissions`, the concurrency group, and the `PYPI_API_TOKEN`
  secret are unchanged.

## Docs cited

- Twine `twine upload --skip-existing`: "Continue uploading files if one
  already exists. (Only valid when uploading to PyPI. Other implementations
  may not support this.)"
  https://twine.readthedocs.io/en/stable/#twine-upload
- `pypa/gh-action-pypi-publish` input `skip-existing` (not used here; same
  Twine flag): https://github.com/pypa/gh-action-pypi-publish#tolerating-release-package-file-duplicates
  The action's note says to avoid the setting when you can, and to let a PyPI
  upload fail loudly on duplicates. This workflow is one job per tag. The flag
  covers a re-run of that tag after the files are already on PyPI, so the
  release and the `v4` move can still run. It does not cover a failed upload.

## Not done

- No tag, no release, no workflow dispatch.
- Trusted Publishing stays a separate item.
