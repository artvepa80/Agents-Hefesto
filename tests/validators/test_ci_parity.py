"""
Tests for CI Parity Checker.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hefesto.validators.ci_parity import CIParityChecker, ParityIssue, Severity


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create .github/workflows directory
        workflows_dir = project_root / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        yield project_root


@pytest.fixture
def sample_workflow():
    """Sample GitHub Actions workflow YAML."""
    return """
name: Tests
on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Run flake8
        run: flake8 hefesto/ --max-line-length=100 --extend-ignore=E203,W503
      - name: Run tests
        run: pytest
"""


def test_checker_initialization(temp_project):
    """Test checker initialization."""
    checker = CIParityChecker(temp_project)
    assert checker.project_root == temp_project
    assert checker.ci_workflow is None  # No workflow file yet


def test_find_ci_workflow(temp_project, sample_workflow):
    """Test finding CI workflow file."""
    # Create tests.yml
    workflow_file = temp_project / ".github" / "workflows" / "tests.yml"
    workflow_file.write_text(sample_workflow)

    checker = CIParityChecker(temp_project)
    assert checker.ci_workflow == workflow_file
    assert checker.ci_workflow.exists()


def test_find_ci_workflow_alternative_names(temp_project, sample_workflow):
    """Test finding workflow with alternative names."""
    # Create ci.yml instead of tests.yml
    workflow_file = temp_project / ".github" / "workflows" / "ci.yml"
    workflow_file.write_text(sample_workflow)

    checker = CIParityChecker(temp_project)
    assert checker.ci_workflow == workflow_file


@patch("subprocess.run")
def test_get_tool_version_success(mock_run):
    """Test getting tool version successfully."""
    mock_run.return_value = MagicMock(returncode=0, stdout="flake8 5.0.4 (pycodestyle: 2.10.0)")

    checker = CIParityChecker()
    version = checker._get_tool_version("flake8")

    assert version == "5.0.4"
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_get_tool_version_not_found(mock_run):
    """Test handling missing tool."""
    mock_run.side_effect = FileNotFoundError()

    checker = CIParityChecker()
    version = checker._get_tool_version("nonexistent-tool")

    assert version is None


def test_get_python_version():
    """Test getting local Python version."""
    checker = CIParityChecker()
    version = checker._get_python_version()

    # Should return format like "3.10" or "3.11"
    assert isinstance(version, str)
    assert "." in version
    parts = version.split(".")
    assert len(parts) == 2
    assert parts[0] == "3"  # Python 3.x


def test_extract_ci_python_versions(temp_project, sample_workflow):
    """Test extracting Python versions from CI workflow."""
    workflow_file = temp_project / ".github" / "workflows" / "tests.yml"
    workflow_file.write_text(sample_workflow)

    checker = CIParityChecker(temp_project)
    workflow = checker._parse_ci_workflow()
    versions = checker._extract_ci_python_versions(workflow)

    assert "3.10" in versions
    assert "3.11" in versions
    assert "3.12" in versions


def test_extract_flake8_config_from_ci(temp_project, sample_workflow):
    """Test extracting Flake8 config from CI."""
    workflow_file = temp_project / ".github" / "workflows" / "tests.yml"
    workflow_file.write_text(sample_workflow)

    checker = CIParityChecker(temp_project)
    workflow = checker._parse_ci_workflow()
    config = checker._extract_flake8_config_from_ci(workflow)

    assert config["max-line-length"] == "100"
    assert config["extend-ignore"] == "E203,W503"


def test_get_local_flake8_config_from_file(temp_project):
    """Test reading local Flake8 config from .flake8 file."""
    flake8_file = temp_project / ".flake8"
    flake8_file.write_text("""
[flake8]
max-line-length = 100
extend-ignore = E203,W503
""")

    checker = CIParityChecker(temp_project)
    config = checker._get_local_flake8_config()

    assert config["max-line-length"] == "100"
    assert config["extend-ignore"] == "E203,W503"


def test_get_local_flake8_config_from_setup_cfg(temp_project):
    """Test reading local Flake8 config from setup.cfg."""
    setup_cfg = temp_project / "setup.cfg"
    setup_cfg.write_text("""
[metadata]
name = test-project

[flake8]
max-line-length = 88
ignore = E501
""")

    checker = CIParityChecker(temp_project)
    config = checker._get_local_flake8_config()

    assert config["max-line-length"] == "88"
    assert config["ignore"] == "E501"


@patch("hefesto.validators.ci_parity.CIParityChecker._get_python_version")
def test_check_python_version_mismatch(mock_python_version, temp_project, sample_workflow):
    """Test detecting Python version mismatch."""
    # Mock local Python version as 3.9 (not in CI matrix)
    mock_python_version.return_value = "3.9"

    workflow_file = temp_project / ".github" / "workflows" / "tests.yml"
    workflow_file.write_text(sample_workflow)

    checker = CIParityChecker(temp_project)
    issues = checker.check_python_version()

    assert len(issues) == 1
    assert issues[0].severity == Severity.MEDIUM
    assert "3.9" in issues[0].message


@patch("hefesto.validators.ci_parity.CIParityChecker._get_python_version")
def test_check_python_version_match(mock_python_version, temp_project, sample_workflow):
    """Test Python version matches CI."""
    # Mock local Python version as 3.11 (in CI matrix)
    mock_python_version.return_value = "3.11"

    workflow_file = temp_project / ".github" / "workflows" / "tests.yml"
    workflow_file.write_text(sample_workflow)

    checker = CIParityChecker(temp_project)
    issues = checker.check_python_version()

    assert len(issues) == 0


@patch("hefesto.validators.ci_parity.CIParityChecker._get_tool_version")
def test_check_tool_versions_missing(mock_tool_version):
    """Test detecting missing tools."""
    # Mock all tools as not found
    mock_tool_version.return_value = None

    checker = CIParityChecker()
    issues = checker.check_tool_versions()

    # Should detect 4 missing tools: flake8, black, isort, pytest
    assert len(issues) == 4
    assert all(issue.severity == Severity.HIGH for issue in issues)
    assert all("not found" in issue.message.lower() for issue in issues)


@patch("hefesto.validators.ci_parity.CIParityChecker._get_tool_version")
def test_check_tool_versions_present(mock_tool_version):
    """Test all tools present."""
    # Mock all tools as installed
    mock_tool_version.return_value = "1.0.0"

    checker = CIParityChecker()
    issues = checker.check_tool_versions()

    assert len(issues) == 0


def test_check_flake8_config_mismatch(temp_project, sample_workflow):
    """Test detecting Flake8 config mismatch."""
    # Create CI workflow with max-line-length=100
    workflow_file = temp_project / ".github" / "workflows" / "tests.yml"
    workflow_file.write_text(sample_workflow)

    # Create local config with max-line-length=88 (mismatch)
    flake8_file = temp_project / ".flake8"
    flake8_file.write_text("""
