"""Contract for production PyPI trusted publishing in release.yml."""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"


def _workflow() -> dict:
    """Load release.yml. PyYAML 1.1 treats the key ``on`` as boolean true."""
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    if True in loaded and "on" not in loaded:
        loaded["on"] = loaded.pop(True)
    return loaded


def test_trigger_and_workflow_permissions_stay_minimal():
    data = _workflow()
    assert data["on"]["push"]["tags"] == ["v*", "!v*rc*", "!v*-rc.*", "!v4"]
    assert data["permissions"] == {"contents": "read"}
    assert "id-token" not in data["permissions"]
    assert data["concurrency"]["group"] == "release-${{ github.ref }}"


def test_build_keeps_guard_tag_check_and_twine_check():
    build = _workflow()["jobs"]["build"]
    names = [step["name"] for step in build["steps"]]
    assert names == [
        "Checkout",
        "Setup Python",
        "Guard (public repo boundary)",
        "Verify release tag",
        "Install build tooling",
        "Build sdist + wheel",
        "Twine check",
        "Upload dist",
    ]
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/guard_public_repo.py" in text
    assert "scripts/verify_release_tag.py" in text
    assert "python -m build" in text
    assert "python -m twine check dist/*" in text
    upload = build["steps"][-1]
    assert upload["uses"] == "actions/upload-artifact@v6"
    assert upload["with"]["name"] == "python-package-distributions"
    assert upload["with"]["path"] == "dist/"
    assert upload["with"]["if-no-files-found"] == "error"


def test_publish_is_trusted_publishing_fail_closed():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "PYPI_API_TOKEN" not in text
    assert "TWINE_PASSWORD" not in text
    assert "twine upload" not in text
    assert "continue-on-error" not in text
    assert "skip-existing" not in text
    publish = _workflow()["jobs"]["publish"]
    assert publish["needs"] == "build"
    assert publish["environment"] == {
        "name": "pypi",
        "url": "https://pypi.org/p/hefesto-ai",
    }
    assert publish["permissions"] == {"id-token": "write"}
    publish_step = publish["steps"][-1]
    assert publish_step["name"] == "Publish to PyPI"
    assert publish_step["uses"] == "pypa/gh-action-pypi-publish@v1.14.2"
    assert "with" not in publish_step
    download = publish["steps"][0]
    assert download["uses"] == "actions/download-artifact@v7"
    assert download["with"]["name"] == "python-package-distributions"


def test_github_release_runs_only_after_publish():
    job = _workflow()["jobs"]["github-release"]
    assert job["needs"] == "publish"
    assert job["permissions"] == {"contents": "write"}
    release = next(step for step in job["steps"] if step["name"] == "Create GitHub Release")
    script = release["run"]
    assert 'gh release create "${{ github.ref_name }}"' in script
    assert "dist/*" in script
    assert '--title "Hefesto ${{ github.ref_name }}"' in script
    assert "--generate-notes" in script
    assert "--verify-tag" in script
    move = next(step for step in job["steps"] if step["name"] == "Move floating v4 tag")
    assert 'git tag -f "$MAJOR" "$GITHUB_SHA"' in move["run"]
    assert 'git push -f origin "refs/tags/${MAJOR}"' in move["run"]
    assert "success()" not in WORKFLOW.read_text(encoding="utf-8")
