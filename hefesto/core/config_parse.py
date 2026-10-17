"""Parse a YAML or JSON document once and reuse it.

``yaml.safe_load`` always uses the pure-Python ``SafeLoader``, even when
libyaml is installed. ``CSafeLoader`` is that library's safe loader: it does
not construct arbitrary objects. ``Loader``, ``FullLoader`` and
``unsafe_load`` are never used here.

A file is parsed once inside :func:`parse_scope`. Format detection and the
analyzer share that result. On a syntax error the pure-Python loader is the
source of the mark and the message, because the two loaders word the same
failure differently and can point at different marks.

libyaml's ``CSafeLoader`` segfaults on CPython 3.10-3.13 when a document is
nested about 50,000 levels, and it accepts depths the pure-Python loader
rejects. Above :data:`C_LOADER_MAX_DEPTH` the pure-Python loader is used.
Any exception from a loader becomes that pure-Python error, which is what
4.20.1 reported while still returning the file's other findings.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional, cast

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - PyYAML is a required dependency
    yaml = None  # type: ignore


_CACHE: ContextVar[Optional[dict]] = ContextVar("hefesto_config_parse_cache", default=None)

# SafeLoader raises RecursionError near 800 nested ``- `` sequences (a HIGH
# YAML_SYNTAX_ERROR on 4.20.1) while CSafeLoader still accepts them. CSafeLoader
# segfaults near 50,000 levels on CPython 3.10-3.13. Documents deeper than this
# are parsed with SafeLoader. Normal manifests are far shallower.
C_LOADER_MAX_DEPTH = 256


def yaml_installed() -> bool:
    """True when PyYAML imported."""
    return yaml is not None


def loader_class() -> type:
    """``CSafeLoader`` when libyaml is installed, otherwise ``SafeLoader``."""
    if yaml is None:
        raise RuntimeError("PyYAML is not installed")
    c_loader = getattr(yaml, "CSafeLoader", None)
    if c_loader is not None:
        return cast(type, c_loader)
    return yaml.SafeLoader


def yaml_nesting_exceeds(content: str, limit: int = C_LOADER_MAX_DEPTH) -> bool:
    """True when a cheap scan sees nesting deeper than ``limit``.

    The scan is a run of ``- ``, ``[``, ``{`` or leading spaces. A real
    bracket depth is counted only when the file has more brackets than
    ``limit``. Over-counting selects SafeLoader, which is how 4.20.1 parsed
    the file.
    """
    if ("- " * (limit + 1)) in content:
        return True
    if ("[" * (limit + 1)) in content or ("{" * (limit + 1)) in content:
        return True
    spaces = " " * (limit + 1)
    if content.startswith(spaces) or ("\n" + spaces) in content:
        return True
    if content.count("[") + content.count("{") <= limit:
        return False
    return _flow_depth_exceeds(content, limit)


def _flow_depth_exceeds(content: str, limit: int) -> bool:
    depth = 0
    for char in content:
        if char == "[" or char == "{":
            depth += 1
            if depth > limit:
                return True
        elif (char == "]" or char == "}") and depth:
            depth -= 1
    return False


def _loader_for(content: str) -> type:
    loader = loader_class()
    if yaml is not None and loader is not yaml.SafeLoader and yaml_nesting_exceeds(content):
        return yaml.SafeLoader
    return loader


@contextmanager
def parse_scope() -> Iterator[None]:
    """Reuse a parse of the same string object for the rest of this block.

    An outer scope is left in place, so a nested call does not drop results
    the caller still needs.
    """
    if _CACHE.get() is not None:
        yield
        return
    token = _CACHE.set({})
    try:
        yield
    finally:
        _CACHE.reset(token)


def _cached(kind: str, content: str) -> Any:
    cache = _CACHE.get()
    if not cache:
        return None
    hit = cache.get((kind, id(content)))
    if hit is None or hit[0] is not content:
        return None
    return hit[1]


def _store(kind: str, content: str, value: Any) -> None:
    cache = _CACHE.get()
    if cache is not None:
        cache[(kind, id(content))] = (content, value)


@dataclass
class YamlStream:
    """Documents from one YAML stream.

    ``raw`` is every document, including ``None`` for an empty document.
    ``raw is None`` means the stream did not parse. ``error`` is that failure.
    """

    raw: Optional[List[Any]]
    error: Optional[BaseException]

    @property
    def documents(self) -> Optional[List[Any]]:
        """Non-empty documents, or ``None`` when the stream did not parse."""
        if self.raw is None:
            return None
        return [doc for doc in self.raw if doc is not None]

    @property
    def is_single(self) -> bool:
        """True when ``yaml.safe_load`` would return instead of raising."""
        return self.error is None and self.raw is not None and len(self.raw) <= 1

    @property
    def single_document(self) -> Any:
        """The value ``yaml.safe_load`` would return for a single document."""
        if not self.is_single or not self.raw:
            return None
        return self.raw[0]


def yaml_error_line(exc: BaseException) -> int:
    """1-based line from a loader mark, or 1 when the error has no mark."""
    mark = getattr(exc, "problem_mark", None)
    line = getattr(mark, "line", None) if mark is not None else None
    if isinstance(line, int) and line >= 0:
        return line + 1
    return 1


def load_yaml(content: str) -> YamlStream:
    """Parse every document in ``content`` with the safe loader.

    The same string object is parsed once inside :func:`parse_scope`.
    """
    if yaml is None:
        return YamlStream(raw=None, error=None)
    cached = _cached("yaml", content)
    if isinstance(cached, YamlStream):
        return cached
    loaded = _load_yaml(content)
    _store("yaml", content, loaded)
    return loaded


def _load_yaml(content: str) -> YamlStream:
    loader = _loader_for(content)
    try:
        raw = list(yaml.load_all(content, Loader=loader))
    except Exception as exc:
        # 4.20.1 caught every loader exception, recorded a syntax finding,
        # and still ran the other checks. ValueError from a timestamp is
        # one of those: it is not a yaml.YAMLError.
        return _yaml_failure(content, loader, exc)
    return YamlStream(raw=raw, error=None)


def _yaml_failure(content: str, loader: type, exc: BaseException) -> YamlStream:
    """Keep the pure-Python loader's mark and message when the C loader failed.

    A successful pure-Python parse wins, so a document only the C loader
    rejects is still analyzed the way ``SafeLoader`` analyzes it.
    """
    if yaml is None or loader is yaml.SafeLoader:
        return YamlStream(raw=None, error=exc)
    try:
        raw = list(yaml.load_all(content, Loader=yaml.SafeLoader))
    except Exception as pure:
        return YamlStream(raw=None, error=pure)
    return YamlStream(raw=raw, error=None)


@dataclass
class JsonDocument:
    """A JSON value, or the error ``json.loads`` raised."""

    value: Any = None
    error: Optional[BaseException] = None


def load_json(content: str) -> JsonDocument:
    """Parse ``content`` once inside :func:`parse_scope`."""
    cached = _cached("json", content)
    if isinstance(cached, JsonDocument):
        return cached
    try:
        value = json.loads(content)
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        document = JsonDocument(error=exc)
    else:
        document = JsonDocument(value=value)
    _store("json", content, document)
    return document
