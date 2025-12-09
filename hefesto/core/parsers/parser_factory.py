"""Factory for creating appropriate parser for each language."""

from hefesto.core.language_detector import Language
from hefesto.core.parsers.base_parser import CodeParser
from hefesto.core.parsers.python_parser import PythonParser
from hefesto.core.parsers.treesitter_parser import TreeSitterParser


class ParserFactory:
    """Factory for creating appropriate parser for each language."""

    @staticmethod
    def get_parser(language: Language) -> CodeParser:
        """Get parser for language."""
        if language == Language.PYTHON:
            return PythonParser()
        elif language in [Language.TYPESCRIPT, Language.JAVASCRIPT]:
            return TreeSitterParser(language.value)
        elif language == Language.JAVA:
            return TreeSitterParser("java")
        elif language == Language.GO:
            return TreeSitterParser("go")
        else:
            raise ValueError(f"Unsupported language: {language}")
