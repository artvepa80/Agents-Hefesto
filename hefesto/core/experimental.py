"""Experimental features: ``--experimental`` and ``experimental:`` in .hefesto.yaml.

An experimental feature is one whose results have not been measured yet. It is
off by default, and the output of a run is unchanged while it is off.
"""

from typing import Dict, FrozenSet, Iterable, List, Tuple, Union

DEFINITION = (
    "Experimental features are off by default. Their results have not been "
    "measured yet, and a run without them gives the same output as before."
)

# name -> what it turns on
FEATURES: Dict[str, str] = {
    "lang-security": "run the C#, Go, Rust, C and C++ security rules (docs/ANALYSIS_RULES.md)",
    "c-cpp": "analyze C and C++ files (.c, .h, .cpp, .cc, .cxx, .c++, .hpp, .hh, .hxx)",
}

# name -> release where it became on by default (a warning, not an error)
GRADUATED: Dict[str, str] = {}


class ExperimentalError(ValueError):
    """An unknown experimental feature name."""


def _names(value: Union[str, Iterable[str], None]) -> List[str]:
    if value is None:
        return []
    items = value.split(",") if isinstance(value, str) else list(value)
    return [str(item).strip().lower() for item in items if str(item).strip()]


def parse(value: Union[str, Iterable[str], None]) -> Tuple[FrozenSet[str], List[str]]:
    """Return (enabled names, warnings); raise ExperimentalError on unknown names."""
    names = _names(value)
    unknown = sorted({n for n in names if n not in FEATURES and n not in GRADUATED})
    if unknown:
        known = ", ".join(sorted(FEATURES)) or "none"
        raise ExperimentalError(
            f"unknown experimental feature(s): {', '.join(unknown)} (known: {known})"
        )
    warnings = [
        f"'{n}' is no longer experimental (on by default since {GRADUATED[n]}); "
        "remove it from the experimental list"
        for n in sorted({n for n in names if n in GRADUATED})
    ]
    return frozenset(n for n in names if n in FEATURES), warnings


__all__ = ["DEFINITION", "FEATURES", "GRADUATED", "ExperimentalError", "parse"]
