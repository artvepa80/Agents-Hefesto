"""Abstract base class for code parsers."""

from abc import ABC, abstractmethod

from hefesto.core.ast.generic_ast import GenericAST


class CodeParser(ABC):
    """Abstract base class for code parsers."""

    @abstractmethod
    def parse(self, code: str, file_path: str) -> GenericAST:
        """Parse code into GenericAST."""
        pass

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """Check if parser supports language."""
        pass
