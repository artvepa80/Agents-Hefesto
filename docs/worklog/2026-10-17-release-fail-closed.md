# 2026-10-17 — release.yml fails closed when PyPI publish fails

Handoff. No tag, no GitHub Release, no PyPI publish. Not merged.

## What was wrong

`Publish to PyPI` in `.github/workflows/release.yml` set `continue-on-error: true`.
GitHub then lets the job pass when that step fails: `steps.pypi.outcome` is
`failure` and `steps.pypi.conclusion` is `success`. The run stayed green,
`Create GitHub Release` still ran, and `Move floating v4 tag` still force-moved
`v4`.

## What changed

- Removed `continue-on-error: true` from `Publish to PyPI`.
- `Create GitHub Release` and `Move floating v4 tag` stay later in the same job
  (`build-and-publish`) and set `if: ${{ success() }}`. A failed upload fails the
  job, so those steps do not run.
- An empty `PYPI_API_TOKEN` still skips the upload
  (`if: env.TWINE_PASSWORD != ''`). A skipped step is not a failure, so the
  release and `v4` steps still run in that case, as they did before. The
  "PyPI publish status" step is unchanged.
- No Trusted Publishing. Triggers and the secret name `PYPI_API_TOKEN` are
  unchanged.
- No `skip-existing`. The workflow did not have one, so none was added. A
  re-run of a version already on PyPI still fails at `twine upload`.

## Docs

- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepscontinue-on-error
  — "Prevents a job from failing when a step fails. Set to `true` to allow a job to pass when this step fails."
- https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#success
  — `success()` returns true when all previous steps have succeeded. A default status check of `success()` is applied unless an `if` includes a status check function.
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idneeds
  — a job that `needs` another job is skipped when that job fails, unless its own `if` says otherwise.
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idif
  — `jobs.<job_id>.if` prevents a job from running unless a condition is met.
- https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#steps-context
  — when `continue-on-error` is set and the step fails, `outcome` is `failure` and `conclusion` is `success`.

## GH-8

This changes `.github/workflows/release.yml`, which is a runtime path. It is not
merged on the calendar day (America/Lima) it was opened unless the PR body
records Arturo's exception line. Not merged here.

## Test

`tests/test_release_workflow.py` parses the YAML. It was committed first, while
`continue-on-error: true` was still on the publish step.
`test_no_release_step_continues_on_error` failed with
`build-and-publish: Publish to PyPI`. After this change both tests pass.
