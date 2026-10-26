"""Compare one test file's base and head sources for weakened critical tests.

Pure: takes two source strings and the mapped test qualnames, returns the
changes. Git, rename detection, enforcement and reporting live elsewhere.

What it reports for each mapped test present in the base:

- ``DELETED``: no definition in the head (file deleted, function removed or
  renamed; the pure core cannot tell a rename from a deletion).
- ``SKIPPED``: a skip/xfail marker, ``pytest.skip()``/``pytest.xfail()`` call,
  ``pytestmark`` or ``__test__ = False`` that the base did not have, at
  function, class or module level. ``warn_only`` is true when every new marker
  is a ``skipif`` on the platform alone (``sys.platform``, ``os.name``,
  ``platform.system()``/``machine()``).
- ``TRIVIALIZED``: the base had assertions and the head has none that can run
  (body is ``pass``, ``...``, a docstring, ``assert <constant>``, returns
  before asserting, or hides them under ``if False:``).
- ``ASSERTS_REDUCED``: fewer assertions than the base, but not zero.
  ``warn_only`` is always true: a lower count is a reason to review, not a
  proven regression.

The last definition of a name in a module or class body wins, as in Python.

Copyright 2026 Narapa LLC, Miami, Florida
"""

import ast
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Union

from hefesto.core.safe_parse import safe_parse

DELETED = "DELETED"
SKIPPED = "SKIPPED"
TRIVIALIZED = "TRIVIALIZED"
ASSERTS_REDUCED = "ASSERTS_REDUCED"

FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]
_Scope = Union[ast.Module, ast.ClassDef]

_SKIP_MARKS = ("skip", "skipif", "xfail")
_SKIP_CALLS = ("pytest.skip", "pytest.xfail", "self.skipTest")
_RAISES_HELPERS = ("pytest.raises", "pytest.warns", "pytest.deprecated_call")
_HELPER_PREFIXES = ("assert", "check_", "verify_")
_PLATFORM_NAMES = ("sys.platform", "os.name", "platform.system", "platform.machine")


class SourceParseError(ValueError):
    """A base or head source could not be parsed as Python."""


@dataclass(frozen=True)
class TestChange:
    __test__ = False  # not a pytest test class

    kind: str
    test: str  # qualname: "test_x" or "TestClass::test_x"
    detail: str
    base_assertions: int = 0
    head_assertions: int = 0
    warn_only: bool = False

    @property
    def rule_id(self) -> str:
        return f"CT_{self.kind}"


# ---------------------------------------------------------------- lookup


def _parse(source: str, side: str) -> ast.Module:
    result = safe_parse(source)
    if result.tree is None:
        exc = result.exception
        raise SourceParseError(f"cannot parse {side} source: {exc}") from exc
    return result.tree


def _last_def(scope: _Scope, name: str) -> Optional[ast.stmt]:
    found: Optional[ast.stmt] = None
    for node in scope.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                found = node
    return found


