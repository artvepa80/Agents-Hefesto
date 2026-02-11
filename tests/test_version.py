import importlib
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest


def test_version_is_string():
    """Ensure hefesto.__version__ is exposed as a string."""
    import hefesto

    assert isinstance(hefesto.__version__, str)
    assert len(hefesto.__version__) > 0


def test_version_fallback(monkeypatch):
    """
    Simulate PackageNotFoundError to verify fallback behavior.
    """
    # Import the module
    m = importlib.import_module("hefesto.__version__")

    def mock(_name: str):
        raise PackageNotFoundError(_name)

    # Patch the _dist_version function constant in the module
    monkeypatch.setattr(m, "_dist_version", mock)

    # Test get_version() directly - no reload needed
    assert m.get_version() == "0.0.0+dev"


def test_version_success_mock(monkeypatch):
    """
    Simulate successful version retrieval.
    """
    m = importlib.import_module("hefesto.__version__")

    monkeypatch.setattr(m, "_dist_version", lambda _name: "9.9.9")

    assert m.get_version() == "9.9.9"


def test_cli_version_flag_works():
    """
    Verify `hefesto --version` works (integration-ish).
    """
    from click.testing import CliRunner

    from hefesto.cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()

    # Verify the actual version string is present
    import hefesto

    assert hefesto.__version__ in result.output


def test_version_drift():
    """
    Verify that hefesto.__version__ matches pyproject.toml version.
    This ensures the single source of truth is respected.
    """
    import sys

    import hefesto

    # Robustly find pyproject.toml by walking up from this file
    curr = Path(__file__).resolve().parent
    pyproject_path = None
    for _ in range(5):  # Look up to 5 levels
        candidate = curr / "pyproject.toml"
        if candidate.exists():
            pyproject_path = candidate
            break
        if curr.parent == curr:  # System root reached
            break
        curr = curr.parent

    if not pyproject_path:
        pytest.skip("pyproject.toml not found in parents, skipping drift test")

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomli as tomllib
        except ImportError:
            pytest.skip("tomllib/tomli not available for parsing pyproject.toml")

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    project_version = data["project"]["version"]

    # Verify strict equality to prevent any drift
    assert (
        hefesto.__version__ == project_version
    ), f"Version drift detected! Runtime={hefesto.__version__}, pyproject={project_version}"
