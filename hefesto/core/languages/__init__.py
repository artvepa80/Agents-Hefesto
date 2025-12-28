"""Language specifications and registry for Hefesto."""

from hefesto.core.languages.registry import (
    LanguageRegistry,
    get_registry,
)
from hefesto.core.languages.specs import (
    LANGUAGE_SPECS,
    Language,
    LanguageSpec,
    ProviderRef,
)

__all__ = [
    "Language",
    "LanguageSpec",
    "ProviderRef",
    "LANGUAGE_SPECS",
    "LanguageRegistry",
    "get_registry",
]
