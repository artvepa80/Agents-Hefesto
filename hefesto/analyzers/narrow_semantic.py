"""
Narrow Semantic Analyzer — Phase 4

Two narrow, computable, auditable checks for Python files:

1. ATTRIBUTE_NAME_MISMATCH: ``self.x`` assigned in ``__init__`` but
   ``self.y`` read elsewhere where ``y`` is a close match to ``x``
   (probable typo / rename miss).

2. SILENT_EXCEPTION_SWALLOW: ``except Exception`` or
   ``except BaseException`` whose body is only ``pass``,
   ``return None``, ``return ""``, ``return []``, ``return {}``,
   or ``return 0``.  Bare ``except:`` is excluded — already covered
   by BARE_EXCEPT in SecurityAnalyzer.

This analyzer is intentionally closed to these two checks.
New narrow checks may be added only after dogfooding evidence.

Copyright 2025 Narapa LLC, Miami, Florida
"""

import ast as python_ast
import difflib
from typing import List, Set, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST


class NarrowSemanticAnalyzer:
    """Narrow semantic checks for Python files.

    Registered as a file-level analyzer via
    ``engine.register_analyzer(NarrowSemanticAnalyzer())``.
    """

    def analyze(self, tree: GenericAST, file_path: str, code: str) -> List[AnalysisIssue]:
        if tree.language != "python" or not code:
            return []

        try:
            py_tree = python_ast.parse(code)
        except SyntaxError:
            return []

        issues: List[AnalysisIssue] = []
        issues.extend(self._check_attribute_name_mismatch(py_tree, file_path))
        issues.extend(self._check_silent_exception_swallow(py_tree, file_path))
        return issues

    # ------------------------------------------------------------------
    # Check 1 — Attribute Name Mismatch
    # ------------------------------------------------------------------

    def _check_attribute_name_mismatch(
        self, py_tree: python_ast.Module, file_path: str
    ) -> List[AnalysisIssue]:
        issues: List[AnalysisIssue] = []

        for node in python_ast.walk(py_tree):
            if not isinstance(node, python_ast.ClassDef):
                continue

            # Skip classes that use dynamic attribute access — high FP risk
            if self._has_dynamic_attrs(node):
                continue

            init_attrs = self._collect_init_attrs(node)
            if not init_attrs:
                continue

            # Collect all self.X assignments across all methods (not just __init__)
            all_assigned = self._collect_all_assigned_attrs(node)

            read_attrs = self._collect_read_attrs(node)

            for attr_name, attr_line, attr_col in read_attrs:
                if attr_name in all_assigned:
                    continue

                # Look for a close match among __init__ attrs only
                matches = difflib.get_close_matches(attr_name, init_attrs, n=1, cutoff=0.8)
                if matches:
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=attr_line,
                            column=attr_col,
                            issue_type=AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH,
                            severity=AnalysisIssueSeverity.MEDIUM,
                            message=(
                                f"self.{attr_name} read but never assigned; "
                                f"did you mean self.{matches[0]}?"
                            ),
                            suggestion=(
                                f"Replace self.{attr_name} with self.{matches[0]} "
                                f"if this was a typo."
                            ),
                            engine="internal:narrow_semantic_v1",
                            rule_id="NS-ATTR-001",
                            metadata={
                                "read_attr": attr_name,
                                "closest_match": matches[0],
                            },
                        )
                    )

        return issues

    @staticmethod
    def _has_dynamic_attrs(cls_node: python_ast.ClassDef) -> bool:
        """Return True if the class uses dynamic attribute patterns."""
        for node in python_ast.walk(cls_node):
            # __getattr__ / __setattr__ / __getattribute__
            if isinstance(node, python_ast.FunctionDef) and node.name in (
                "__getattr__",
                "__setattr__",
                "__getattribute__",
            ):
                return True
            # setattr() / getattr() calls
            if isinstance(node, python_ast.Call):
                func = node.func
                if isinstance(func, python_ast.Name) and func.id in (
                    "setattr",
                    "getattr",
                ):
                    return True
            # **kwargs unpacking into self.__dict__
            if isinstance(node, python_ast.Attribute):
                if (
                    isinstance(node.value, python_ast.Name)
                    and node.value.id == "self"
                    and node.attr == "__dict__"
                ):
                    return True
        return False

    @staticmethod
    def _collect_init_attrs(cls_node: python_ast.ClassDef) -> Set[str]:
        """Collect attribute names from ``self.X = ...`` in ``__init__``."""
        attrs: Set[str] = set()
        for item in cls_node.body:
            if isinstance(item, python_ast.FunctionDef) and item.name == "__init__":
                for node in python_ast.walk(item):
                    if (
                        isinstance(node, python_ast.Assign)
                        and len(node.targets) == 1
                        and isinstance(node.targets[0], python_ast.Attribute)
                        and isinstance(node.targets[0].value, python_ast.Name)
                        and node.targets[0].value.id == "self"
                    ):
                        attrs.add(node.targets[0].attr)
                    elif (
                        isinstance(node, python_ast.AnnAssign)
                        and node.target is not None
                        and isinstance(node.target, python_ast.Attribute)
                        and isinstance(node.target.value, python_ast.Name)
                        and node.target.value.id == "self"
                    ):
                        attrs.add(node.target.attr)
                break
        return attrs

    @staticmethod
    def _collect_all_assigned_attrs(cls_node: python_ast.ClassDef) -> Set[str]:
        """Collect all ``self.X`` assignments across all methods.

        Also includes:
        - All method names defined in the class (``self.method`` is a
          valid reference whether called or passed as a callback).
        - Any decorated method name — ``@property``, ``@reify``,
          ``@cached_property``, and any custom decorator that exposes
          ``self.<name>`` as a valid attribute.
        """
        attrs: Set[str] = set()
        for item in cls_node.body:
            # Class-level assignments: descriptors like
            # ``padding = PaddingProperty()`` or ``__slots__`` entries
            # expose ``self.<name>`` as a valid attribute.
            if isinstance(item, python_ast.Assign):
                for target in item.targets:
                    if isinstance(target, python_ast.Name):
                        attrs.add(target.id)
            elif isinstance(item, python_ast.AnnAssign) and isinstance(
                item.target, python_ast.Name
            ):
                attrs.add(item.target.id)
            if not isinstance(item, python_ast.FunctionDef):
                continue
            # Every method name is a valid self.<name> reference —
            # covers @property, @reify, @cached_property, custom
            # decorators, and method references passed as callbacks
            # (e.g., loop.call_at(when, self._send_heartbeat)).
            attrs.add(item.name)
            for node in python_ast.walk(item):
                if (
                    isinstance(node, python_ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], python_ast.Attribute)
                    and isinstance(node.targets[0].value, python_ast.Name)
                    and node.targets[0].value.id == "self"
                ):
                    attrs.add(node.targets[0].attr)
                elif (
                    isinstance(node, python_ast.AnnAssign)
                    and node.target is not None
                    and isinstance(node.target, python_ast.Attribute)
                    and isinstance(node.target.value, python_ast.Name)
                    and node.target.value.id == "self"
                ):
                    attrs.add(node.target.attr)
        return attrs

    @staticmethod
    def _collect_read_attrs(
        cls_node: python_ast.ClassDef,
    ) -> List[Tuple[str, int, int]]:
        """Collect ``(attr_name, line, col)`` for all ``self.X`` reads.

        A read is any ``self.X`` that is NOT the target of an assignment.
        """
        reads: List[Tuple[str, int, int]] = []

        # Build sets of node ids to exclude: assignment targets + call funcs
        exclude_ids: set = set()
        for item in cls_node.body:
            if not isinstance(item, python_ast.FunctionDef):
                continue
            for node in python_ast.walk(item):
                if isinstance(node, python_ast.Assign):
                    for t in node.targets:
                        exclude_ids.add(id(t))
                elif isinstance(node, python_ast.AnnAssign) and node.target is not None:
                    exclude_ids.add(id(node.target))
                # NOTE: AugAssign (self.x += 1) is intentionally NOT excluded.
                # It reads self.x before writing — if self.x was never
                # assigned, the AugAssign is a bug (AttributeError at runtime).
                # Exclude method calls: self.method(...) is not an attr read
                elif isinstance(node, python_ast.Call):
                    exclude_ids.add(id(node.func))

        for item in cls_node.body:
            if not isinstance(item, python_ast.FunctionDef):
                continue
            for node in python_ast.walk(item):
                if (
                    isinstance(node, python_ast.Attribute)
                    and isinstance(node.value, python_ast.Name)
                    and node.value.id == "self"
                    and id(node) not in exclude_ids
                ):
                    reads.append((node.attr, node.lineno, node.col_offset))

        return reads

    # ------------------------------------------------------------------
    # Check 2 — Silent Exception Swallow
    # ------------------------------------------------------------------

    # Trivially-silent bodies: the handler does nothing useful.
    _SILENT_RETURNS = frozenset(
        [
            "None",
            '""',
            "''",
            "[]",
            "{}",
            "0",
            "False",
            "b''",
            'b""',
        ]
    )

    def _check_silent_exception_swallow(
        self, py_tree: python_ast.Module, file_path: str
    ) -> List[AnalysisIssue]:
        issues: List[AnalysisIssue] = []

        for node in python_ast.walk(py_tree):
            if not isinstance(node, python_ast.ExceptHandler):
                continue

            # Skip bare except — already covered by BARE_EXCEPT
            if node.type is None:
                continue

            if not self._is_broad_exception(node.type):
                continue

            if not self._is_trivially_silent(node.body):
                continue

            exc_name = self._exception_name(node.type)

            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=node.lineno,
                    column=node.col_offset,
                    issue_type=AnalysisIssueType.SILENT_EXCEPTION_SWALLOW,
                    severity=AnalysisIssueSeverity.MEDIUM,
                    message=(f"except {exc_name}: silently swallowed — " f"errors will be hidden"),
                    suggestion=(
                        "Log the exception or re-raise. Silent broad "
                        "except masks real failures:\n"
                        f"except {exc_name} as e:\n"
                        "    logger.exception('Unexpected error')\n"
                        "    raise"
                    ),
                    engine="internal:narrow_semantic_v1",
                    rule_id="NS-SWALLOW-001",
                    metadata={"exception_type": exc_name},
                )
            )

        return issues

    @staticmethod
    def _is_broad_exception(exc_type: python_ast.expr) -> bool:
        """Return True if the except type is Exception or BaseException."""
        if isinstance(exc_type, python_ast.Name):
            return exc_type.id in ("Exception", "BaseException")
        # except (Exception,) — tuple form
        if isinstance(exc_type, python_ast.Tuple):
            return any(
                isinstance(elt, python_ast.Name) and elt.id in ("Exception", "BaseException")
                for elt in exc_type.elts
            )
        return False

    @staticmethod
    def _exception_name(exc_type: python_ast.expr) -> str:
        if isinstance(exc_type, python_ast.Name):
            return exc_type.id
        if isinstance(exc_type, python_ast.Tuple):
            names = []
            for elt in exc_type.elts:
                if isinstance(elt, python_ast.Name):
                    names.append(elt.id)
            return f"({', '.join(names)})"
        return "Exception"

    def _is_trivially_silent(self, body: list) -> bool:
        """Return True if the handler body is trivially silent.

        Trivially silent means the body is a single statement that is:
        - ``pass``
        - ``return`` / ``return None`` / ``return ""`` / ``return []``
          / ``return {}`` / ``return 0`` / ``return False``
        - An ellipsis (``...``)
        """
        if len(body) != 1:
            return False

        stmt = body[0]

        # pass
        if isinstance(stmt, python_ast.Pass):
            return True

        # ...
        if isinstance(stmt, python_ast.Expr) and isinstance(stmt.value, python_ast.Constant):
            if stmt.value.value is ...:
                return True

        # return / return <trivial>
        if isinstance(stmt, python_ast.Return):
            if stmt.value is None:
                return True
            if isinstance(stmt.value, python_ast.Constant):
                return repr(stmt.value.value) in self._SILENT_RETURNS
            # return [] → ast.List with no elements
            if isinstance(stmt.value, python_ast.List) and not stmt.value.elts:
                return True
            # return {} → ast.Dict with no keys
            if isinstance(stmt.value, python_ast.Dict) and not stmt.value.keys:
                return True

        return False


__all__ = ["NarrowSemanticAnalyzer"]