[flake8]
max-line-length = 88
""")

    checker = CIParityChecker(temp_project)
    issues = checker.check_flake8_config()

    # Should detect max-line-length mismatch
    assert len(issues) >= 1
    max_length_issue = [i for i in issues if "max-line-length" in i.message][0]
    assert max_length_issue.severity == Severity.HIGH
    assert "88" in max_length_issue.local_value
    assert "100" in max_length_issue.ci_value


def test_check_flake8_config_ignore_rules_mismatch(temp_project, sample_workflow):
    """Test detecting ignore rules mismatch."""
    workflow_file = temp_project / ".github" / "workflows" / "tests.yml"
    workflow_file.write_text(sample_workflow)

    # Create local config missing some ignore rules
    flake8_file = temp_project / ".flake8"
    flake8_file.write_text("""
[flake8]
max-line-length = 100
extend-ignore = E203
""")

    checker = CIParityChecker(temp_project)
    issues = checker.check_flake8_config()

    # Should detect missing W503 rule
    assert len(issues) >= 1
    ignore_issue = [i for i in issues if "ignore rules" in i.message.lower()]
    assert len(ignore_issue) > 0
    assert "W503" in ignore_issue[0].message


def test_check_all_combines_all_checks(temp_project, sample_workflow):
    """Test check_all runs all validators and combines results."""
    workflow_file = temp_project / ".github" / "workflows" / "tests.yml"
    workflow_file.write_text(sample_workflow)

    checker = CIParityChecker(temp_project)

    with (
        patch.object(checker, "check_python_version") as mock_python,
        patch.object(checker, "check_tool_versions") as mock_tools,
        patch.object(checker, "check_flake8_config") as mock_flake8,
    ):

        mock_python.return_value = [
            ParityIssue(
                severity=Severity.MEDIUM,
                category="Python",
                local_value="3.9",
                ci_value="3.10",
                message="Test",
                fix_suggestion="Fix",
            )
        ]
        mock_tools.return_value = [
            ParityIssue(
                severity=Severity.HIGH,
                category="Tools",
                local_value="missing",
                ci_value="present",
                message="Test",
                fix_suggestion="Fix",
            )
        ]
        mock_flake8.return_value = []

        issues = checker.check_all()

        # Should have called all three checks
        mock_python.assert_called_once()
        mock_tools.assert_called_once()
        mock_flake8.assert_called_once()

        # Should combine results
        assert len(issues) == 2


def test_check_all_sorts_by_severity(temp_project):
    """Test check_all sorts issues by severity (HIGH first)."""
    checker = CIParityChecker(temp_project)

    with (
        patch.object(checker, "check_python_version") as mock_python,
        patch.object(checker, "check_tool_versions") as mock_tools,
        patch.object(checker, "check_flake8_config") as mock_flake8,
    ):

        # Return issues in mixed severity order
        mock_python.return_value = [
            ParityIssue(
                severity=Severity.LOW,
                category="Python",
                local_value="a",
                ci_value="b",
                message="Low priority",
                fix_suggestion="Fix",
            )
        ]
        mock_tools.return_value = [
            ParityIssue(
                severity=Severity.HIGH,
                category="Tools",
                local_value="c",
                ci_value="d",
                message="High priority",
                fix_suggestion="Fix",
            )
        ]
        mock_flake8.return_value = [
            ParityIssue(
                severity=Severity.MEDIUM,
                category="Config",
                local_value="e",
                ci_value="f",
                message="Medium priority",
                fix_suggestion="Fix",
            )
        ]

        issues = checker.check_all()

        # Should be sorted: HIGH, MEDIUM, LOW
        assert issues[0].severity == Severity.HIGH
        assert issues[1].severity == Severity.MEDIUM
        assert issues[2].severity == Severity.LOW


def test_print_report_no_issues(capsys):
    """Test printing report with no issues."""
    checker = CIParityChecker()
    checker.print_report([])

    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "matches CI" in captured.out


def test_print_report_with_issues(capsys):
    """Test printing report with issues."""
    issues = [
        ParityIssue(
            severity=Severity.HIGH,
            category="Test Category",
            local_value="local",
            ci_value="ci",
            message="Test message",
            fix_suggestion="Test fix",
        )
    ]

    checker = CIParityChecker()
    checker.print_report(issues)

    captured = capsys.readouterr()
    assert "ISSUES FOUND" in captured.out
    assert "HIGH Priority" in captured.out
    assert "Test Category" in captured.out
    assert "Test message" in captured.out
