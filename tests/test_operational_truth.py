"""Unit + canary tests for Phase 1a Operational Truth analyzers.

Each analyzer gets a small set of unit tests driven by a temporary
project layout. One canary test at the bottom runs the full engine
against a fixture project containing a known violation of every
analyzer and asserts they all fire with the expected issue types.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import re
from pathlib import Path

from hefesto.analyzers.operational_truth import (
    DocsVsEntrypointsAnalyzer,
    ImportsVsDepsAnalyzer,
    InstallArtifactParityAnalyzer,
    PackagingParityAnalyzer,
)
from hefesto.core.analysis_models import AnalysisIssueType
from hefesto.core.analyzer_engine import AnalyzerEngine

PYPROJECT_MIN = """\
[project]
name = "demo-app"
version = "1.2.3"
dependencies = [
    "click>=8.0.0",
]

[project.scripts]
demo = "demo.cli:main"
ghost = "demo.cli:ghost"
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------- Imports vs deps


def test_imports_vs_deps_flags_undeclared(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(
        tmp_path / "demo" / "__init__.py",
        "",
    )
    _write(
        tmp_path / "demo" / "main.py",
        "import click\nimport requests\nfrom demo import other\n",
    )
    _write(tmp_path / "demo" / "other.py", "x = 1\n")

    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    kinds = [i.issue_type for i in issues]
    msgs = " ".join(i.message for i in issues)

    assert AnalysisIssueType.UNDECLARED_DEPENDENCY in kinds
    assert "requests" in msgs
    # click is declared and must not fire
    assert "'click'" not in msgs
    # first-party demo package must not fire
    assert "'demo'" not in msgs


def test_imports_vs_deps_respects_requirements_txt(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "requirements.txt", "requests==2.31.0\n")
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(tmp_path / "demo" / "main.py", "import requests\n")
    assert ImportsVsDepsAnalyzer().analyze_project(tmp_path) == []


def test_imports_vs_deps_ignores_stdlib(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(tmp_path / "demo" / "main.py", "import os\nimport sys\nimport click\n")
    assert ImportsVsDepsAnalyzer().analyze_project(tmp_path) == []


def test_imports_vs_deps_skips_optional_import_guard(tmp_path: Path) -> None:
    """B1 regression: imports under try/except ImportError must not fire."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "try:\n"
        "    import optional_pkg\n"
        "    from other_optional import thing\n"
        "except ImportError:\n"
        "    optional_pkg = None\n"
        "    thing = None\n"
        "\n"
        "try:\n"
        "    import tuple_guarded\n"
        "except (ImportError, ModuleNotFoundError):\n"
        "    tuple_guarded = None\n"
        "\n"
        "try:\n"
        "    import broad_guarded\n"
        "    from broad_pkg import thing2\n"
        "except Exception:\n"
        "    broad_guarded = None\n"
        "    thing2 = None\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "optional_pkg" not in msgs
    assert "other_optional" not in msgs
    assert "tuple_guarded" not in msgs
    # Body-structural rule: a try whose body is purely imports is treated
    # as an optional-import guard regardless of the except type.
    assert "broad_guarded" not in msgs
    assert "broad_pkg" not in msgs


def test_imports_vs_deps_try_with_real_logic_not_a_guard(tmp_path: Path) -> None:
    """Structural rule must not over-apply: a try with real code is not a guard."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "try:\n"
        "    import real_dep\n"
        "    value = real_dep.compute()\n"
        "except ValueError:\n"
        "    value = 0\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "real_dep" in msgs


def test_imports_vs_deps_skips_type_checking_block(tmp_path: Path) -> None:
    """B1 regression: imports under TYPE_CHECKING must not fire."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    import pandas\n"
        "    from sqlalchemy import Session\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "pandas" not in msgs
    assert "sqlalchemy" not in msgs


def test_imports_vs_deps_type_checking_else_is_runtime(tmp_path: Path) -> None:
    """F1 regression: the else branch of a TYPE_CHECKING if is runtime code."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from stub_only import Stub\n"
        "else:\n"
        "    from runtime_lib import runtime_fn\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "stub_only" not in msgs
    assert "runtime_lib" in msgs


def test_imports_vs_deps_bare_reraise_is_still_guard(tmp_path: Path) -> None:
    """F3: documented corner case. A try body composed purely of imports
    with a narrow ``except X: raise`` is structurally classified as an
    optional-import guard. This is a known conservative trade-off: the
    author *could* be using the try to scope a timing/retry wrapper, but
    the overwhelmingly common idiom is optional import. Flagging it would
    reintroduce the high-FP class that B1 eliminated.
    """
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "try:\n" "    import expensive\n" "except TimeoutError:\n" "    raise\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    # Documented FN: expensive is not flagged.
    assert "expensive" not in msgs


def test_imports_vs_deps_suppress_importerror_guard(tmp_path: Path) -> None:
    """contextlib.suppress(ImportError) is an optional-import guard."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "from contextlib import suppress\n"
        "\n"
        "with suppress(ImportError):\n"
        "    import optional_lib\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "optional_lib" not in msgs


def test_imports_vs_deps_suppress_attribute_form(tmp_path: Path) -> None:
    """contextlib.suppress(ImportError) via attribute form."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "import contextlib\n"
        "\n"
        "with contextlib.suppress(ImportError):\n"
        "    import optional_attr\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "optional_attr" not in msgs


def test_imports_vs_deps_suppress_module_not_found(tmp_path: Path) -> None:
    """suppress(ModuleNotFoundError) is also a guard."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "from contextlib import suppress\n"
        "\n"
        "with suppress(ModuleNotFoundError):\n"
        "    import mod_not_found_lib\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "mod_not_found_lib" not in msgs


def test_imports_vs_deps_suppress_valueerror_not_guard(tmp_path: Path) -> None:
    """suppress(ValueError) is NOT an import guard."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "from contextlib import suppress\n"
        "\n"
        "with suppress(ValueError):\n"
        "    import not_guarded_lib\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "not_guarded_lib" in msgs


def test_imports_vs_deps_regular_with_not_affected(tmp_path: Path) -> None:
    """Regular with blocks should not be treated as import guards."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "with open('config.txt') as f:\n" "    import inside_with\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "inside_with" in msgs


def test_imports_vs_deps_namespace_prefix_blocks_short_heads(tmp_path: Path) -> None:
    """F2 regression: py-cpuinfo must not silently satisfy ``import py``."""
    _write(
        tmp_path / "pyproject.toml",
        """\
[project]
name = "demo-app"
version = "0.1.0"
dependencies = ["py-cpuinfo>=9.0.0"]
""",
    )
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(tmp_path / "demo" / "main.py", "import py\n")
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "'py'" in msgs  # flagged, not silently accepted


def test_imports_vs_deps_namespace_prefix_accepts_long_head(tmp_path: Path) -> None:
    """G2: pin the intentional tradeoff that a 2-segment distribution with a
    >=4 char head adds its head to the namespace prefix set.

    This is a known FN risk: ``django-redis`` will silently satisfy a bare
    ``import django`` even though the real Django package is not declared.
    The tradeoff is deliberate — blocking it would require hard-coding
    hundreds of real namespace packages. If a future change tightens the
    rule (e.g. bumping the minimum segment count), this test will fail
    and force a conscious decision rather than a silent regression.
    """
    _write(
        tmp_path / "pyproject.toml",
        """\
[project]
name = "demo-app"
version = "0.1.0"
dependencies = ["django-redis>=5.0.0"]
""",
    )
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(tmp_path / "demo" / "main.py", "import django\n")
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    assert issues == []  # django-redis satisfies import django (intentional FN risk)


def test_imports_vs_deps_elif_type_checking_chain(tmp_path: Path) -> None:
    """G3: pin that ``elif TYPE_CHECKING:`` chains are fully handled.

    In AST, ``elif`` is parsed as ``If(orelse=[If(...)])``. The refactor
    to ``_dispatch_node`` was designed so that recursing into ``orelse``
    re-enters the guard check for the next ``If`` in the chain. Without
    an explicit test, that intent lives only in comments.
    """
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    import stub_a\n"
        "elif TYPE_CHECKING:\n"
        "    import stub_b\n"
        "else:\n"
        "    import runtime_c\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "stub_a" not in msgs
    assert "stub_b" not in msgs
    assert "runtime_c" in msgs


def test_imports_vs_deps_namespace_package_satisfies(tmp_path: Path) -> None:
    """P6 regression: ``import google.cloud.bigquery`` must not fire when
    any ``google-*`` distribution is declared."""
    _write(
        tmp_path / "pyproject.toml",
        """\
[project]
name = "demo-app"
version = "0.1.0"
dependencies = ["google-cloud-bigquery>=3.0"]
""",
    )
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "import google.cloud.bigquery\nfrom google.auth import default\n",
    )
    issues = ImportsVsDepsAnalyzer().analyze_project(tmp_path)
    assert issues == []


# ---------------------------------------------------------------- Docs vs entrypoints


def test_docs_vs_entrypoints_flags_undocumented_script(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(
        tmp_path / "README.md",
        "# Demo\n\nRun with:\n\n```\ndemo --help\n```\n",
    )
    issues = DocsVsEntrypointsAnalyzer().analyze_project(tmp_path)
    names = " ".join(i.message for i in issues)
    assert "ghost" in names
    # demo is documented
    assert "'demo'" not in names


def test_docs_vs_entrypoints_no_readme(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    issues = DocsVsEntrypointsAnalyzer().analyze_project(tmp_path)
    # Both scripts should be flagged when README is missing
    assert len(issues) == 2


# ---------------------------------------------------------------- Packaging parity


def test_packaging_parity_detects_changelog_drift(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [0.9.0] - 2025-01-01\n")
    issues = PackagingParityAnalyzer().analyze_project(tmp_path)
    kinds = [i.issue_type for i in issues]
    assert AnalysisIssueType.PACKAGING_VERSION_DRIFT in kinds


def test_packaging_parity_detects_readme_badge_drift(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(
        tmp_path / "README.md",
        "![badge](https://img.shields.io/badge/version-0.9.0-blue)\n",
    )
    issues = PackagingParityAnalyzer().analyze_project(tmp_path)
    kinds = [i.issue_type for i in issues]
    assert AnalysisIssueType.PACKAGING_VERSION_DRIFT in kinds


def test_packaging_parity_clean_project(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [1.2.3] - 2025-01-01\n")
    assert PackagingParityAnalyzer().analyze_project(tmp_path) == []


def test_packaging_parity_generic_repo_slug(tmp_path: Path) -> None:
    """B2 regression: patterns must be derived from pyproject, not literal."""
    _write(
        tmp_path / "pyproject.toml",
        """\
[project]
name = "widgets"
version = "2.0.0"

[project.urls]
Repository = "https://github.com/acme/widgets"
""",
    )
    _write(
        tmp_path / "README.md",
        "## Install\n\n```\npip install widgets==1.0.0\n```\n\n"
        "Use in CI:\n\n```\nuses: acme/widgets@v1.0.0\n```\n",
    )
    issues = PackagingParityAnalyzer().analyze_project(tmp_path)
    msgs = [i.message for i in issues]
    assert any("1.0.0" in m and "2.0.0" in m for m in msgs)
    # Two patterns should have matched (pip install + GitHub action tag)
    assert sum("1.0.0" in m for m in msgs) >= 2


# ---------------------------------------------------------------- Install artifact


ACTION_YML = """\
name: Demo
inputs:
  target:
    description: path
    required: false
  unused_flag:
    description: never read
    required: false
runs:
  using: docker
  image: Dockerfile.action
"""

ENTRYPOINT_SH = """\
#!/bin/bash
set -e
TARGET="${INPUT_TARGET:-.}"
echo "$TARGET"
"""

DOCKERFILE_MISSING_COPY = """\
FROM python:3.11-slim
COPY pyproject.toml README.md ./
COPY does_not_exist/ app/
"""


def test_install_artifact_flags_unused_input(tmp_path: Path) -> None:
    _write(tmp_path / "action.yml", ACTION_YML)
    _write(tmp_path / "scripts" / "action_entrypoint.sh", ENTRYPOINT_SH)
    issues = InstallArtifactParityAnalyzer().analyze_project(tmp_path)
    flagged = {
        re.search(r"input '([^']+)'", i.message).group(1) for i in issues if "input '" in i.message
    }
    assert flagged == {"unused_flag"}  # target is consumed via INPUT_TARGET


def test_install_artifact_flags_missing_copy(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "README.md", "x")
    _write(tmp_path / "Dockerfile.action", DOCKERFILE_MISSING_COPY)
    issues = InstallArtifactParityAnalyzer().analyze_project(tmp_path)
    msgs = " ".join(i.message for i in issues)
    assert "does_not_exist" in msgs


# ---------------------------------------------------------------- Canary — full engine


def test_engine_files_analyzed_excludes_synthetic(tmp_path: Path) -> None:
    """P1 regression: project-level synthetic results do not inflate count."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(tmp_path / "demo" / "main.py", "import requests\n")
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [0.1.0] - 2025-01-01\n")

    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.register_project_analyzer(ImportsVsDepsAnalyzer())
    engine.register_project_analyzer(PackagingParityAnalyzer())

    report = engine.analyze_path(str(tmp_path))

    # Both analyzers fired, so the report must contain at least two findings,
    # but files_analyzed must still reflect only real Python files scanned.
    assert len(report.get_all_issues()) >= 2
    real_results = [fr for fr in report.file_results if not fr.metadata.get("synthetic")]
    assert report.summary.files_analyzed == len(real_results)


def test_reporters_handle_project_findings(tmp_path: Path) -> None:
    """P3 regression: text and HTML reporters must render project issues."""
    from hefesto.reports.html_reporter import HTMLReporter
    from hefesto.reports.text_reporter import TextReporter

    _write(
        tmp_path / "pyproject.toml",
        """\
[project]
name = "demo-app"
version = "1.2.3"
dependencies = ["click>=8.0.0"]
""",
    )
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(tmp_path / "demo" / "main.py", "import requests\n")
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [0.9.0] - 2025-01-01\n")

    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.register_project_analyzer(ImportsVsDepsAnalyzer())
    engine.register_project_analyzer(PackagingParityAnalyzer())

    report = engine.analyze_path(str(tmp_path))

    text = TextReporter().generate(report)
    assert "UNDECLARED_DEPENDENCY" in text or "requests" in text
    assert "pyproject.toml" in text

    html = HTMLReporter().generate(report)
    assert "<html" in html.lower() or "<!doctype" in html.lower()
    assert "UNDECLARED_DEPENDENCY" in html or "requests" in html


def test_canary_engine_wires_project_analyzers(tmp_path: Path) -> None:
    """Real file containing a known violation per analyzer."""
    _write(
        tmp_path / "pyproject.toml",
        """\
[project]
name = "demo-app"
version = "1.2.3"
dependencies = ["click>=8.0.0"]

[project.scripts]
demo = "demo.cli:main"
ghost = "demo.cli:ghost"
""",
    )
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(
        tmp_path / "demo" / "main.py",
        "import click\nimport requests\n",
    )
    _write(
        tmp_path / "README.md",
        "# Demo\n\n```\ndemo --help\n```\n"
        "Version: ![badge](https://img.shields.io/badge/version-0.9.0-blue)\n",
    )
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [0.9.0] - 2025-01-01\n")
    _write(tmp_path / "action.yml", ACTION_YML)
    _write(tmp_path / "scripts" / "action_entrypoint.sh", ENTRYPOINT_SH)

    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.register_project_analyzer(ImportsVsDepsAnalyzer())
    engine.register_project_analyzer(DocsVsEntrypointsAnalyzer())
    engine.register_project_analyzer(PackagingParityAnalyzer())
    engine.register_project_analyzer(InstallArtifactParityAnalyzer())

    report = engine.analyze_path(str(tmp_path))
    all_issues = report.get_all_issues()
    kinds = {issue.issue_type for issue in all_issues}

    assert AnalysisIssueType.UNDECLARED_DEPENDENCY in kinds
    assert AnalysisIssueType.DOCS_ENTRYPOINT_DRIFT in kinds
    assert AnalysisIssueType.PACKAGING_VERSION_DRIFT in kinds
    assert AnalysisIssueType.INSTALL_ARTIFACT_DRIFT in kinds
