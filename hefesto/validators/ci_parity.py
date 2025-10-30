"""
CI Parity Checker - Detects discrepancies between local and CI environments.

This validator prevents "works on my machine" issues by comparing:
- Tool versions (flake8, black, isort, pytest)
- Flake8 configuration (max-line-length, ignore rules)
- Python version compatibility

Learned from: v4.0.1 release where 20+ Flake8 errors passed locally but failed in CI.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml


class Severity(Enum):
    """Severity levels for parity issues."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ParityIssue:
    """Represents a parity discrepancy between local and CI."""

    severity: Severity
    category: str
    local_value: str
    ci_value: str
    message: str
    fix_suggestion: str


class CIParityChecker:
    """
    Checks for discrepancies between local and CI environments.

    Usage:
        checker = CIParityChecker()
        issues = checker.check_all()
        if issues:
            checker.print_report(issues)
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize CI Parity Checker.

        Args:
            project_root: Root directory of project. If None, uses current directory.
        """
        self.project_root = project_root or Path.cwd()
        self.ci_workflow = self._find_ci_workflow()

    def _find_ci_workflow(self) -> Optional[Path]:
        """Find GitHub Actions workflow file."""
        workflows_dir = self.project_root / ".github" / "workflows"
        if not workflows_dir.exists():
            return None

        # Look for common names
        for name in ["tests.yml", "test.yml", "ci.yml", "main.yml"]:
            workflow = workflows_dir / name
            if workflow.exists():
                return workflow

        # If none found, return first .yml file
        yml_files = list(workflows_dir.glob("*.yml"))
        return yml_files[0] if yml_files else None

    def _get_tool_version(self, tool: str) -> Optional[str]:
        """Get local version of a tool."""
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Extract version number from output
                version_match = re.search(r"(\d+\.\d+\.?\d*)", result.stdout)
                if version_match:
                    return version_match.group(1)
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _get_python_version(self) -> str:
        """Get local Python version."""
        return f"{sys.version_info.major}.{sys.version_info.minor}"

    def _parse_ci_workflow(self) -> Optional[Dict]:
        """Parse CI workflow YAML file."""
        if not self.ci_workflow or not self.ci_workflow.exists():
            return None

        try:
            with open(self.ci_workflow) as f:
                return yaml.safe_load(f)
        except Exception:
            return None

    def _extract_ci_python_versions(self, workflow: Dict) -> List[str]:
        """Extract Python versions used in CI."""
        versions = []

        # Look for matrix strategy
        for job_name, job_config in workflow.get("jobs", {}).items():
            if "strategy" in job_config:
                matrix = job_config["strategy"].get("matrix", {})
                if "python-version" in matrix:
                    py_versions = matrix["python-version"]
                    if isinstance(py_versions, list):
                        versions.extend([str(v) for v in py_versions])

            # Also check setup-python action
            steps = job_config.get("steps", [])
            for step in steps:
                if "uses" in step and "setup-python" in step["uses"]:
                    with_config = step.get("with", {})
                    if "python-version" in with_config:
                        versions.append(str(with_config["python-version"]))

        return list(set(versions))  # Remove duplicates

    def _extract_flake8_config_from_ci(self, workflow: Dict) -> Dict[str, str]:
        """Extract Flake8 configuration from CI workflow."""
        config = {}

        for job_name, job_config in workflow.get("jobs", {}).items():
            steps = job_config.get("steps", [])
            for step in steps:
                if "run" in step and "flake8" in step["run"]:
                    command = step["run"]

                    # Extract max-line-length
                    max_length_match = re.search(r"--max-line-length[=\s]+(\d+)", command)
                    if max_length_match:
                        config["max-line-length"] = max_length_match.group(1)

                    # Extract extend-ignore
                    ignore_match = re.search(r"--extend-ignore[=\s]+([A-Z0-9,]+)", command)
                    if ignore_match:
                        config["extend-ignore"] = ignore_match.group(1)

                    # Extract ignore (older style)
                    ignore_match_alt = re.search(r"--ignore[=\s]+([A-Z0-9,]+)", command)
                    if ignore_match_alt and "extend-ignore" not in config:
                        config["ignore"] = ignore_match_alt.group(1)

        return config

    def _get_local_flake8_config(self) -> Dict[str, str]:
        """Get local Flake8 configuration."""
        config = {}

        # Check .flake8 file
        flake8_file = self.project_root / ".flake8"
        if flake8_file.exists():
            with open(flake8_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("max-line-length"):
                        config["max-line-length"] = line.split("=")[1].strip()
                    elif line.startswith("extend-ignore") or line.startswith("ignore"):
                        key = "extend-ignore" if "extend" in line else "ignore"
                        config[key] = line.split("=")[1].strip()

        # Check setup.cfg
        setup_cfg = self.project_root / "setup.cfg"
        if setup_cfg.exists():
            in_flake8_section = False
            with open(setup_cfg) as f:
                for line in f:
                    line = line.strip()
                    if line == "[flake8]":
                        in_flake8_section = True
                        continue
                    if line.startswith("["):
                        in_flake8_section = False
                    if in_flake8_section:
                        if line.startswith("max-line-length"):
                            config["max-line-length"] = line.split("=")[1].strip()
                        elif "ignore" in line:
                            key = "extend-ignore" if "extend" in line else "ignore"
                            config[key] = line.split("=")[1].strip()

        # Check pyproject.toml
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject) as f:
                content = f.read()
                if "[tool.flake8]" in content:
                    # Simple extraction (full TOML parsing would be better)
                    max_length_match = re.search(r'max-line-length\s*=\s*["\']?(\d+)', content)
                    if max_length_match:
                        config["max-line-length"] = max_length_match.group(1)

        return config

    def check_python_version(self) -> List[ParityIssue]:
        """Check if local Python version matches CI."""
        issues = []

        workflow = self._parse_ci_workflow()
        if not workflow:
            return issues

        ci_versions = self._extract_ci_python_versions(workflow)
        local_version = self._get_python_version()

        if not ci_versions:
            return issues

        if local_version not in ci_versions:
            issues.append(
                ParityIssue(
                    severity=Severity.MEDIUM,
                    category="Python Version",
                    local_value=local_version,
                    ci_value=", ".join(ci_versions),
                    message=f"Local Python {local_version} not in CI matrix {ci_versions}",
                    fix_suggestion=f"Consider testing with Python {ci_versions[0]} locally: pyenv install {ci_versions[0]}",  # noqa: E501
                )
            )

        return issues

    def check_tool_versions(self) -> List[ParityIssue]:
        """Check if tool versions are compatible."""
        issues = []

        tools = ["flake8", "black", "isort", "pytest"]

        for tool in tools:
            local_version = self._get_tool_version(tool)
            if not local_version:
                issues.append(
                    ParityIssue(
                        severity=Severity.HIGH,
                        category="Tool Installation",
                        local_value="Not installed",
                        ci_value="Installed",
                        message=f"{tool} not found locally but used in CI",
                        fix_suggestion=f"Install {tool}: pip install {tool}",
                    )
                )

        return issues

    def check_flake8_config(self) -> List[ParityIssue]:
        """Check if Flake8 configuration matches CI."""
        issues = []

        workflow = self._parse_ci_workflow()
        if not workflow:
            return issues

        ci_config = self._extract_flake8_config_from_ci(workflow)
        local_config = self._get_local_flake8_config()

        # Check max-line-length
        if "max-line-length" in ci_config:
            ci_max = ci_config["max-line-length"]
            local_max = local_config.get("max-line-length", "79")  # flake8 default

            if ci_max != local_max:
                issues.append(
                    ParityIssue(
                        severity=Severity.HIGH,
                        category="Flake8 Config",
                        local_value=f"max-line-length={local_max}",
                        ci_value=f"max-line-length={ci_max}",
                        message=f"Flake8 max-line-length mismatch: local={local_max}, CI={ci_max}",
                        fix_suggestion=f"Update .flake8 or setup.cfg with: max-line-length = {ci_max}",  # noqa: E501
                    )
                )

        # Check ignore/extend-ignore rules
        ci_ignore = ci_config.get("extend-ignore") or ci_config.get("ignore", "")
        local_ignore = local_config.get("extend-ignore") or local_config.get("ignore", "")

        if ci_ignore:
            ci_rules = set(ci_ignore.replace(" ", "").split(","))
            local_rules = set(local_ignore.replace(" ", "").split(","))

            missing_rules = ci_rules - local_rules
            if missing_rules:
                issues.append(
                    ParityIssue(
                        severity=Severity.HIGH,
                        category="Flake8 Config",
                        local_value=f"ignore={local_ignore or 'none'}",
                        ci_value=f"extend-ignore={ci_ignore}",
                        message=f"Flake8 ignore rules missing locally: {', '.join(missing_rules)}",
                        fix_suggestion=f"Update .flake8 or setup.cfg with: extend-ignore = {ci_ignore}",  # noqa: E501
                    )
                )

        return issues

    def check_all(self) -> List[ParityIssue]:
        """Run all parity checks."""
        issues = []

        issues.extend(self.check_python_version())
        issues.extend(self.check_tool_versions())
        issues.extend(self.check_flake8_config())

        # Sort by severity
        severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        issues.sort(key=lambda x: severity_order[x.severity])

        return issues

    def print_report(self, issues: List[ParityIssue]) -> None:
        """Print a formatted report of parity issues."""
        if not issues:
            print("\n✅ CI Parity Check: PASS")
            print("Local environment matches CI configuration.")
            return

        print("\n⚠️  CI Parity Check: ISSUES FOUND")
        print("=" * 80)

        # Group by severity
        high = [i for i in issues if i.severity == Severity.HIGH]
        medium = [i for i in issues if i.severity == Severity.MEDIUM]
        low = [i for i in issues if i.severity == Severity.LOW]

        if high:
            print(f"\n🔥 HIGH Priority ({len(high)} issues)")
            print("-" * 80)
            for issue in high:
                self._print_issue(issue)

        if medium:
            print(f"\n⚠️  MEDIUM Priority ({len(medium)} issues)")
            print("-" * 80)
            for issue in medium:
                self._print_issue(issue)

        if low:
            print(f"\n💡 LOW Priority ({len(low)} issues)")
            print("-" * 80)
            for issue in low:
                self._print_issue(issue)

        print("\n" + "=" * 80)
        print(f"Total: {len(issues)} issue(s) - Fix these to prevent CI failures")

    def _print_issue(self, issue: ParityIssue) -> None:
        """Print a single parity issue."""
        print(f"\n📋 {issue.category}")
        print(f"   Message: {issue.message}")
        print(f"   Local:   {issue.local_value}")
        print(f"   CI:      {issue.ci_value}")
        print(f"   Fix:     {issue.fix_suggestion}")


def main():
    """CLI entry point."""
    checker = CIParityChecker()
    issues = checker.check_all()
    checker.print_report(issues)

    # Exit with error code if HIGH priority issues found
    high_priority = [i for i in issues if i.severity == Severity.HIGH]
    if high_priority:
        sys.exit(1)


if __name__ == "__main__":
    main()
