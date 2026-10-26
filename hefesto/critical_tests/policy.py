"""Parse and validate the ``critical_tests`` section of .hefesto.yaml.

Schema::

    critical_tests:
      enforcement: warn          # optional, warn (default) or block
      entries:
        - id: authorization      # unique
          requirement: "Users must not access resources they do not own."
          tests:                 # pytest node IDs, without [param] suffixes
            - tests/test_auth.py::test_denies_unauthorized_access
            - tests/test_auth.py::TestAdmin::test_admin_only
          enforcement: block     # optional, defaults to the section value

Unknown keys anywhere in the section are an error.

Copyright 2026 Narapa LLC, Miami, Florida
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from hefesto.config.project_config import ConfigError

ENFORCEMENTS = ("warn", "block")
DEFAULT_ENFORCEMENT = "warn"

_SECTION_KEYS = ("enforcement", "entries")
_ENTRY_KEYS = ("id", "requirement", "tests", "enforcement")


@dataclass(frozen=True)
class TestRef:
    """One pytest node ID split into a repo-relative path and a qualname."""

    __test__ = False  # not a pytest test class

    path: str
    qualname: str  # "test_x" or "TestClass::test_x"

    @property
    def nodeid(self) -> str:
        return f"{self.path}::{self.qualname}"


@dataclass(frozen=True)
class CriticalTestEntry:
    id: str
    requirement: str
    tests: Tuple[TestRef, ...]
    enforcement: str


@dataclass(frozen=True)
class CriticalTestsPolicy:
    enforcement: str
    entries: Tuple[CriticalTestEntry, ...]

    def tests_by_file(self) -> Dict[str, List[Tuple[str, str]]]:
        """``{path: [(entry_id, qualname), ...]}`` in config order."""
        grouped: Dict[str, List[Tuple[str, str]]] = {}
        for entry in self.entries:
            for ref in entry.tests:
                grouped.setdefault(ref.path, []).append((entry.id, ref.qualname))
        return grouped


def _err(where: str, message: str) -> ConfigError:
    return ConfigError(f"critical_tests: {where}{message}")


def _check_keys(where: str, data: Dict[Any, Any], allowed: Tuple[str, ...]) -> None:
    for key in data:
        if key not in allowed:
            raise _err(where, f"unknown key '{key}' (supported: {', '.join(allowed)})")


def _enforcement(where: str, value: Any, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or value.lower() not in ENFORCEMENTS:
        raise _err(where, f"'enforcement' must be one of {', '.join(ENFORCEMENTS)} (got {value!r})")
    return value.lower()


def _non_empty_str(where: str, key: str, data: Dict[Any, Any]) -> str:
    if key not in data or data[key] is None:
        raise _err(where, f"'{key}' is required")
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise _err(where, f"'{key}' must be a non-empty string")
    return value.strip()


def parse_nodeid(where: str, value: Any) -> TestRef:
    """Validate one pytest node ID (``path.py::[Class::]test``)."""
    if not isinstance(value, str):
        raise _err(f"{where}: ", f"test must be a string (got {value!r})")
    nodeid = value.strip()
    if "[" in nodeid or "]" in nodeid:
        raise _err(
            f"{where}: ",
            f"{nodeid!r}: list the test function without a [param] suffix",
        )
    path, sep, rest = nodeid.partition("::")
    if path.startswith("./"):
        path = path[2:]
    parts = rest.split("::") if sep else []
    if (
        not sep
        or not path.endswith(".py")
        or "\\" in path
        or path.startswith("/")
        or ".." in path.split("/")
        or not parts
        or not all(part.isidentifier() for part in parts)
    ):
        raise _err(
            f"{where}: ",
            f"{nodeid!r} is not a pytest node ID like tests/test_x.py::test_y "
            "(repo-relative path with '/', then ::Class::test or ::test)",
        )
    return TestRef(path=path, qualname="::".join(parts))


def _parse_entry(index: int, raw: Any, default: str) -> CriticalTestEntry:
    where = f"entries[{index}]: "
    if not isinstance(raw, dict):
        raise _err(where, "each entry must be a mapping")
    _check_keys(where, raw, _ENTRY_KEYS)
    entry_id = _non_empty_str(where, "id", raw)
    where = f"entry '{entry_id}': "
    requirement = _non_empty_str(where, "requirement", raw)
    tests = raw.get("tests")
    if not isinstance(tests, list) or not tests:
        raise _err(where, "'tests' must list at least one test")
    refs: List[TestRef] = []
    for position, item in enumerate(tests):
        ref = parse_nodeid(f"entry '{entry_id}' tests[{position}]", item)
        if ref in refs:
            raise _err(where, f"{ref.nodeid!r} is listed more than once")
        refs.append(ref)
    return CriticalTestEntry(
        id=entry_id,
        requirement=requirement,
        tests=tuple(refs),
        enforcement=_enforcement(where, raw.get("enforcement"), default),
    )


def _entry_list(raw_entries: Any) -> List[Any]:
    if raw_entries is None:
        raise _err("", "'entries' is required")
    if not isinstance(raw_entries, list):
        raise _err("", "'entries' must be a list")
    if not raw_entries:
        raise _err("", "'entries' must have at least one entry")
    return raw_entries


def _parse_entries(raw_entries: Any, default: str) -> List[CriticalTestEntry]:
    entries: List[CriticalTestEntry] = []
    seen = set()
    for index, raw in enumerate(_entry_list(raw_entries)):
        entry = _parse_entry(index, raw, default)
        if entry.id in seen:
            raise _err("", f"duplicate id '{entry.id}'")
        seen.add(entry.id)
        entries.append(entry)
    return entries


def parse_critical_tests(data: Any) -> Optional[CriticalTestsPolicy]:
    """Return the validated policy, or None when the section is null."""
    if data is None:
        return None
    if not isinstance(data, dict):
        raise _err("", "must be a mapping with 'entries' (and optional 'enforcement')")
    _check_keys("", data, _SECTION_KEYS)
    default = _enforcement("", data.get("enforcement"), DEFAULT_ENFORCEMENT)
    entries = _parse_entries(data.get("entries"), default)
    return CriticalTestsPolicy(enforcement=default, entries=tuple(entries))


__all__ = [
    "DEFAULT_ENFORCEMENT",
    "ENFORCEMENTS",
    "CriticalTestEntry",
    "CriticalTestsPolicy",
    "TestRef",
    "parse_critical_tests",
    "parse_nodeid",
]
