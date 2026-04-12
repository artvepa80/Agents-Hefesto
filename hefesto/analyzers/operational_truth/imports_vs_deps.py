"""ImportsVsDepsAnalyzer — Phase 1a Operational Truth.

Detects Python ``import`` statements that reference third-party
distributions not declared in ``pyproject.toml`` or ``requirements.txt``.

Scope decisions (conservative, aimed at <5% FP per CLAUDE.md BP-7):
- Only the *undeclared* direction is emitted here. "Declared but unused"
  has high FP risk from dev extras, plugins, and indirect uses; a
  separate pass may add it later under an explicit flag.
- Imports are resolved against:
    * stdlib modules (``sys.stdlib_module_names``),
    * first-party top-level packages discovered in the project root,
    * declared distributions from pyproject.toml / requirements*.txt,
    * a small import-name → distribution-name map for common mismatches.
- Test files and fixture directories are excluded from the import scan.
- Findings point at ``pyproject.toml`` so the fix location is unambiguous.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import ast
import logging
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Set, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

logger = logging.getLogger(__name__)

try:  # pragma: no cover - py311+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - py310
    try:
        import tomli as _toml  # type: ignore
    except ModuleNotFoundError:
        _toml = None  # type: ignore


# Common import-name → PyPI distribution-name mismatches.
# Minimal on purpose — add only when a real FP shows up.
# NOTE: ``google`` is intentionally absent. The ``google`` namespace is used
# by many distributions (google-cloud-*, google-auth, google-api-*) and a
# single mapping would misdirect the check. Instead the analyzer treats any
# declared ``google-*`` distribution as satisfying a ``google`` import.
IMPORT_TO_DIST = {
    "yaml": "pyyaml",
    "PIL": "pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "jose": "python-jose",
    "magic": "python-magic",
    "serial": "pyserial",
}

# Exception names that mark a try-block as an optional-import guard.
_OPTIONAL_IMPORT_EXC = {"ImportError", "ModuleNotFoundError"}

EXCLUDED_DIRS = {
    "tests",
    "test",
    "testing",
    "docs",
    "examples",
    "example",
    "build",
    "dist",
    "venv",
    ".venv",
    ".tox",
    "node_modules",
    "site-packages",
    "__pycache__",
    ".git",
    "htmlcov",
    ".mypy_cache",
    ".pytest_cache",
    ".eggs",
}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower().strip()


class ImportsVsDepsAnalyzer:
    """Project-level analyzer: imports vs declared dependencies."""

    def analyze_project(self, project_root: Path) -> List[AnalysisIssue]:
        project_root = Path(project_root).resolve()
        if not project_root.is_dir():
            return []

        pyproject = project_root / "pyproject.toml"
        if not pyproject.exists() or _toml is None:
            return []

        declared, project_line = self._read_declared_distributions(pyproject)
        declared.update(self._read_requirements(project_root))
        if not declared:
            return []

        first_party = self._discover_first_party(project_root)
        stdlib = set(getattr(sys, "stdlib_module_names", set()))

        used = self._collect_imports(project_root)
        declared_namespaces = self._collect_namespace_prefixes(declared)
        undeclared: Set[str] = set()
        for import_name in used:
            if import_name in stdlib:
                continue
            if import_name in first_party:
                continue
            if import_name in declared_namespaces:
                continue
            dist = _normalize(IMPORT_TO_DIST.get(import_name, import_name))
            if dist in declared:
                continue
            undeclared.add(import_name)

        issues: List[AnalysisIssue] = []
        for import_name in sorted(undeclared):
            dist = IMPORT_TO_DIST.get(import_name, import_name)
            issues.append(
                AnalysisIssue(
                    file_path=str(pyproject),
                    line=project_line,
                    column=0,
                    issue_type=AnalysisIssueType.UNDECLARED_DEPENDENCY,
                    severity=AnalysisIssueSeverity.MEDIUM,
                    message=(
                        f"Import '{import_name}' is used in the codebase but "
                        f"distribution '{dist}' is not declared in pyproject.toml "
                        f"or requirements.txt."
                    ),
                    suggestion=(
                        f"Add '{dist}' to [project].dependencies in pyproject.toml, "
                        f"or to requirements.txt."
                    ),
                    engine="internal:operational_truth",
                    rule_id="OT-IMPORTS-001",
                    confidence=0.85,
                )
            )
        return issues

    # ------------------------------------------------------------------

    def _read_declared_distributions(self, pyproject: Path) -> Tuple[Set[str], int]:
        """Return (normalized distribution names, line of [project] section)."""
        declared: Set[str] = set()
        project_line = 1
        try:
            with open(pyproject, "rb") as f:
                data = _toml.load(f)
        except Exception as exc:
            logger.debug("pyproject.toml parse failed: %s", exc)
            return declared, project_line

        project = data.get("project", {})
        for spec in project.get("dependencies", []) or []:
            name = self._spec_name(spec)
            if name:
                declared.add(_normalize(name))

        optional = project.get("optional-dependencies", {}) or {}
        for specs in optional.values():
            for spec in specs or []:
                name = self._spec_name(spec)
                if name:
                    declared.add(_normalize(name))

        try:
            with open(pyproject, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    if line.strip().startswith("[project]"):
                        project_line = idx
                        break
        except Exception:
            pass

        return declared, project_line

    def _read_requirements(self, project_root: Path) -> Set[str]:
        declared: Set[str] = set()
        for name in ("requirements.txt", "requirements-dev.txt"):
            req = project_root / name
            if not req.exists():
                continue
            try:
                for line in req.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    name = self._spec_name(line)
                    if name:
                        declared.add(_normalize(name))
            except Exception as exc:
                logger.debug("requirements parse failed: %s", exc)
        return declared

    @staticmethod
    def _spec_name(spec: str) -> Optional[str]:
        m = re.match(r"^\s*([A-Za-z0-9_.\-]+)", spec)
        return m.group(1) if m else None

    def _discover_first_party(self, project_root: Path) -> Set[str]:
        names: Set[str] = set()
        for entry in project_root.iterdir():
            if entry.is_dir() and (entry / "__init__.py").exists():
                if entry.name in EXCLUDED_DIRS:
                    continue
                names.add(entry.name)
        return names

    def _collect_imports(self, project_root: Path) -> Set[str]:
        imports: Set[str] = set()
        for py in self._iter_python_files(project_root):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for node in self._iter_effective_imports(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        continue
                    if node.module:
                        imports.add(node.module.split(".")[0])
        return imports

    def _iter_effective_imports(self, node: ast.AST) -> Iterator[ast.AST]:
        """Yield Import/ImportFrom nodes outside optional-import guards.

        Skips subtrees rooted at:
        - ``try/except ImportError`` or ``except ModuleNotFoundError`` or bare
          ``except`` — the canonical "optional import" pattern.
        - The *if-body* of ``if TYPE_CHECKING:`` / ``if typing.TYPE_CHECKING:``.
          The ``else`` branch is processed normally so runtime fallback
          imports like ``else: from importlib import import_module`` are not
          lost as false negatives.
        """
        for child in ast.iter_child_nodes(node):
            yield from self._dispatch_node(child)

    def _dispatch_node(self, child: ast.AST) -> Iterator[ast.AST]:
        """Process a single AST child, applying all guard rules."""
        if isinstance(child, ast.Try) and self._is_optional_import_try(child):
            return
        if isinstance(child, ast.If) and self._is_type_checking_if(child):
            for else_stmt in child.orelse:
                yield from self._dispatch_node(else_stmt)
            return
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            yield child
            return
        yield from self._iter_effective_imports(child)

    @staticmethod
    def _is_optional_import_try(node: ast.Try) -> bool:
        """A try-block counts as an optional-import guard when either:

        - any handler catches ``ImportError`` / ``ModuleNotFoundError`` or is
          bare ``except:``, or
        - the try body is composed *only* of import statements — the author
          has clearly wrapped imports for best-effort loading, even if they
          used a broad exception type like ``except Exception:``.
        """
        if not node.handlers:
            return False
        for handler in node.handlers:
            exc = handler.type
            if exc is None:
                return True  # bare except
            if isinstance(exc, ast.Name) and exc.id in _OPTIONAL_IMPORT_EXC:
                return True
            if isinstance(exc, ast.Tuple):
                for elt in exc.elts:
                    if isinstance(elt, ast.Name) and elt.id in _OPTIONAL_IMPORT_EXC:
                        return True
        if node.body and all(isinstance(stmt, (ast.Import, ast.ImportFrom)) for stmt in node.body):
            return True
        return False

    @staticmethod
    def _is_type_checking_if(node: ast.If) -> bool:
        test = node.test
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
            return True
        return False

    @staticmethod
    def _collect_namespace_prefixes(declared: Set[str]) -> Set[str]:
        """Return safe namespace prefixes derived from declared distributions.

        ``google-cloud-bigquery`` → ``google``. This lets a ``google`` or
        ``google.cloud.bigquery`` import be satisfied by *any* declared
        ``google-*`` distribution without hard-coding mappings.

        Conservative filter (F2) to avoid over-satisfying imports:
        - a distribution must have at least two ``-`` segments,
        - the head segment must be >=4 characters *or* the distribution
          must have >=3 segments,
        - short or generic heads that collide with real import names
          (``py``, ``python``, ``types``, ``test``) are blocked, so
          ``py-cpuinfo`` does not silently satisfy ``import py``.
        """
        blocked = {"py", "python", "types", "test"}
        prefixes: Set[str] = set()
        for dist in declared:
            parts = dist.split("-")
            if len(parts) < 2:
                continue
            head = parts[0]
            if not head or head in blocked:
                continue
            if len(parts) < 3 and len(head) < 4:
                continue
            prefixes.add(head)
        return prefixes

    def _iter_python_files(self, project_root: Path) -> Iterable[Path]:
        for path in project_root.rglob("*.py"):
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            yield path
