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
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise SourceParseError(f"cannot parse {side} source: {exc}") from exc


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
        if not last:
            assert isinstance(node, ast.ClassDef)
            scope = node
    return chain


# ---------------------------------------------------------------- skips


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - unparse handles every expression
        return ""


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
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "pytestmark" in names:
            signals.extend(ast.unparse(m) for m in _marks_in(node.value) if _is_skip_marker(m))
        if "__test__" in names and isinstance(node.value, ast.Constant):
            if not node.value.value:
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
        else:
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            signals.extend(_function_signals(node))
    return Counter(signals)


def _platform_only(expr: ast.expr) -> bool:
    """True when a skipif condition reads nothing but the platform."""
    if isinstance(expr, ast.Constant):
        return True
    if isinstance(expr, (ast.Name, ast.Attribute)):
        return _dotted(expr) in _PLATFORM_NAMES
    if isinstance(expr, ast.BoolOp):
        return all(_platform_only(value) for value in expr.values)
    if isinstance(expr, ast.UnaryOp):
        return _platform_only(expr.operand)
    if isinstance(expr, ast.Compare):
        return all(_platform_only(part) for part in [expr.left, *expr.comparators])
    if isinstance(expr, ast.Call):
        if expr.keywords or not all(isinstance(a, ast.Constant) for a in expr.args):
            return False
        if _dotted(expr.func) in _PLATFORM_NAMES:  # platform.system()
            return True
        func = expr.func  # sys.platform.startswith("win")
        return isinstance(func, ast.Attribute) and _dotted(func.value) in _PLATFORM_NAMES
    return False


def _reads_platform(expr: ast.expr) -> bool:
    return any(
        isinstance(node, (ast.Name, ast.Attribute)) and _dotted(node) in _PLATFORM_NAMES
        for node in ast.walk(expr)
    )


def _is_platform_skipif(signal: str) -> bool:
    if not signal.startswith("pytest.mark.skipif("):
        return False
    node = ast.parse(signal, mode="eval").body
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
    total = 0
    for field, value in ast.iter_fields(stmt):
        if field in _BLOCK_FIELDS:
            continue
        values = value if isinstance(value, list) else [value]
        for root in values:
            if not isinstance(root, ast.AST):
                continue
            for node in ast.walk(root):
                if isinstance(node, ast.Call) and _is_assert_call(node):
                    total += 1
    return total


def _count(statements: Sequence[ast.stmt]) -> int:
    total = 0
    for stmt in statements:
        if isinstance(stmt, ast.Return):
            break  # nothing after a top-level return runs
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, ast.Assert):
            total += 0 if isinstance(stmt.test, ast.Constant) else 1
            continue
        if isinstance(stmt, ast.If) and _falsy_constant(stmt.test):
            total += _count(stmt.orelse)
            continue
        total += _header_calls(stmt)
        total += sum(_count(block) for block in _blocks(stmt))
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

    changes: List[TestChange] = []
    new_signals = _skip_signals(head, head_chain) - _skip_signals(base, base_chain)
    if new_signals:
        added = sorted(new_signals.elements())
        changes.append(
            TestChange(
                SKIPPED,
                qualname,
                f"{qualname}: newly skipped or disabled by {', '.join(added)}",
                warn_only=all(_is_platform_skipif(s) for s in added),
            )
        )

    base_func = base_chain[-1]
    head_func = head_chain[-1]
    assert isinstance(base_func, (ast.FunctionDef, ast.AsyncFunctionDef))
    assert isinstance(head_func, (ast.FunctionDef, ast.AsyncFunctionDef))
    before, after = count_assertions(base_func), count_assertions(head_func)
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
