"""
Resource Safety Pack v1 — Reliability Drift Gates (EPIC 4)

Five deterministic static rules for Python that detect common resource-leak
and unbounded-growth patterns in long-running services.

Rules:
  R1 — RELIABILITY_UNBOUNDED_GLOBAL: module-level mutable (dict/list/set)
        mutated inside functions → memory leak in workers.
  R2 — RELIABILITY_UNBOUNDED_CACHE: @lru_cache(maxsize=None) or manual
        dict-cache without eviction → unbounded memory.
  R3 — RELIABILITY_SESSION_LIFECYCLE: Session()/connect() without a
        context-manager or explicit .close() → leaked connections.
  R4 — RELIABILITY_LOGGING_HANDLER_DUP: addHandler() inside a function →
        handler duplication across requests.
  R5 — RELIABILITY_THREAD_IN_REQUEST: threading.Thread() spawned inside a
        function → uncontrolled thread growth.

All severities default to MEDIUM (conservative).
Engine: internal:resource_safety_v1
Confidence: 0.85 (static heuristic)

Copyright 2025 Narapa LLC, Miami, Florida
"""

import ast
import re
from typing import Any, Dict, List, Optional, Set

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

_ENGINE = "internal:resource_safety_v1"
_CONFIDENCE = 0.85

# Session/connection constructor names (R3)
_SESSION_CONSTRUCTORS = frozenset(
    [
        "Session",
        "ClientSession",
        "connect",
        "create_connection",
        "create_engine",
        "urlopen",
        "HTTPConnection",
        "HTTPSConnection",
    ]
)

# Resource-close methods (R3)
_CLOSE_METHODS = frozenset(["close", "disconnect", "shutdown", "dispose"])


