"""``.tsx`` files use the tsx grammar; ``.ts`` files stay on typescript.

The typescript grammar has no JSX, so a component parsed as ``.tsx`` used to
be an ERROR node. The tsx grammar rejects TypeScript ``<T>expr`` casts, so
``.ts`` must not switch with it.
"""

from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_language_pack")

_JSX = "export const View = (name: string) => <div id={name} />;\n"
_CAST = "export function id<T>(expr: T): T {\n  return <T>expr;\n}\n"


def _types(code: str, path: str) -> set:
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    ast = TreeSitterParser("typescript").parse(code, path)
    assert ast.language == "typescript"
    return {str(node.metadata.get("treesitter_type")) for node in ast.walk()}


def test_tsx_file_parses_jsx_without_error_nodes() -> None:
    types = _types(_JSX, "src/View.tsx")
    assert "ERROR" not in types
    assert "jsx_self_closing_element" in types


def test_ts_file_still_parses_angle_bracket_cast() -> None:
    types = _types(_CAST, "src/cast.ts")
    assert "ERROR" not in types
    assert "type_assertion" in types


def test_ts_file_does_not_parse_jsx() -> None:
    """The same component in a ``.ts`` file stays on the typescript grammar."""
    types = _types(_JSX, "src/View.ts")
    assert "ERROR" in types
    assert "jsx_self_closing_element" not in types
