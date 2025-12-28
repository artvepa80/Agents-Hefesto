"""
Language Registry for Hefesto v4.4.0.

Provides lookup and resolution of language specs, providers, and analyzers.

Copyright 2025 Narapa LLC, Miami, Florida
"""

from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, Tuple

from hefesto.core.languages.specs import Language, LanguageSpec, LANGUAGE_SPECS, ProviderRef


class LanguageRegistry:
    """
    Registry for language specifications and capabilities.

    Provides efficient lookup by extension, filename, and shebang.
    Resolves providers based on mode and configuration.
    """

    def __init__(self, specs: Optional[List[LanguageSpec]] = None):
        self._specs = specs or LANGUAGE_SPECS
        self._by_language: Dict[Language, LanguageSpec] = {}
        self._by_extension: Dict[str, Language] = {}
        self._by_filename: Dict[str, Language] = {}
        self._shebang_languages: List[LanguageSpec] = []
        self._glob_patterns: List[Tuple[str, Language]] = []  # (pattern, Language)

        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build lookup indexes from specs."""
        for spec in self._specs:
            self._by_language[spec.language] = spec

            for glob in spec.file_globs:
                g = glob.lower()

                # Exact filename (no wildcard)
                if ("*" not in g) and ("?" not in g):
                    self._by_filename[g] = spec.language
                    continue

                # Simple extension glob like "*.py" (single dot after *)
                if g.startswith("*.") and g.count(".") == 1:
                    ext = g[1:]  # ".py"
                    self._by_extension[ext] = spec.language
                    continue

                # Otherwise treat as glob pattern (covers "*.tf.json", "Dockerfile.*", "*.Dockerfile")
                self._glob_patterns.append((g, spec.language))

            # Index detect_by_filename patterns (often wildcard patterns)
            if spec.detect_by_filename:
                for pattern in spec.filename_patterns:
                    p = pattern.lower()
                    if ("*" in p) or ("?" in p):
                        self._glob_patterns.append((p, spec.language))
                    else:
                        self._by_filename[p] = spec.language

            if spec.detect_by_shebang:
                self._shebang_languages.append(spec)

    def get_spec(self, language: Language) -> Optional[LanguageSpec]:
        """Get spec for a language."""
        return self._by_language.get(language)

    def detect_language(self, file_path: Path, content: Optional[str] = None) -> Language:
        """
        Detect language from file path and optionally content.

        Detection order:
        1. Exact filename match (Dockerfile, Makefile, etc.)
        2. Extension match
        3. Shebang detection (if content provided)
        """
        filename = file_path.name.lower()
        suffix = file_path.suffix.lower()

        if filename in self._by_filename:
            return self._by_filename[filename]

        # Wildcards (Dockerfile.*, *.Dockerfile, *.tf.json, etc.)
        for pattern, lang in self._glob_patterns:
            if fnmatch(filename, pattern):
                return lang

        if suffix in self._by_extension:
            return self._by_extension[suffix]

        if content and self._shebang_languages:
            first_line = content.split("\n", 1)[0].strip()
            if first_line.startswith("#!"):
                for spec in self._shebang_languages:
                    for shebang in spec.shebang_patterns:
                        if first_line.startswith(shebang):
                            return spec.language

        return Language.UNKNOWN

    def is_supported(self, file_path: Path, content: Optional[str] = None) -> bool:
        """Check if file language is supported."""
        return self.detect_language(file_path, content) != Language.UNKNOWN

    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        return list(self._by_extension.keys())

    def get_supported_languages(self) -> List[Language]:
        """Get all supported languages."""
        return [lang for lang in self._by_language.keys() if lang != Language.UNKNOWN]

    def get_supported_file_globs(self) -> List[str]:
        """Return all file globs across specs (for file discovery)."""
        globs: List[str] = []
        for spec in self._specs:
            globs.extend(spec.file_globs)

        # stable dedupe (preserve order)
        seen: set = set()
        out: List[str] = []
        for g in globs:
            if g not in seen:
                out.append(g)
                seen.add(g)
        return out

    def resolve_providers(
        self,
        language: Language,
        mode: Literal["auto", "internal", "external"] = "auto",
        enabled: Optional[Set[str]] = None,
        disabled: Optional[Set[str]] = None,
    ) -> List[ProviderRef]:
        """
        Resolve which providers to use for a language.

        Args:
            language: Target language
            mode: Provider mode (auto=external if available, internal=fallback only)
            enabled: Explicit allowlist of provider names
            disabled: Explicit denylist of provider names

        Returns:
            List of ProviderRef sorted by priority (highest first)
        """
        spec = self.get_spec(language)
        if not spec:
            return []

        if mode == "internal":
            return []

        providers = []
        for ref in spec.providers:
            if disabled and ref.name in disabled:
                continue

            if enabled is not None and ref.name not in enabled:
                continue

            if enabled is None and not ref.enabled_by_default:
                continue

            providers.append(ref)

        return sorted(providers, key=lambda p: -p.priority)

    def get_internal_analyzers(self, language: Language) -> List[str]:
        """Get internal analyzer names for fallback."""
        spec = self.get_spec(language)
        return list(spec.internal_analyzers) if spec else []


_default_registry: Optional[LanguageRegistry] = None


def get_registry() -> LanguageRegistry:
    """Get the default language registry (singleton)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = LanguageRegistry()
    return _default_registry


__all__ = ["LanguageRegistry", "get_registry"]
