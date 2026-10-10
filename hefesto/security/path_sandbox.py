"""
Path sandbox enforcement for Hefesto API.

Ensures all file paths resolve under a trusted workspace root,
preventing directory traversal attacks.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import os
from pathlib import Path


def resolve_under_root(path: str, root: Path) -> Path:
    """
    Resolve *path* and ensure it lives under *root*.

    The path is normalized with ``os.path.realpath`` (symlinks and ``..``
    resolved) and then checked against the root prefix, the sanitizer
    pattern that static analyzers such as CodeQL recognize.

    Args:
        path: Relative or absolute file/dir path.
        root: Trusted workspace root directory.

    Returns:
        Resolved absolute Path guaranteed to be under root.

    Raises:
        ValueError: If the resolved path escapes the root.
    """
    root_real = os.path.realpath(root)
    resolved = os.path.realpath(os.path.join(root_real, path))
    if not resolved.startswith(root_real):
        raise ValueError(_escape_message(path, resolved, root_real))
    rest = resolved[len(root_real) :]
    if rest and not rest.startswith(os.sep) and not root_real.endswith(os.sep):
        # A sibling sharing the prefix, e.g. /work/app-evil for root /work/app.
        raise ValueError(_escape_message(path, resolved, root_real))
    return Path(resolved)


def _escape_message(path: str, resolved: str, root: str) -> str:
    return f"Path escapes workspace root: {path!r} resolves to {resolved} which is outside {root}"
