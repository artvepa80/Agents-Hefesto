"""
Provider Registry for Hefesto v4.4.0.

Manages external provider discovery, configuration, and resolution.
Supports auto-detect, internal-only, and external-only modes.

Copyright 2025 Narapa LLC, Miami, Florida
"""

from typing import Any, Dict, List, Literal, Optional, Set, Type

from hefesto.core.languages.specs import Language
from hefesto.core.providers.base import ExternalProvider


class ProviderRegistry:
    """
    Registry for external analysis providers.
    
    Handles provider discovery, availability checking, and resolution
    based on language, mode, and configuration.
    """

    def __init__(self):
        self._providers: Dict[str, Type[ExternalProvider]] = {}
        self._instances: Dict[str, ExternalProvider] = {}
        self._by_language: Dict[Language, List[str]] = {}

    def register(self, provider_class: Type[ExternalProvider]) -> None:
        """
        Register a provider class.
        
        Args:
            provider_class: ExternalProvider subclass to register
        """
        name = provider_class.name
        self._providers[name] = provider_class

        for lang in provider_class.supported_languages:
            if lang not in self._by_language:
                self._by_language[lang] = []
            if name not in self._by_language[lang]:
                self._by_language[lang].append(name)

    def get_provider(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[ExternalProvider]:
        """
        Get or create a provider instance by name.
        
        Args:
            name: Provider name
            config: Optional configuration
            
        Returns:
            Provider instance or None if not registered
        """
        if name not in self._providers:
            return None

        cache_key = f"{name}:{hash(str(config))}"
        if cache_key not in self._instances:
            self._instances[cache_key] = self._providers[name](config)

        return self._instances[cache_key]

    def get_available_providers(self, language: Language) -> List[str]:
        """Get list of available (installed) providers for a language."""
        providers = self._by_language.get(language, [])
        available = []
        for name in providers:
            instance = self.get_provider(name)
            if instance and instance.is_available():
                available.append(name)
        return available

    def resolve(
        self,
        language: Language,
        mode: Literal["auto", "internal", "external"] = "auto",
        enabled: Optional[Set[str]] = None,
        disabled: Optional[Set[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[ExternalProvider]:
        """
        Resolve which providers to use for a language.
        
        Args:
            language: Target language
            mode: Resolution mode
                - auto: Use external if available, otherwise skip
                - internal: Skip all external providers
                - external: Only use external providers (fail if unavailable)
            enabled: Explicit allowlist of provider names
            disabled: Explicit denylist of provider names
            config: Provider configuration
            
        Returns:
            List of resolved provider instances
        """
        if mode == "internal":
            return []

        candidates = self._by_language.get(language, [])
        resolved = []

        for name in candidates:
            if disabled and name in disabled:
                continue

            if enabled is not None and name not in enabled:
                continue

            instance = self.get_provider(name, config)
            if instance is None:
                continue

            if mode == "auto" and not instance.is_available():
                continue

            if mode == "external" and not instance.is_available():
                continue

            resolved.append(instance)

        return resolved

    def list_all(self) -> List[Dict[str, Any]]:
        """List all registered providers with status."""
        result = []
        for name, provider_class in self._providers.items():
            instance = self.get_provider(name)
            result.append({
                "name": name,
                "display_name": provider_class.display_name,
                "languages": [lang.value for lang in provider_class.supported_languages],
                "available": instance.is_available() if instance else False,
                "version": instance.get_version() if instance else "N/A",
            })
        return result


_default_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Get the default provider registry (singleton)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ProviderRegistry()
        _register_default_providers(_default_registry)
    return _default_registry


def _register_default_providers(registry: ProviderRegistry) -> None:
    """Register default providers (lazy import to avoid circular deps)."""
    pass


__all__ = ["ProviderRegistry", "get_provider_registry"]
