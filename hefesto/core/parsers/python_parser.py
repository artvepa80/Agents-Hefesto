"""Python parser using built-in ast module."""

import ast

from hefesto.core.ast.generic_ast import GenericAST, GenericNode, NodeType
from hefesto.core.parsers.base_parser import CodeParser


class PythonParser(CodeParser):
    """Python parser using built-in ast module."""

    def parse(self, code: str, file_path: str) -> GenericAST:
        """Parse Python code using ast module."""
        try:
            tree = ast.parse(code, filename=file_path)
            # Pre-compute lines once for O(1) text extraction per node
            # (MiniMax Option B: avoids O(n) split per node)
            lines = code.split("\n")
            root = self._convert_ast_to_generic(tree, lines)
            return GenericAST(root, "python", code)
        except SyntaxError as e:
            root = GenericNode(
                type=NodeType.UNKNOWN,
                name=None,
                line_start=1,
                line_end=len(code.split("\n")),
                column_start=0,
                column_end=0,
                text=code,
                children=[],
                metadata={"error": str(e)},
            )
            return GenericAST(root, "python", code)

    def supports_language(self, language: str) -> bool:
        return language == "python"

    def _extract_node_text(self, node: ast.AST, lines: list) -> str:
        """Extract source text for an AST node using pre-computed lines.

        Uses lineno/end_lineno (1-based) and col_offset/end_col_offset (0-based)
        to slice the original source. Returns empty string for nodes without
        position info (e.g. Module root).

        Design: DeepSeek (architecture) + MiniMax (pre-computed lines optimization).
        """
        lineno = getattr(node, "lineno", None)
        end_lineno = getattr(node, "end_lineno", None)
        if lineno is None or end_lineno is None:
            return ""

        col_offset = getattr(node, "col_offset", 0)
        end_col_offset = getattr(node, "end_col_offset", 0)

        start_idx = lineno - 1
        end_idx = end_lineno - 1

        if start_idx < 0 or end_idx >= len(lines):
            return ""

        if start_idx == end_idx:
            return lines[start_idx][col_offset:end_col_offset]

        parts = [lines[start_idx][col_offset:]]
        if end_idx > start_idx + 1:
            parts.extend(lines[start_idx + 1:end_idx])
        parts.append(lines[end_idx][:end_col_offset])
        return "\n".join(parts)

    def _convert_ast_to_generic(self, node: ast.AST, lines: list) -> GenericNode:
        """Convert Python AST to GenericNode."""
        node_type = self._map_node_type(node)
        name = getattr(node, "name", None)
        line_start = getattr(node, "lineno", 1)
        line_end = getattr(node, "end_lineno", line_start)

        children = []
        for child in ast.iter_child_nodes(node):
            children.append(self._convert_ast_to_generic(child, lines))

        return GenericNode(
            type=node_type,
            name=name,
            line_start=line_start,
            line_end=line_end,
            column_start=getattr(node, "col_offset", 0),
            column_end=getattr(node, "end_col_offset", 0),
            text=self._extract_node_text(node, lines),
            children=children,
            metadata={"python_node_type": type(node).__name__},
        )

    def _map_node_type(self, node: ast.AST) -> NodeType:
        """Map Python AST node to NodeType."""
        mapping = {
            ast.FunctionDef: NodeType.FUNCTION,
            ast.AsyncFunctionDef: NodeType.ASYNC_FUNCTION,
            ast.ClassDef: NodeType.CLASS,
            ast.If: NodeType.CONDITIONAL,
            ast.For: NodeType.LOOP,
            ast.While: NodeType.LOOP,
            ast.AsyncFor: NodeType.LOOP,
            ast.Call: NodeType.CALL,
            ast.Return: NodeType.RETURN,
            ast.Import: NodeType.IMPORT,
            ast.ImportFrom: NodeType.IMPORT,
            ast.Try: NodeType.TRY,
            ast.Raise: NodeType.THROW,
            ast.Assign: NodeType.VARIABLE,
            ast.AnnAssign: NodeType.VARIABLE,
        }
        return mapping.get(type(node), NodeType.UNKNOWN)
