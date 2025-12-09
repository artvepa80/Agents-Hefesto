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
            root = self._convert_ast_to_generic(tree)
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

    def _convert_ast_to_generic(self, node: ast.AST) -> GenericNode:
        """Convert Python AST to GenericNode."""
        node_type = self._map_node_type(node)
        name = getattr(node, "name", None)
        line_start = getattr(node, "lineno", 1)
        line_end = getattr(node, "end_lineno", line_start)

        children = []
        for child in ast.iter_child_nodes(node):
            children.append(self._convert_ast_to_generic(child))

        return GenericNode(
            type=node_type,
            name=name,
            line_start=line_start,
            line_end=line_end,
            column_start=getattr(node, "col_offset", 0),
            column_end=getattr(node, "end_col_offset", 0),
            text="",
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
