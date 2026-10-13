"""
Project config file (``.hefesto.yaml`` / ``.hefesto.yml``) for ``hefesto analyze``.

Discovery: starting at the analyzed path (its directory when it is a file),
walk up the directory tree and use the first ``.hefesto.yaml`` or
``.hefesto.yml`` found. The walk stops after the repository root (the first
directory containing ``.git``) or at the filesystem root.

Every supported key maps 1:1 to an existing ``hefesto analyze`` option.
Precedence is: explicit CLI flag > config file > built-in default. The CLI
decides what was explicit (click's parameter source); this module only finds,
parses and validates the file.

The CLI passes the names of the options ``hefesto analyze`` really has as
``allowed_keys``, so a key whose option does not exist in this build (e.g.
``format_check`` before ``--format-check`` ships) is rejected as unknown
instead of being silently ignored.

Copyright 2026 Narapa LLC, Miami, Florida
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

CONFIG_FILENAMES = (".hefesto.yaml", ".hefesto.yml")

_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
_OUTPUTS = ("text", "json", "html", "sarif")


class ConfigError(ValueError):
    """Raised for a config file that cannot be found, parsed or validated."""


@dataclass
class ProjectConfig:
    """A loaded, validated config file (``path`` is None when no file applies).

    ``values`` uses the ``hefesto analyze`` parameter names and the value
    shapes those parameters expect (e.g. ``exclude`` is a comma-separated
    string, like ``--exclude``). Keys set to ``null`` in the file are omitted.
    """

    path: Optional[Path] = None
    values: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _config_in(directory: Path) -> Optional[Path]:
    found = [directory / name for name in CONFIG_FILENAMES if (directory / name).is_file()]
    if len(found) > 1:
        raise ConfigError(
            f"both {found[0].name} and {found[1].name} exist in {directory}; keep only one"
        )
    return found[0] if found else None


def find_config(start: Path) -> Optional[Path]:
    """Return the nearest config file at or above ``start``, or None."""
    current = Path(start).resolve()
    if not current.is_dir():
        current = current.parent
    for directory in (current, *current.parents):
        found = _config_in(directory)
        if found is not None:
            return found
        if (directory / ".git").exists():
            return None
    return None


def discover_config(paths: Iterable[str]) -> Tuple[Optional[Path], List[str]]:
    """Find the config for a set of analyzed paths.

    The first path decides. If other paths would pick a different config
    file, a warning is returned (one config applies to the whole run).
    """
    path_list = list(paths)
    if not path_list:
        return None, []
    chosen = find_config(Path(path_list[0]))
    warnings: List[str] = []
    for other in path_list[1:]:
        candidate = find_config(Path(other))
        if candidate != chosen:
            warnings.append(
                f"{other} would use config {candidate or '(none)'}, but only one config "
                f"applies per run; using {chosen or '(none)'} (from {path_list[0]})"
            )
    return chosen, warnings


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _choice(choices: Tuple[str, ...], upper: bool) -> Callable[[str, Any], Any]:
    def validate(key: str, value: Any) -> Any:
        if not isinstance(value, str):
            raise ConfigError(f"'{key}' must be one of {', '.join(choices)} (got {value!r})")
        normalized = value.upper() if upper else value.lower()
        if normalized not in choices:
            raise ConfigError(f"'{key}' must be one of {', '.join(choices)} (got {value!r})")
        return normalized

    return validate


def _bool(key: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"'{key}' must be true or false (got {value!r})")
    return value


def _positive_int(key: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"'{key}' must be a positive integer (got {value!r})")
    return value


def _string_list(key: str, value: Any) -> List[str]:
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
        items = value
    else:
        raise ConfigError(f"'{key}' must be a list of strings or a comma-separated string")
    return [item.strip() for item in items if item.strip()]


def _pattern_list(key: str, value: Any) -> str:
    return ",".join(_string_list(key, value))


def _issue_type_list(key: str, value: Any) -> str:
    from hefesto.core.analysis_models import AnalysisIssueType

    known = {t.value for t in AnalysisIssueType}
    items = [item.upper() for item in _string_list(key, value)]
    unknown = [item for item in items if item not in known]
    if unknown:
        raise ConfigError(
            f"'{key}' has unknown issue type(s): {', '.join(unknown)} "
            "(see the 'type' field in --output json)"
        )
    return ",".join(items)


# config key -> validator returning the value in the shape the CLI option uses
_VALIDATORS: Dict[str, Callable[[str, Any], Any]] = {
    "severity": _choice(_SEVERITIES, upper=True),
    "output": _choice(_OUTPUTS, upper=False),
    "exclude": _pattern_list,
    "exclude_types": _issue_type_list,
    "fail_on": _choice(_SEVERITIES, upper=True),
    "quiet": _bool,
    "max_issues": _positive_int,
    "format_check": _bool,
    "enable_memory_budget_gate": _bool,
    "copybook_paths": _string_list,
}

SUPPORTED_KEYS = tuple(_VALIDATORS)

_UNSUPPORTED_HINTS = {
    "rules": "rule thresholds are not configurable yet",
    "format_check": "this hefesto version has no --format-check option",
}


def _unknown_key(raw_key: Any, supported: Tuple[str, ...]) -> ConfigError:
    key = str(raw_key).strip().replace("-", "_")
    hint = _UNSUPPORTED_HINTS.get(key, "")
    detail = f"; {hint}" if hint else ""
    return ConfigError(f"unknown key '{raw_key}'{detail} (supported: {', '.join(supported)})")


def _supported(allowed_keys: Optional[Iterable[str]]) -> Tuple[str, ...]:
    if allowed_keys is None:
        return SUPPORTED_KEYS
    allowed = set(allowed_keys)
    return tuple(key for key in SUPPORTED_KEYS if key in allowed)


def _validate_entry(
    raw_key: Any, raw_value: Any, seen: set, supported: Tuple[str, ...]
) -> Optional[Tuple[str, Any]]:
    key = str(raw_key).strip().replace("-", "_")
    validator = _VALIDATORS.get(key)
    if validator is None or key not in supported:
        raise _unknown_key(raw_key, supported)
    if key in seen:
        raise ConfigError(f"key '{raw_key}' is set more than once")
    seen.add(key)
    if raw_value is None:
        return None
    return key, validator(str(raw_key), raw_value)


def validate_config(data: Any, allowed_keys: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Validate parsed YAML and return CLI-shaped values (nulls dropped).

    ``allowed_keys`` limits the accepted keys (the CLI passes its option
    names); None accepts every key in ``SUPPORTED_KEYS``.
    """
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError("top level must be a mapping of key: value pairs")

    supported = _supported(allowed_keys)
    values: Dict[str, Any] = {}
    seen: set = set()
    for raw_key, raw_value in data.items():
        entry = _validate_entry(raw_key, raw_value, seen, supported)
        if entry is not None:
            values[entry[0]] = entry[1]
    return values


def load_config(path: Path, allowed_keys: Optional[Iterable[str]] = None) -> ProjectConfig:
    """Parse and validate one config file (see ``validate_config``)."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - PyYAML is a core dependency
        raise ConfigError("reading .hefesto.yaml needs PyYAML: pip install pyyaml") from exc

    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML: {exc}") from exc
    values = validate_config(data, allowed_keys)
    if "copybook_paths" in values:
        values["copybook_paths"] = _resolve_dirs(values["copybook_paths"], path.parent)
    return ProjectConfig(path=path, values=values)


def _resolve_dirs(entries: List[str], base: Path) -> Tuple[str, ...]:
    """``copybook_paths`` entries resolved against the config file's directory."""
    resolved = []
    for entry in entries:
        directory = Path(entry).expanduser()
        if not directory.is_absolute():
            directory = base / directory
        if not directory.is_dir():
            raise ConfigError(f"'copybook_paths' entry {entry!r} is not a directory")
        resolved.append(str(directory.resolve()))
    return tuple(resolved)


__all__ = [
    "CONFIG_FILENAMES",
    "SUPPORTED_KEYS",
    "ConfigError",
    "ProjectConfig",
    "discover_config",
    "find_config",
    "load_config",
    "validate_config",
]
