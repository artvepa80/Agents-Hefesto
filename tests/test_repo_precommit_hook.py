"""The repo's own pre-commit hook uses the same gate flag as the installed hook."""

from pathlib import Path

from hefesto.cli.hook_templates import PRE_COMMIT

ROOT = Path(__file__).resolve().parent.parent


def test_repo_precommit_fails_on_high_like_installed_hook() -> None:
    repo_hook = (ROOT / "scripts" / "git-hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "--fail-on HIGH" in PRE_COMMIT
    assert "--fail-on HIGH" in repo_hook


def test_core_models_have_no_llm_model_list() -> None:
    import hefesto.core
    import hefesto.core.models as models

    assert not hasattr(models, "LLMModel")
    assert "LLMModel" not in hefesto.core.__all__
