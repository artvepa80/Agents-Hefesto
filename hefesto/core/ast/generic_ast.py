"""Language-agnostic Abstract Syntax Tree representation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeType(Enum):
    """Universal AST node types across languages."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"
    CALL = "call"
    RETURN = "return"
    ASYNC_FUNCTION = "async_function"
    COMMENT = "comment"
    BLOCK = "block"
    TRY = "try"
    CATCH = "catch"
    THROW = "throw"
    UNKNOWN = "unknown"


@dataclass
class GenericNode:
    """Language-agnostic AST node."""

    type: NodeType
    name: Optional[str]
    line_start: int
    line_end: int
    column_start: int
    column_end: int
    text: str
    children: List["GenericNode"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def find_children_by_type(self, node_type: NodeType) -> List["GenericNode"]:
        """Find all direct children of a specific type."""
        return [child for child in self.children if child.type == node_type]

    def walk(self) -> List["GenericNode"]:
        """Walk all nodes in tree (depth-first)."""
        nodes = [self]
        for child in self.children:
            nodes.extend(child.walk())
        return nodes

    def count_descendants_by_type(self, node_type: NodeType) -> int:
        """Count all descendants of a specific type."""
        count = 0
        for node in self.walk():
            if node.type == node_type:
                count += 1
        return count


class GenericAST:
    """Language-agnostic Abstract Syntax Tree."""

    def __init__(self, root: GenericNode, language: str, source: str):
        self.root = root
        self.language = language
        self.source = source

    def walk(self) -> List[GenericNode]:
        """Walk all nodes in tree."""
        return self.root.walk()

    def find_nodes_by_type(self, node_type: NodeType) -> List[GenericNode]:
        """Find all nodes of a specific type."""
        return [node for node in self.walk() if node.type == node_type]

    def count_nodes_by_type(self, node_type: NodeType) -> int:
        """Count nodes of a specific type."""
        return len(self.find_nodes_by_type(node_type))

    def get_functions(self) -> List[GenericNode]:
        """Get all function nodes."""
        functions = self.find_nodes_by_type(NodeType.FUNCTION)
        functions.extend(self.find_nodes_by_type(NodeType.METHOD))
        functions.extend(self.find_nodes_by_type(NodeType.ASYNC_FUNCTION))
        return functions

    def get_classes(self) -> List[GenericNode]:
        """Get all class nodes."""
        return self.find_nodes_by_type(NodeType.CLASS)
