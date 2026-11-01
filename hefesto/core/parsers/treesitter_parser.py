"""Universal parser using TreeSitter."""

import logging
from pathlib import Path
from typing import Optional

from hefesto.core.ast.generic_ast import GenericAST, GenericNode, NodeType
from hefesto.core.parsers.base_parser import CodeParser

logger = logging.getLogger(__name__)

# Try pre-built grammar packs (preferred → legacy → manual build)
USE_PREBUILT = False
get_ts_parser = None

try:
    from tree_sitter_language_pack import get_parser as get_ts_parser  # type: ignore[no-redef]

    USE_PREBUILT = True
except ImportError:
    try:
        from tree_sitter_languages import get_parser as get_ts_parser  # type: ignore[no-redef]

        USE_PREBUILT = True
    except ImportError:
        pass

if not USE_PREBUILT:
    from tree_sitter import Language, Parser


_FUNCTION_EXPRESSIONS = frozenset({"arrow_function", "function_expression", "function"})
_ANONYMOUS_CAPABLE = _FUNCTION_EXPRESSIONS | {"function_declaration", "method_definition"}
_IDENTIFIER_PARENTS = frozenset({"variable_declarator", "assignment_expression"})
_PROPERTY_PARENTS = frozenset({"pair", "property", "property_assignment"})
_PROPERTY_KEY_TYPES = frozenset({"property_identifier", "identifier", "string"})
_PARAMETERIZED_NODES = _ANONYMOUS_CAPABLE | {"method_declaration", "function_item"}
_PARAMETER_LIST_TYPES = frozenset({"formal_parameters", "parameters", "parameter_list"})
_PARAMETER_TYPES = frozenset(
    {
        "identifier",
        "required_parameter",
        "optional_parameter",
        "rest_parameter",
        "parameter",
        "simple_parameter",
        "typed_parameter",
        "default_parameter",
        "formal_parameter",
        "spread_element",
    }
)


