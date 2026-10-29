"""Tests for BANNED_FILES in scripts/guard_public_repo.py."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "guard_public_repo.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("guard_public_repo", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


@pytest.mark.parametrize("rel", ["CLAUDE.md", "docs/CLAUDE_HEFESTO.md"])
def test_agent_guides_are_banned(tmp_path, monkeypatch, rel):
    assert rel in guard.BANNED_FILES
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    assert guard.check_banned_files() == []
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# guide\n", encoding="utf-8")
    assert guard.check_banned_files() == [f"BANNED FILE exists: {rel}"]