def _resolve(module: ast.Module, qualname: str) -> Optional[List[ast.stmt]]:
    """Return [class, ..., function] for a qualname, or None."""
    chain: List[ast.stmt] = []
    scope: _Scope = module
    parts = qualname.split("::")
    for index, part in enumerate(parts):
        node = _last_def(scope, part)
        last = index == len(parts) - 1
        if node is None or (last != isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            return None
        chain.append(node)
        if isinstance(node, ast.ClassDef):
            scope = node
    return chain


# ---------------------------------------------------------------- skips


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    return ast.unparse(node)


def _is_skip_marker(node: ast.expr) -> bool:
    name = _dotted(node)
    if name.startswith("pytest.mark."):
        return name.rsplit(".", 1)[1] in _SKIP_MARKS
    return name.startswith("unittest.skip") or name.startswith("unittest.expectedFailure")


def _marks_in(value: ast.expr) -> List[ast.expr]:
    if isinstance(value, (ast.List, ast.Tuple)):
        return list(value.elts)
    return [value]


def _scope_signals(scope: _Scope) -> List[str]:
    """Skip signals that apply to every test in a module or class body."""
    signals: List[str] = []
    if isinstance(scope, ast.ClassDef):
        signals.extend(ast.unparse(d) for d in scope.decorator_list if _is_skip_marker(d))
    for node in scope.body:
        if isinstance(node, ast.Assign):
            signals.extend(_assign_signals(node))
    return signals


def _assign_signals(node: ast.Assign) -> List[str]:
    """Skip signals from a ``pytestmark = ...`` or ``__test__ = False`` assignment."""
    names = [t.id for t in node.targets if isinstance(t, ast.Name)]
    signals: List[str] = []
    if "pytestmark" in names:
        signals.extend(ast.unparse(m) for m in _marks_in(node.value) if _is_skip_marker(m))
    if "__test__" in names and _falsy_constant(node.value):
        signals.append("__test__ = False")
    return signals


def _own_nodes(func: FunctionNode) -> Iterable[ast.AST]:
    """Nodes of a function body, not descending into nested defs or lambdas."""
    stack: List[ast.AST] = list(reversed(func.body))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _function_signals(func: FunctionNode) -> List[str]:
    signals = [ast.unparse(d) for d in func.decorator_list if _is_skip_marker(d)]
    for node in _own_nodes(func):
        if isinstance(node, ast.Call) and _dotted(node) in _SKIP_CALLS:
            signals.append(ast.unparse(node))
    return signals


def _skip_signals(module: ast.Module, chain: Sequence[ast.stmt]) -> Counter:
    signals = _scope_signals(module)
    for node in chain:
        if isinstance(node, ast.ClassDef):
            signals.extend(_scope_signals(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            signals.extend(_function_signals(node))
    return Counter(signals)


def _platform_only(expr: ast.expr) -> bool:
    """True when a skipif condition reads nothing but the platform."""
    if isinstance(expr, ast.Constant):
        return True
    if isinstance(expr, (ast.Name, ast.Attribute)):
        return _dotted(expr) in _PLATFORM_NAMES
    if isinstance(expr, ast.Call):
        return _platform_call(expr)
    parts = _operands(expr)
    return parts is not None and all(_platform_only(part) for part in parts)


def _operands(expr: ast.expr) -> Optional[List[ast.expr]]:
    """Sub-expressions of a boolean, unary or comparison expression, else None."""
    if isinstance(expr, ast.BoolOp):
        return list(expr.values)
    if isinstance(expr, ast.UnaryOp):
        return [expr.operand]
    if isinstance(expr, ast.Compare):
        return [expr.left, *expr.comparators]
    return None


def _platform_call(expr: ast.Call) -> bool:
    """``platform.system()`` or ``sys.platform.startswith("win")`` with constant args."""
    if expr.keywords or not all(isinstance(a, ast.Constant) for a in expr.args):
        return False
    if _dotted(expr.func) in _PLATFORM_NAMES:
        return True
    func = expr.func
    return isinstance(func, ast.Attribute) and _dotted(func.value) in _PLATFORM_NAMES


def _reads_platform(expr: ast.expr) -> bool:
    return any(
        isinstance(node, (ast.Name, ast.Attribute)) and _dotted(node) in _PLATFORM_NAMES
        for node in ast.walk(expr)
    )


def _is_platform_skipif(signal: str) -> bool:
    if not signal.startswith("pytest.mark.skipif("):
        return False
    tree = safe_parse(signal).tree
    if tree is None or len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return False
    node = tree.body[0].value
    if not isinstance(node, ast.Call) or not node.args:
        return False
    condition = node.args[0]
    return _platform_only(condition) and _reads_platform(condition)


# ---------------------------------------------------------------- assertions


def _falsy_constant(test: ast.expr) -> bool:
    return isinstance(test, ast.Constant) and not test.value


def _is_assert_call(node: ast.Call) -> bool:
    name = _dotted(node)
    if name in _RAISES_HELPERS:
        return True
    last = name.rsplit(".", 1)[-1]
    return any(last.startswith(prefix) for prefix in _HELPER_PREFIXES)


_BLOCK_FIELDS = ("body", "orelse", "finalbody", "handlers", "cases")


def _blocks(stmt: ast.stmt) -> List[List[ast.stmt]]:
    """Statement lists nested in a compound statement (try handlers, match cases)."""
    blocks: List[List[ast.stmt]] = []
    for field in _BLOCK_FIELDS:
        value = getattr(stmt, field, None)
        if not isinstance(value, list):
            continue
        if field in ("handlers", "cases"):
            blocks.extend(item.body for item in value)
        else:
            blocks.append(value)
    return blocks


def _header_calls(stmt: ast.stmt) -> int:
    """Assertion-like calls outside the nested blocks (an expression, an if test)."""
    return sum(_assert_calls_in(root) for root in _header_roots(stmt))


def _header_roots(stmt: ast.stmt) -> List[ast.AST]:
    roots: List[ast.AST] = []
    for field, value in ast.iter_fields(stmt):
        if field not in _BLOCK_FIELDS:
            values = value if isinstance(value, list) else [value]
            roots.extend(v for v in values if isinstance(v, ast.AST))
    return roots


def _assert_calls_in(root: ast.AST) -> int:
    return sum(1 for node in ast.walk(root) if isinstance(node, ast.Call) and _is_assert_call(node))


def _count_stmt(stmt: ast.stmt) -> int:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return 0
    if isinstance(stmt, ast.Assert):
        return 0 if isinstance(stmt.test, ast.Constant) else 1
    if isinstance(stmt, ast.If) and _falsy_constant(stmt.test):
        return _count(stmt.orelse)
    return _header_calls(stmt) + sum(_count(block) for block in _blocks(stmt))


def _count(statements: Sequence[ast.stmt]) -> int:
    total = 0
    for stmt in statements:
        if isinstance(stmt, ast.Return):
            break  # nothing after a top-level return runs
        total += _count_stmt(stmt)
    return total


def count_assertions(func: FunctionNode) -> int:
    """Assertions that can run in a test body (see module docstring)."""
    return _count(func.body)


# ---------------------------------------------------------------- compare


def _compare_one(qualname: str, base: ast.Module, head: Optional[ast.Module]) -> List[TestChange]:
    base_chain = _resolve(base, qualname)
    if base_chain is None:
        return []  # not in the base: nothing to protect yet
    if head is None:
        return [TestChange(DELETED, qualname, f"{qualname}: the file was deleted")]
    head_chain = _resolve(head, qualname)
    if head_chain is None:
        return [TestChange(DELETED, qualname, f"{qualname}: no definition in the head")]

    changes = _skip_changes(qualname, base, base_chain, head, head_chain)
    changes.extend(_assertion_changes(qualname, base_chain[-1], head_chain[-1]))
    return changes


def _skip_changes(
    qualname: str,
    base: ast.Module,
    base_chain: Sequence[ast.stmt],
    head: ast.Module,
    head_chain: Sequence[ast.stmt],
) -> List[TestChange]:
    new_signals = _skip_signals(head, head_chain) - _skip_signals(base, base_chain)
    if not new_signals:
        return []
    added = sorted(new_signals.elements())
    return [
        TestChange(
            SKIPPED,
            qualname,
            f"{qualname}: newly skipped or disabled by {', '.join(added)}",
            warn_only=all(_is_platform_skipif(s) for s in added),
        )
    ]


def _assertions(node: ast.stmt) -> int:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return count_assertions(node)
    return 0  # _resolve always ends a chain with a function


def _assertion_changes(qualname: str, base_func: ast.stmt, head_func: ast.stmt) -> List[TestChange]:
    changes: List[TestChange] = []
    before, after = _assertions(base_func), _assertions(head_func)
    if before > 0 and after == 0:
        changes.append(
            TestChange(
                TRIVIALIZED,
                qualname,
                f"{qualname}: {before} assertion(s) in the base, none that can run in the head",
                before,
                after,
            )
        )
    elif after < before:
        changes.append(
            TestChange(
                ASSERTS_REDUCED,
                qualname,
                f"{qualname}: assertions went from {before} to {after}; review the change",
                before,
                after,
                warn_only=True,
            )
        )
    return changes


def compare_tests(
    base_source: str, head_source: Optional[str], qualnames: Iterable[str]
) -> List[TestChange]:
    """Compare mapped tests between base and head (``None`` = file deleted)."""
    base = _parse(base_source, "base")
    head = _parse(head_source, "head") if head_source is not None else None
    changes: List[TestChange] = []
    for qualname in qualnames:
        changes.extend(_compare_one(qualname, base, head))
    return changes


__all__ = [
    "ASSERTS_REDUCED",
    "DELETED",
    "SKIPPED",
    "TRIVIALIZED",
    "SourceParseError",
    "TestChange",
    "compare_tests",
    "count_assertions",
]
