"""Factory for creating appropriate parser for each language."""

from hefesto.core.language_detector import Language
from hefesto.core.parsers.base_parser import CodeParser
from hefesto.core.parsers.python_parser import PythonParser
from hefesto.core.parsers.treesitter_parser import TreeSitterParser


class ParserFactory:
    """Factory for creating appropriate parser for each language."""

    # Map Language enum to TreeSitter grammar name
    GRAMMAR_NAMES = {
        Language.TYPESCRIPT: "typescript",
        Language.JAVASCRIPT: "javascript",
        Language.JAVA: "java",
        Language.GO: "go",
        Language.RUST: "rust",
        Language.CSHARP: "c_sharp",
    }

    @staticmethod
    def get_parser(language: Language) -> CodeParser:
        """Get parser for language."""
        if language == Language.PYTHON:
            return PythonParser()
        elif language in ParserFactory.GRAMMAR_NAMES:
            grammar_name = ParserFactory.GRAMMAR_NAMES[language]
            return TreeSitterParser(grammar_name)
        else:
            raise ValueError(f"Unsupported language: {language}")
