"""Universal parser using TreeSitter."""

from pathlib import Path

from tree_sitter import Parser

from hefesto.core.ast.generic_ast import GenericAST, GenericNode, NodeType
from hefesto.core.parsers.base_parser import CodeParser

# Try to use tree-sitter-languages for pre-built grammars
try:
    from tree_sitter_languages import get_parser as get_ts_parser

    USE_PREBUILT = True
except ImportError:
    from tree_sitter import Language

    USE_PREBUILT = False


class TreeSitterParser(CodeParser):
    """Universal parser using TreeSitter."""

    # Map our language names to tree-sitter-languages names
    LANG_MAP = {
        "typescript": "typescript",
        "javascript": "javascript",
        "java": "java",
        "go": "go",
        "rust": "rust",
        "c_sharp": "c_sharp",
    }

    def __init__(self, language: str):
        self.language = language

        if USE_PREBUILT:
            # Use tree-sitter-languages pre-built grammars
            ts_lang = self.LANG_MAP.get(language, language)
            self.parser = get_ts_parser(ts_lang)
        else:
            # Fallback to custom-built grammars
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
            self.ts_language = Language(str(build_path), grammar_name)
            self.parser.set_language(self.ts_language)

    def parse(self, code: str, file_path: str) -> GenericAST:
        """Parse code using TreeSitter."""
        tree = self.parser.parse(bytes(code, "utf8"))
        root = self._convert_treesitter_to_generic(tree.root_node, code, parent=None)
        return GenericAST(root, self.language, code)

    def supports_language(self, language: str) -> bool:
        return language in self.LANG_MAP

    def _convert_treesitter_to_generic(self, node, source: str, parent=None) -> GenericNode:
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
            text=(
                source[node.start_byte : node.end_byte]
                if node.start_byte < len(source.encode("utf8"))
                else ""
            ),
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

    def _extract_name(self, node, source: str, parent=None) -> str:
        """
        Extract name from node with smart inference for arrow functions.

        Priority order:
        1. Direct identifier child (function foo() {})
        2. Parent variable_declarator name (const foo = () => {})
        3. Property name in object (foo: () => {})
        4. Method name
        5. '<anonymous>' for truly unnamed functions
        """
        # 1. Direct identifier child (standard function declaration)
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte]

        # 2. For arrow functions, look at parent context
        if node.type in ["arrow_function", "function_expression", "function"]:
            if parent is not None:
                # Check if parent is variable_declarator: const NAME = () => {}
                if parent.type == "variable_declarator":
                    for child in parent.children:
                        if child.type == "identifier":
                            return source[child.start_byte : child.end_byte]

                # Check if parent is pair/property: { NAME: () => {} }
                if parent.type in ["pair", "property", "property_assignment"]:
                    for child in parent.children:
                        if child.type in [
                            "property_identifier",
                            "identifier",
                            "string",
                        ]:
                            name = source[child.start_byte : child.end_byte]
                            # Remove quotes from string keys
                            return name.strip("'\"")

                # Check if parent is assignment: NAME = () => {}
                if parent.type == "assignment_expression":
                    for child in parent.children:
                        if child.type == "identifier":
                            return source[child.start_byte : child.end_byte]

        # 3. Method definition name
        if node.type == "method_definition":
            for child in node.children:
                if child.type == "property_identifier":
                    return source[child.start_byte : child.end_byte]

        # 4. Return '<anonymous>' instead of None for unnamed functions
        if node.type in [
            "arrow_function",
            "function_expression",
            "function",
            "function_declaration",
            "method_definition",
        ]:
            return "<anonymous>"

        return None

    def _extract_parameter_count(self, node, source: str) -> int:
        """
        Extract the actual parameter count from formal_parameters.

        Only counts parameters in function declarations, NOT in call expressions.
        """
        if node.type not in [
            "function_declaration",
            "arrow_function",
            "function_expression",
            "function",
            "method_definition",
            "method_declaration",
            "function_item",  # Rust
        ]:
            return 0

        # Find formal_parameters child
        for child in node.children:
            if child.type in [
                "formal_parameters",
                "parameters",
                "parameter_list",
            ]:
                # Count actual parameter nodes, not commas
                param_count = 0
                for param in child.children:
                    if param.type in [
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
                    ]:
                        param_count += 1
                return param_count

        return 0
