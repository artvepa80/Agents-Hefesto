"""
Language detection from file extensions, filenames, and shebangs.

v4.4.0: Now uses LanguageRegistry for unified language support including
Ola 1 DevOps languages (YAML, Terraform, Shell, Dockerfile, SQL).

Copyright 2025 Narapa LLC, Miami, Florida
"""

from pathlib import Path
from typing import List, Optional

from hefesto.core.languages.specs import Language
from hefesto.core.languages.registry import get_registry, LanguageRegistry


class LanguageDetector:
    """
    Detect programming language from file extension, filename, or shebang.

    Uses the new LanguageRegistry for unified detection across all supported
    languages including DevOps languages (YAML, Terraform, Shell, Dockerfile, SQL).
    """

    _registry: Optional[LanguageRegistry] = None

    @classmethod
    def _get_registry(cls) -> LanguageRegistry:
        """Get or create registry instance."""
        if cls._registry is None:
            cls._registry = get_registry()
        return cls._registry

    @classmethod
    def detect(cls, file_path: Path, content: Optional[str] = None) -> Language:
        """
        Detect language from file path and optionally content.

        Detection priority:
        1. Exact filename match (Dockerfile, Makefile, etc.)
        2. Extension match (.py, .ts, .yml, etc.)
        3. Shebang detection for shell scripts (if content provided)

        Args:
            file_path: Path to the file
            content: Optional file content for shebang detection

        Returns:
            Detected Language enum value
        """
        return cls._get_registry().detect_language(file_path, content)

    @classmethod
    def is_supported(cls, file_path: Path, content: Optional[str] = None) -> bool:
        """Check if file language is supported for analysis."""
        return cls._get_registry().is_supported(file_path, content)

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get list of supported file extensions."""
        return cls._get_registry().get_supported_extensions()

    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """Get list of supported language names."""
        return [lang.value for lang in cls._get_registry().get_supported_languages()]


__all__ = ["Language", "LanguageDetector"]
