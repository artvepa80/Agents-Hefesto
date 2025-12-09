"""Language detection from file extensions."""

from enum import Enum
from pathlib import Path
from typing import List


class Language(Enum):
    """Supported programming languages."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CSHARP = "csharp"
    UNKNOWN = "unknown"


class LanguageDetector:
    """Detect programming language from file extension."""

    EXTENSION_MAP = {
        ".py": Language.PYTHON,
        ".pyi": Language.PYTHON,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
        ".js": Language.JAVASCRIPT,
        ".jsx": Language.JAVASCRIPT,
        ".mjs": Language.JAVASCRIPT,
        ".cjs": Language.JAVASCRIPT,
        ".java": Language.JAVA,
        ".go": Language.GO,
        ".rs": Language.RUST,
        ".cs": Language.CSHARP,
    }

    @classmethod
    def detect(cls, file_path: Path) -> Language:
        """Detect language from file extension."""
        suffix = file_path.suffix.lower()
        return cls.EXTENSION_MAP.get(suffix, Language.UNKNOWN)

    @classmethod
    def is_supported(cls, file_path: Path) -> bool:
        """Check if file language is supported."""
        return cls.detect(file_path) != Language.UNKNOWN

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get list of supported file extensions."""
        return list(cls.EXTENSION_MAP.keys())

    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """Get list of supported language names."""
        return [lang.value for lang in Language if lang != Language.UNKNOWN]
