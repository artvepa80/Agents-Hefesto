"""Contract for the manual MCP Registry workflow (mcp-registry.yml).

Guide: https://github.com/modelcontextprotocol/registry/blob/main/docs/
modelcontextprotocol-io/github-actions.mdx
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "mcp-registry.yml"


def _workflow() -> dict:
    """Load the workflow. PyYAML 1.1 treats the key ``on`` as boolean true."""
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    if True in loaded and "on" not in loaded:
        loaded["on"] = loaded.pop(True)
    return loaded


def test_manual_trigger_only_and_dry_run_by_default():
    data = _workflow()
    assert list(data["on"]) == ["workflow_dispatch"]
    inputs = data["on"]["workflow_dispatch"]["inputs"]
    assert inputs["publish"]["type"] == "boolean"
    assert inputs["publish"]["default"] is False
    assert inputs["version"]["required"] is True
    assert data["permissions"] == {"contents": "read"}


def test_only_the_publish_job_can_mint_an_oidc_token():
    jobs = _workflow()["jobs"]
    assert set(jobs) == {"validate", "environment-gate", "publish"}
    for name in ("validate", "environment-gate"):
        assert "permissions" not in jobs[name]
    assert jobs["publish"]["permissions"] == {"id-token": "write"}


def test_publish_is_gated_by_input_branch_environment_and_gate_job():
    jobs = _workflow()["jobs"]
    publish = jobs["publish"]
    condition = "${{ inputs.publish && github.ref == 'refs/heads/main' }}"
    assert publish["if"] == condition
    assert jobs["environment-gate"]["if"] == condition
    assert publish["needs"] == ["validate", "environment-gate"]
    assert publish["environment"]["name"] == "mcp-registry"
    gate = jobs["environment-gate"]["steps"][0]["run"]
    assert "environments/mcp-registry" in gate
    assert "required_reviewers" in gate


def test_gate_requires_the_environment_restricted_to_main():
    gate = _workflow()["jobs"]["environment-gate"]["steps"][0]["run"]
    assert '"protected=false custom=true"' in gate
    assert "environments/mcp-registry/deployment-branch-policies" in gate
    assert '"branch:main"' in gate


def test_publish_rechecks_the_registry_right_before_publishing():
    steps = _workflow()["jobs"]["publish"]["steps"]
    names = [step.get("name", "") for step in steps]
    recheck = next(i for i, n in enumerate(names) if "TOCTOU" in n)
    publish = next(i for i, n in enumerate(names) if n == "Publish server to MCP Registry")
    assert recheck == publish - 1
    run = steps[recheck]["run"]
    assert "registry.modelcontextprotocol.io/v0.1/servers/" in run
    assert "include_deleted=true" in run
    assert "(.name | @uri)/versions/\\(.version | @uri)" in run
    assert '!= "404"' in run


def test_canonical_entry_is_cache_busted_with_retries():
    fetch = _workflow()["jobs"]["validate"]["steps"][2]["run"]
    assert '"${CANONICAL_URL}?t=${GITHUB_RUN_ID}"' in fetch
    assert "--retry 3" in fetch


def test_validate_writes_the_job_summary():
    validate = "\n".join(s.get("run", "") for s in _workflow()["jobs"]["validate"]["steps"])
    assert '--summary "${GITHUB_STEP_SUMMARY}"' in validate


def test_publisher_is_pinned_and_checksum_verified():
    data = _workflow()
    assert data["env"]["MCP_PUBLISHER_VERSION"] == "v1.8.1"
    assert len(data["env"]["MCP_PUBLISHER_SHA256"]) == 64
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "releases/latest" not in text
    assert text.count("sha256sum --check --strict") == 3
    for job in ("validate", "publish"):
        runs = "\n".join(s.get("run", "") for s in data["jobs"][job]["steps"])
        assert "${MCP_PUBLISHER_SHA256}  mcp-publisher.tar.gz" in runs


def test_validate_and_publish_use_the_canonical_entry_only():
    data = _workflow()
    assert data["env"]["CANONICAL_URL"] == "https://hefestoai.narapallc.com/server.json"
    validate = "\n".join(s.get("run", "") for s in data["jobs"]["validate"]["steps"])
    assert "scripts/check_mcp_registry_entry.py registry-entry/server.json" in validate
    assert "./mcp-publisher validate registry-entry/server.json" in validate
    publish = "\n".join(s.get("run", "") for s in data["jobs"]["publish"]["steps"])
    assert "./mcp-publisher login github-oidc" in publish
    assert "./mcp-publisher publish registry-entry/server.json" in publish
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "mcp-publisher publish\n" not in text  # never the repo's ./server.json
    assert "MCP_GITHUB_TOKEN" not in text
    assert "pull_request_target" not in text


def test_inputs_reach_shell_only_through_env():
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            assert "${{ inputs." not in step.get("run", "")


def test_release_workflow_does_not_publish_to_the_registry():
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "mcp-publisher" not in release
