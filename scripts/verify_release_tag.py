#!/usr/bin/env python3
"""
Verify that the git tag matches the version in pyproject.toml.
Used in CI/CD pipelines to prevent release drift.
"""

import argparse
import os
import sys
from pathlib import Path

# Third-party dependencies (must be installed via [ci] or [dev] extras)
try:
    from packaging.version import InvalidVersion, Version
except ImportError:
    print("Error: 'packaging' not found. Install via 'pip install .[ci]'", file=sys.stderr)
    sys.exit(1)

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        print(
            "Error: 'tomli' not found (required for Python < 3.11). Install via 'pip install .[ci]'",
            file=sys.stderr,
        )
        sys.exit(1)


def get_project_version(root_path: Path) -> str:
    """Read version from pyproject.toml."""
    pyproject_path = root_path / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Error: pyproject.toml not found at {pyproject_path}", file=sys.stderr)
        sys.exit(1)

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    try:
        name = data["project"]["name"]
        if name != "hefesto-ai":
            print(f"Error: project.name '{name}' != 'hefesto-ai'", file=sys.stderr)
            sys.exit(1)
        return data["project"]["version"]
    except KeyError as e:
        print(f"Error: {e} not found in pyproject.toml", file=sys.stderr)
        sys.exit(1)


def verify_tag(tag: str, project_version: str) -> bool:
    """
    Compare git tag with project version.
    Current policy: Strict equality of normalized versions.
    Tags must start with 'v'.
    """
    if not tag.startswith("v"):
        print(f"Error: Tag '{tag}' must start with 'v'", file=sys.stderr)
        return False

    tag_clean = tag[1:]  # Remove 'v'

    try:
        tag_ver = Version(tag_clean)
        proj_ver = Version(project_version)
    except InvalidVersion as e:
        print(f"Error: Invalid version format: {e}", file=sys.stderr)
        return False

    if tag_ver != proj_ver:
        print(f"ERROR: tag version ({tag_ver}) != pyproject version ({proj_ver})", file=sys.stderr)
        print(f"  Tag raw: {tag}", file=sys.stderr)
        print(f"  Project raw: {project_version}", file=sys.stderr)
        return False

    print(f"SUCCESS: Tag '{tag}' matches pyproject version '{project_version}'")
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify release tag matches pyproject.toml")
    parser.add_argument(
        "--tag", help="Git tag (e.g., v1.2.3). Defaults to GITHUB_REF_NAME env var."
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Path to project root (directory containing pyproject.toml)",
    )

    args = parser.parse_args()

    tag = args.tag or os.environ.get("GITHUB_REF_NAME")

    if not tag:
        print("Error: No tag provided via --tag or GITHUB_REF_NAME", file=sys.stderr)
        sys.exit(1)

    root_path = Path(args.project_root).resolve()
    project_version = get_project_version(root_path)

    if not verify_tag(tag, project_version):
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