class ResourceSafetyAnalyzer:
    """Static analyzer for resource-safety anti-patterns (5 rules).

    Designed for Python files only.  Uses ``ast.parse`` for detection —
    the ``tree`` parameter (GenericAST) is accepted for API compatibility
    but not used; all logic operates on the raw ``code`` string.
    """

    def analyze(self, tree: Any, file_path: str, code: str) -> List[AnalysisIssue]:
        """Run all five resource-safety rules on *code*.

        Parameters match the standard Hefesto analyzer contract::

            analyze(tree, file_path, code) -> List[AnalysisIssue]
        """
        # Only analyze Python files
        if not file_path.endswith(".py"):
            return []

        try:
            py_tree = ast.parse(code, filename=file_path)
        except SyntaxError:
            return []

        issues: List[AnalysisIssue] = []
        issues.extend(self._r1_unbounded_global(py_tree, file_path, code))
        issues.extend(self._r2_unbounded_cache(py_tree, file_path, code))
        issues.extend(self._r3_session_lifecycle(py_tree, file_path, code))
        issues.extend(self._r4_handler_duplication(py_tree, file_path, code))
        issues.extend(self._r5_thread_in_request(py_tree, file_path, code))
        return issues

    # ------------------------------------------------------------------
    # R1 — Unbounded module-level mutable
    # ------------------------------------------------------------------

    def _r1_unbounded_global(
        self, py_tree: ast.Module, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect module-level dict/list/set that are mutated in functions."""
        issues: List[AnalysisIssue] = []

        # Collect module-level mutable names
        module_mutables: Dict[str, int] = {}  # name -> line
        for node in ast.iter_child_nodes(py_tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(
                        node.value, (ast.Dict, ast.List, ast.Set, ast.Call)
                    ):
                        # For Call, only flag dict()/list()/set()/defaultdict()
                        if isinstance(node.value, ast.Call):
                            func = node.value.func
                            name = ""
                            if isinstance(func, ast.Name):
                                name = func.id
                            elif isinstance(func, ast.Attribute):
                                name = func.attr
                            if name not in ("dict", "list", "set", "defaultdict", "OrderedDict"):
                                continue
                        module_mutables[target.id] = node.lineno

        if not module_mutables:
            return issues

        # Find mutations inside functions
        mutated_globals = self._find_mutated_globals(py_tree, set(module_mutables.keys()))

        for name in mutated_globals:
            line = module_mutables[name]
            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line,
                    column=0,
                    issue_type=AnalysisIssueType.RELIABILITY_UNBOUNDED_GLOBAL,
                    severity=AnalysisIssueSeverity.MEDIUM,
                    message=(
                        f"Module-level mutable '{name}' is mutated inside a function; "
                        "in long-running workers this can grow without bound."
                    ),
                    suggestion=(
                        "Move the mutable into the function scope, use a bounded "
                        "cache (e.g. lru_cache with maxsize), or clear periodically."
                    ),
                    engine=_ENGINE,
                    rule_id="R1",
                    confidence=_CONFIDENCE,
                    metadata={"variable": name},
                )
            )
        return issues

    @staticmethod
    def _find_mutated_globals(py_tree: ast.Module, mutable_names: Set[str]) -> Set[str]:
        """Return names from *mutable_names* that are mutated inside functions."""
        mutated: Set[str] = set()
        _MUTATING_METHODS = frozenset(
            ["append", "extend", "add", "update", "insert", "setdefault", "pop", "clear"]
        )

        for node in ast.walk(py_tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                # dict[key] = ... / list[idx] = ...
                if isinstance(child, ast.Subscript) and isinstance(child.ctx, ast.Store):
                    if isinstance(child.value, ast.Name) and child.value.id in mutable_names:
                        mutated.add(child.value.id)
                # obj.append(...) / obj.update(...) etc.
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if (
                        isinstance(child.func.value, ast.Name)
                        and child.func.value.id in mutable_names
                        and child.func.attr in _MUTATING_METHODS
                    ):
                        mutated.add(child.func.value.id)
        return mutated

    # ------------------------------------------------------------------
    # R2 — Unbounded cache
    # ------------------------------------------------------------------

    def _r2_unbounded_cache(
        self, py_tree: ast.Module, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect @lru_cache(maxsize=None) (unbounded LRU)."""
        issues: List[AnalysisIssue] = []

        for node in ast.walk(py_tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not self._is_unbounded_lru(deco):
                    continue
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=deco.lineno,
                        column=0,
                        issue_type=AnalysisIssueType.RELIABILITY_UNBOUNDED_CACHE,
                        severity=AnalysisIssueSeverity.MEDIUM,
                        message=(
                            f"@lru_cache(maxsize=None) on '{node.name}' — "
                            "cache grows without bound in long-running processes."
                        ),
                        suggestion="Set an explicit maxsize (e.g. maxsize=128).",
                        function_name=node.name,
                        engine=_ENGINE,
                        rule_id="R2",
                        confidence=_CONFIDENCE,
                    )
                )
        return issues

    @staticmethod
    def _is_unbounded_lru(deco: ast.expr) -> bool:
        """Check if decorator is lru_cache(maxsize=None) or cache (Python 3.9+)."""
        # @functools.cache or @cache — always unbounded
        if isinstance(deco, ast.Attribute) and deco.attr == "cache":
            return True
        if isinstance(deco, ast.Name) and deco.id == "cache":
            return True

        # @lru_cache(maxsize=None) or @functools.lru_cache(maxsize=None)
        if not isinstance(deco, ast.Call):
            return False
        func = deco.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name != "lru_cache":
            return False
        for kw in deco.keywords:
            if (
                kw.arg == "maxsize"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is None
            ):
                return True
        return False

    # ------------------------------------------------------------------
    # R3 — Session lifecycle
    # ------------------------------------------------------------------

    def _r3_session_lifecycle(
        self, py_tree: ast.Module, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect Session()/connect() without context-manager or close()."""
        issues: List[AnalysisIssue] = []

        for node in ast.walk(py_tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for child in ast.walk(node):
                if not isinstance(child, ast.Assign):
                    continue
                if not isinstance(child.value, ast.Call):
                    continue

                call_name = self._call_name(child.value)
                if call_name not in _SESSION_CONSTRUCTORS:
                    continue

                # Get the assigned variable name
                var_name = None
                if child.targets and isinstance(child.targets[0], ast.Name):
                    var_name = child.targets[0].id

                # Check if used in with-statement or .close() called
                if self._has_cleanup(node, var_name, child.lineno):
                    continue

                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=child.lineno,
                        column=0,
                        issue_type=AnalysisIssueType.RELIABILITY_SESSION_LIFECYCLE,
                        severity=AnalysisIssueSeverity.MEDIUM,
                        message=(
                            f"'{call_name}()' assigned to '{var_name}' without "
                            "context-manager or explicit .close() — potential connection leak."
                        ),
                        suggestion=(
                            f"Use 'with {call_name}() as {var_name}:' or ensure "
                            f"'{var_name}.close()' in a finally block."
                        ),
                        function_name=node.name,
                        engine=_ENGINE,
                        rule_id="R3",
                        confidence=_CONFIDENCE,
                        metadata={"constructor": call_name},
                    )
                )
        return issues

    @staticmethod
    def _call_name(call_node: ast.Call) -> str:
        """Extract simple name from a Call node."""
        func = call_node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return ""

    @staticmethod
    def _has_cleanup(func_node: ast.AST, var_name: Optional[str], assign_line: int) -> bool:
        """Check if *var_name* is used in a with-statement or .close() is called."""
        if var_name is None:
            return False
        for child in ast.walk(func_node):
            # with ... as var_name
            if isinstance(child, (ast.With, ast.AsyncWith)):
                for item in child.items:
                    if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                        if item.optional_vars.id == var_name:
                            return True
            # var_name.close()
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if (
                    isinstance(child.func.value, ast.Name)
                    and child.func.value.id == var_name
                    and child.func.attr in _CLOSE_METHODS
                ):
                    return True
        return False

    # ------------------------------------------------------------------
    # R4 — Logging handler duplication
    # ------------------------------------------------------------------

    def _r4_handler_duplication(
        self, py_tree: ast.Module, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect addHandler() inside functions (handler duplication)."""
        issues: List[AnalysisIssue] = []

        for node in ast.walk(py_tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                if not isinstance(child.func, ast.Attribute):
                    continue
                if child.func.attr != "addHandler":
                    continue
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=child.lineno,
                        column=0,
                        issue_type=AnalysisIssueType.RELIABILITY_LOGGING_HANDLER_DUP,
                        severity=AnalysisIssueSeverity.MEDIUM,
                        message=(
                            f"addHandler() inside function '{node.name}' — "
                            "handlers accumulate on repeated calls."
                        ),
                        suggestion=(
                            "Configure logging handlers at module level or in an "
                            "if-not-already-configured guard."
                        ),
                        function_name=node.name,
                        engine=_ENGINE,
                        rule_id="R4",
                        confidence=_CONFIDENCE,
                    )
                )
        return issues

    # ------------------------------------------------------------------
    # R5 — Thread spawning in request path
    # ------------------------------------------------------------------

    def _r5_thread_in_request(
        self, py_tree: ast.Module, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect threading.Thread() inside functions."""
        issues: List[AnalysisIssue] = []

        # Also check raw code for Thread( import pattern
        has_thread_import = bool(
            re.search(r"(?:from\s+threading\s+import|import\s+threading)", code)
        )
        if not has_thread_import:
            return issues

        for node in ast.walk(py_tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                call_name = self._call_name(child)
                # threading.Thread() or Thread()
                if call_name != "Thread":
                    continue
                # Verify it's threading.Thread, not some other Thread
                func = child.func
                if isinstance(func, ast.Attribute):
                    if not (isinstance(func.value, ast.Name) and func.value.id == "threading"):
                        continue
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=child.lineno,
                        column=0,
                        issue_type=AnalysisIssueType.RELIABILITY_THREAD_IN_REQUEST,
                        severity=AnalysisIssueSeverity.MEDIUM,
                        message=(
                            f"threading.Thread() inside function '{node.name}' — "
                            "uncontrolled thread creation in request handlers "
                            "leads to resource exhaustion."
                        ),
                        suggestion=(
                            "Use a bounded ThreadPoolExecutor or an async task queue instead."
                        ),
                        function_name=node.name,
                        engine=_ENGINE,
                        rule_id="R5",
                        confidence=_CONFIDENCE,
                    )
                )
        return issues


__all__ = ["ResourceSafetyAnalyzer"]
