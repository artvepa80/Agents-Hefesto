"""Language specifications and registry for Hefesto."""

from hefesto.core.languages.specs import (
    Language,
    LanguageSpec,
    ProviderRef,
    LANGUAGE_SPECS,
)
from hefesto.core.languages.registry import (
    LanguageRegistry,
    get_registry,
)

__all__ = [
    "Language",
    "LanguageSpec",
    "ProviderRef",
    "LANGUAGE_SPECS",
    "LanguageRegistry",
    "get_registry",
]
