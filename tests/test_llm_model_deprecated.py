"""LLMModel stays importable until 5.0, with a DeprecationWarning."""

import pytest


def test_core_models_llm_model_warns() -> None:
    import hefesto.core.models as models

    with pytest.warns(DeprecationWarning, match="removed in Hefesto 5.0"):
        llm_model = models.LLMModel
    assert llm_model.GEMINI_2_FLASH.value == "gemini-2.0-flash"


def test_core_package_llm_model_warns() -> None:
    with pytest.warns(DeprecationWarning, match="LLMModel is deprecated"):
        from hefesto.core import LLMModel
    import hefesto.core
    import hefesto.core.models as models

    assert "LLMModel" not in hefesto.core.__all__
    assert "LLMModel" not in models.__all__
    assert LLMModel.GEMINI_1_5_PRO.value == "gemini-1.5-pro"


def test_other_names_do_not_warn(recwarn: pytest.WarningsRecorder) -> None:
    from hefesto.core.models import SuggestionAction

    assert SuggestionAction.SHOWN.value == "shown"
    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]
