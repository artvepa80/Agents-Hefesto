"""
Path sandbox enforcement for Hefesto API.

Ensures all file paths resolve under a trusted workspace root,
preventing directory traversal attacks.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from pathlib import Path


def resolve_under_root(path: str, root: Path) -> Path:
    """
    Resolve *path* and ensure it lives under *root*.

    Args:
        path: Relative or absolute file/dir path.
        root: Trusted workspace root directory.

    Returns:
        Resolved absolute Path guaranteed to be under root.

    Raises:
        ValueError: If the resolved path escapes the root.
    """
    root = root.resolve()
    candidate = Path(path)

    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / candidate).resolve()

    # Python 3.9+ has is_relative_to; fallback for 3.8
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(
            f"Path escapes workspace root: {path!r} "
            f"resolves to {resolved} which is outside {root}"
        )

    return resolved
