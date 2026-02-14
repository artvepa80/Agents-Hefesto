"""
HEFESTO - AI-Powered Code Quality Guardian (Community Edition)

Static code analysis, security scanning, and quality assurance.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from hefesto.__version__ import __version__

__all__ = [
    "__version__",
]


def get_info() -> dict:
    """Get package information."""
    return {
        "version": __version__,
        "edition": "community",
        "license": "MIT",
    }
