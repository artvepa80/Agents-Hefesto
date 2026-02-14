"""
Hefesto version information.

The version is now read dynamically from package metadata to ensure
CLI, API, and package metadata stay in sync.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version


def get_version() -> str:
    try:
        return _dist_version("hefesto-ai")
    except PackageNotFoundError:
        # Fallback for source execution without install
        return "0.0.0+dev"


__version__ = get_version()