class TreeSitterParser(CodeParser):
    """Universal parser using TreeSitter."""

    # Map our language names to tree-sitter-languages names
    LANG_MAP = {
        "typescript": "typescript",
        "javascript": "javascript",
        "java": "java",
        "go": "go",
        "rust": "rust",
        "c_sharp": "csharp",  # tree-sitter-language-pack manifest uses 'csharp'
    }

    def __init__(self, language: str):
        self.language = language

        if USE_PREBUILT:
            ts_lang = self.LANG_MAP.get(language, language)
            self.parser = get_ts_parser(ts_lang)  # type: ignore[misc]
        else:
            self.parser = Parser()
            build_path = Path(__file__).parent.parent.parent.parent / "build" / "languages.so"

            grammar_map = {
                "typescript": "tsx",
                "javascript": "javascript",
                "java": "java",
                "go": "go",
                "rust": "rust",
                "c_sharp": "c_sharp",
            }
            grammar_name = grammar_map.get(language, language)
            self.language = Language(str(build_path), grammar_name)  # type: ignore
            self.parser.set_language(self.language)

    def parse(self, code: str, file_path: str) -> GenericAST:
        """Parse code using TreeSitter."""
        # tree-sitter offsets are byte offsets into this buffer: encode once and
        # slice bytes, never the decoded str (a BOM or accented text shifts it).
        data = code.encode("utf8")
        tree = self.parser.parse(data)
        root = self._convert_treesitter_to_generic(tree.root_node, data, parent=None)
        return GenericAST(root, self.language, code)

    def supports_language(self, language: str) -> bool:
        return language in self.LANG_MAP

    @staticmethod
    def _node_text(node, source: bytes) -> str:
        """Source text of ``node``: slice the UTF-8 bytes, then decode."""
        return source[node.start_byte : node.end_byte].decode("utf8", errors="replace")

    def _convert_treesitter_to_generic(self, node, source: bytes, parent=None) -> GenericNode:
        """Convert TreeSitter node to GenericNode."""
        node_type = self._map_node_type(node.type, self.language)

        children = []
        for child in node.children:
            children.append(self._convert_treesitter_to_generic(child, source, parent=node))

        # Extract name with parent context for arrow functions
        name = self._extract_name(node, source, parent)

        # Extract parameter count for functions
        param_count = self._extract_parameter_count(node, source)

        return GenericNode(
            type=node_type,
            name=name,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            column_start=node.start_point[1],
            column_end=node.end_point[1],
            text=self._node_text(node, source) if node.start_byte < len(source) else "",
            children=children,
            metadata={
                "treesitter_type": node.type,
                "language": self.language,
                "param_count": param_count,
            },
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

        elif language == "rust":
            mapping = {
                "function_item": NodeType.FUNCTION,
                "impl_item": NodeType.CLASS,
                "struct_item": NodeType.CLASS,
                "enum_item": NodeType.CLASS,
                "if_expression": NodeType.CONDITIONAL,
                "match_expression": NodeType.CONDITIONAL,
                "for_expression": NodeType.LOOP,
                "while_expression": NodeType.LOOP,
                "loop_expression": NodeType.LOOP,
                "call_expression": NodeType.CALL,
                "return_expression": NodeType.RETURN,
                "use_declaration": NodeType.IMPORT,
            }
            return mapping.get(ts_type, NodeType.UNKNOWN)

        elif language == "c_sharp":
            mapping = {
                "method_declaration": NodeType.METHOD,
                "class_declaration": NodeType.CLASS,
                "struct_declaration": NodeType.CLASS,
                "if_statement": NodeType.CONDITIONAL,
                "switch_statement": NodeType.CONDITIONAL,
                "for_statement": NodeType.LOOP,
                "foreach_statement": NodeType.LOOP,
                "while_statement": NodeType.LOOP,
                "do_statement": NodeType.LOOP,
                "invocation_expression": NodeType.CALL,
                "return_statement": NodeType.RETURN,
                "using_directive": NodeType.IMPORT,
                "try_statement": NodeType.TRY,
                "catch_clause": NodeType.CATCH,
                "throw_statement": NodeType.THROW,
            }
            return mapping.get(ts_type, NodeType.UNKNOWN)

        return NodeType.UNKNOWN

    @classmethod
    def _first_child_text(cls, node, source: bytes, types) -> Optional[str]:
        """Return the text of the first child whose type is in ``types``."""
        for child in node.children:
            if child.type in types:
                return cls._node_text(child, source)
        return None

    def _name_from_parent(self, parent, source: bytes) -> Optional[str]:
        """Infer a function expression's name from its parent context."""
        if parent.type in _IDENTIFIER_PARENTS:
            # const NAME = () => {}  /  NAME = () => {}
            return self._first_child_text(parent, source, ("identifier",))
        if parent.type in _PROPERTY_PARENTS:
            # { NAME: () => {} }; quotes are removed from string keys
            name = self._first_child_text(parent, source, _PROPERTY_KEY_TYPES)
            return None if name is None else name.strip("'\"")
        return None

    def _extract_name(self, node, source: bytes, parent=None) -> Optional[str]:
        """
        Extract name from node with smart inference for arrow functions.

        Priority order:
        1. Direct identifier child (function foo() {})
        2. Parent variable_declarator, pair/property or assignment name
        3. Method name
        4. '<anonymous>' for truly unnamed functions
        """
        name = self._first_child_text(node, source, ("identifier",))
        if name is None and node.type in _FUNCTION_EXPRESSIONS and parent is not None:
            name = self._name_from_parent(parent, source)
        if name is None and node.type == "method_definition":
            name = self._first_child_text(node, source, ("property_identifier",))
        if name is None and node.type in _ANONYMOUS_CAPABLE:
            name = "<anonymous>"
        return name

    def _extract_parameter_count(self, node, source: bytes) -> int:
        """
        Extract the actual parameter count from formal_parameters.

        Only counts parameters in function declarations, NOT in call expressions.
        """
        if node.type not in _PARAMETERIZED_NODES:
            return 0
        for child in node.children:
            if child.type in _PARAMETER_LIST_TYPES:
                # Count actual parameter nodes, not commas
                return sum(1 for param in child.children if param.type in _PARAMETER_TYPES)
        return 0
