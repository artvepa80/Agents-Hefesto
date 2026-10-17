"""release.yml must fail closed when the PyPI upload fails.

A failed ``twine upload`` used to set ``continue-on-error: true``, so the job
stayed green, the GitHub Release was still created, and the floating ``v4``
tag still moved. These checks read the workflow YAML only.
"""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _jobs(workflow: dict[str, Any]) -> dict[str, Any]:
    jobs = workflow.get("jobs") or {}
    assert isinstance(jobs, dict) and jobs
    return jobs


def _continues_on_error(step: dict[str, Any]) -> bool:
    value = step.get("continue-on-error")
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return value is True


def _run_text(step: dict[str, Any]) -> str:
    run = step.get("run")
    return run if isinstance(run, str) else ""


def _is_publish(step: dict[str, Any]) -> bool:
    return step.get("id") == "pypi" or "twine upload" in _run_text(step)


def _is_github_release(step: dict[str, Any]) -> bool:
    return "gh release create" in _run_text(step)


def _is_v4_move(step: dict[str, Any]) -> bool:
    run = _run_text(step)
    return 'MAJOR="v4"' in run or "Move floating v4 tag" in str(step.get("name") or "")


def _needs_list(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs")
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    return [str(item) for item in needs]


def test_no_release_step_continues_on_error() -> None:
    offenders: list[str] = []
    for job_name, job in _jobs(_workflow()).items():
        for index, step in enumerate(job.get("steps") or []):
            if isinstance(step, dict) and _continues_on_error(step):
                label = step.get("name") or step.get("id") or f"step {index}"
                offenders.append(f"{job_name}: {label}")
    assert offenders == []


def test_release_and_v4_follow_or_depend_on_publish() -> None:
    jobs = _jobs(_workflow())
    publish: tuple[str, int] | None = None
    release: tuple[str, int] | None = None
    move_v4: tuple[str, int] | None = None

    for job_name, job in jobs.items():
        for index, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                continue
            if _is_publish(step):
                publish = (job_name, index)
            if _is_github_release(step):
                release = (job_name, index)
            if _is_v4_move(step):
                move_v4 = (job_name, index)

    assert publish is not None, "Publish to PyPI step not found"
    assert release is not None, "Create GitHub Release step not found"
    assert move_v4 is not None, "Move floating v4 tag step not found"

    def follows_or_depends(found: tuple[str, int]) -> bool:
        job_name, index = found
        publish_job, publish_index = publish
        if job_name == publish_job:
            return index > publish_index
        return publish_job in _needs_list(jobs[job_name])

    assert follows_or_depends(release)
    assert follows_or_depends(move_v4)
