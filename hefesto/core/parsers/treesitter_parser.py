"""Universal parser using TreeSitter."""

from pathlib import Path

from tree_sitter import Language, Parser

from hefesto.core.ast.generic_ast import GenericAST, GenericNode, NodeType
from hefesto.core.parsers.base_parser import CodeParser


class TreeSitterParser(CodeParser):
    """Universal parser using TreeSitter."""

    def __init__(self, language: str):
        self.language = language
        self.parser = Parser()

        build_path = Path(__file__).parent.parent.parent.parent / "build" / "languages.so"

        grammar_map = {
            "typescript": "tsx",
            "javascript": "javascript",
            "java": "java",
            "go": "go",
        }

        grammar_name = grammar_map.get(language, language)
        self.ts_language = Language(str(build_path), grammar_name)
        self.parser.set_language(self.ts_language)

    def parse(self, code: str, file_path: str) -> GenericAST:
        """Parse code using TreeSitter."""
        tree = self.parser.parse(bytes(code, "utf8"))
        root = self._convert_treesitter_to_generic(tree.root_node, code)
        return GenericAST(root, self.language, code)

    def supports_language(self, language: str) -> bool:
        return language in ["typescript", "javascript", "java", "go"]

    def _convert_treesitter_to_generic(self, node, source: str) -> GenericNode:
        """Convert TreeSitter node to GenericNode."""
        node_type = self._map_node_type(node.type, self.language)

        children = []
        for child in node.children:
            children.append(self._convert_treesitter_to_generic(child, source))

        return GenericNode(
            type=node_type,
            name=self._extract_name(node, source),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            column_start=node.start_point[1],
            column_end=node.end_point[1],
            text=(
                source[node.start_byte : node.end_byte]
                if node.start_byte < len(source.encode("utf8"))
                else ""
            ),
            children=children,
            metadata={"treesitter_type": node.type, "language": self.language},
        )

    def _map_node_type(self, ts_type: str, language: str) -> NodeType:
        """Map TreeSitter node type to NodeType."""
        if language in ["typescript", "javascript"]:
            mapping = {
                "function_declaration": NodeType.FUNCTION,
                "arrow_function": NodeType.FUNCTION,
                "function": NodeType.FUNCTION,
                "function_expression": NodeType.FUNCTION,
                "method_definition": NodeType.METHOD,
                "class_declaration": NodeType.CLASS,
                "if_statement": NodeType.CONDITIONAL,
                "switch_statement": NodeType.CONDITIONAL,
                "ternary_expression": NodeType.CONDITIONAL,
                "conditional_expression": NodeType.CONDITIONAL,
                "for_statement": NodeType.LOOP,
                "for_in_statement": NodeType.LOOP,
                "while_statement": NodeType.LOOP,
                "do_statement": NodeType.LOOP,
                "call_expression": NodeType.CALL,
                "return_statement": NodeType.RETURN,
                "import_statement": NodeType.IMPORT,
                "variable_declaration": NodeType.VARIABLE,
                "lexical_declaration": NodeType.VARIABLE,
                "try_statement": NodeType.TRY,
                "catch_clause": NodeType.CATCH,
                "throw_statement": NodeType.THROW,
            }
            return mapping.get(ts_type, NodeType.UNKNOWN)

        elif language == "java":
            mapping = {
                "method_declaration": NodeType.METHOD,
                "class_declaration": NodeType.CLASS,
                "if_statement": NodeType.CONDITIONAL,
                "switch_expression": NodeType.CONDITIONAL,
                "for_statement": NodeType.LOOP,
                "enhanced_for_statement": NodeType.LOOP,
                "while_statement": NodeType.LOOP,
                "do_statement": NodeType.LOOP,
                "method_invocation": NodeType.CALL,
                "return_statement": NodeType.RETURN,
                "import_declaration": NodeType.IMPORT,
                "try_statement": NodeType.TRY,
                "catch_clause": NodeType.CATCH,
                "throw_statement": NodeType.THROW,
            }
            return mapping.get(ts_type, NodeType.UNKNOWN)

        elif language == "go":
            mapping = {
                "function_declaration": NodeType.FUNCTION,
                "method_declaration": NodeType.METHOD,
                "type_declaration": NodeType.CLASS,
                "if_statement": NodeType.CONDITIONAL,
                "switch_statement": NodeType.CONDITIONAL,
                "for_statement": NodeType.LOOP,
                "call_expression": NodeType.CALL,
                "return_statement": NodeType.RETURN,
                "import_declaration": NodeType.IMPORT,
            }
            return mapping.get(ts_type, NodeType.UNKNOWN)

        return NodeType.UNKNOWN

    def _extract_name(self, node, source: str) -> str:
        """Extract name from node (function name, class name, etc.)."""
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte]
        return None
