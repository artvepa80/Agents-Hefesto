"""Parse a YAML or JSON document once and reuse it.

``yaml.safe_load`` always uses the pure-Python ``SafeLoader``, even when
libyaml is installed. ``CSafeLoader`` is that library's safe loader: it does
not construct arbitrary objects. ``Loader``, ``FullLoader`` and
``unsafe_load`` are never used here.

A file is parsed once inside :func:`parse_scope`. Format detection and the
analyzer share that result. A parser error from the depth scan is loaded
only with the pure-Python loader. A C loader exception after that scan
accepted the document is parsed again with it. That loader is the source
of the mark and the message, because the two loaders word the same failure
differently and can point at different marks.

libyaml's ``CSafeLoader`` segfaults between 20,000 and 30,000 levels,
including flow documents whose brackets are not consecutive. It also
accepts depths the pure-Python loader rejects. ``SafeLoader`` raises
``RecursionError`` from depth 486-489, because the default recursion limit
is 1000 and each level uses about two frames. Nesting deeper than
:data:`C_LOADER_MAX_DEPTH` is parsed with the pure-Python loader. Depth is
always measured with ``yaml.parse`` (iterative events). A count of ``[``
and ``{`` plus the longest line is not enough: block YAML can nest two
collections in one indent column.

A tab, a line that starts with ``%``, or a block-scalar header glued to
``#`` (``[|>][0-9+-]*#``, yaml-test-suite X4QW ``block: ># comment``) is
also parsed with the pure-Python loader. Those are the markers that
separate the two loaders on the yaml-test-suite, apart from JR7V and
WZ62. Any exception from a loader becomes that pure-Python error, which
is what 4.20.1 reported while still returning the file's other findings.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional, cast

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - PyYAML is a required dependency
    yaml = None  # type: ignore


_CACHE: ContextVar[Optional[dict]] = ContextVar("hefesto_config_parse_cache", default=None)

# Deeper than this uses SafeLoader. SafeLoader rejects from depth 486-489
# (recursion limit 1000, about 2 frames per level) on every supported
# Python. 256 is below that. It is not taken from the C loader's crash
# (20,000 to 30,000).
C_LOADER_MAX_DEPTH = 256

_COLLECTION_START = frozenset({"SequenceStartEvent", "MappingStartEvent"})
_COLLECTION_END = frozenset({"SequenceEndEvent", "MappingEndEvent"})

# ``>#``, ``|+2#``, ``|-#``: a block scalar indicator, optional chomp or
# indent digits, then ``#`` with no space. X4QW is ``block: ># comment``.
_BLOCK_SCALAR_HASH = re.compile(r"[|>][0-9+-]*#")


def yaml_installed() -> bool:
    """True when PyYAML imported."""
    return yaml is not None


def loader_class() -> type:
    """``CSafeLoader`` when libyaml is installed, otherwise ``SafeLoader``.

    ``HEFESTO_YAML_LOADER=safe`` forces ``SafeLoader``. Tests use it so a
    subprocess can compare the default loader with the pure-Python one
    from the same call stack.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is not installed")
    if os.environ.get("HEFESTO_YAML_LOADER") == "safe":
        return yaml.SafeLoader
    c_loader = getattr(yaml, "CSafeLoader", None)
    if c_loader is not None:
        return cast(type, c_loader)
    return yaml.SafeLoader


def yaml_nesting_exceeds(content: str, limit: int = C_LOADER_MAX_DEPTH) -> bool:
    """True when collection nesting is deeper than ``limit``.

    Every document is measured with :func:`yaml.parse`. The events are
    iterative and do not build the objects that crash libyaml. A count of
    brackets plus the longest line is not used: ``a:`` and ``-`` can share
    one indent column, so that sum understates the depth by about half.
    """
    if yaml is None:
        return False
    return _event_depth_exceeds(content, limit)


def _event_loader() -> type:
    """``CSafeLoader`` for the event scan. Its parser does not recurse in Python."""
    c_loader = getattr(yaml, "CSafeLoader", None)
    if c_loader is not None:
        return cast(type, c_loader)
    return yaml.SafeLoader


def _event_depth_exceeds(content: str, limit: int) -> bool:
    """True when ``yaml.parse`` sees more than ``limit`` open collections.

    A parser error, or ``RecursionError`` from the pure-Python parser, is
    treated as too deep: the C loader is not given a document this bound
    could not clear.
    """
    try:
        events = yaml.parse(content, Loader=_event_loader())
    except RecursionError:
        return True
    except yaml.YAMLError:
        return True
    depth = 0
    try:
        for event in events:
            kind = type(event).__name__
            if kind in _COLLECTION_START:
                depth += 1
                if depth > limit:
                    return True
            elif kind in _COLLECTION_END and depth:
                depth -= 1
    except RecursionError:
        return True
    except yaml.YAMLError:
        return True
    finally:
        close = getattr(events, "close", None)
        if close is not None:
            close()
    return False


def _libyaml_markers(content: str) -> bool:
    """True when this text carries a known libyaml / SafeLoader split.

    A tab anywhere, a line starting with ``%``, or :data:`_BLOCK_SCALAR_HASH`.
    JR7V and WZ62 disagree too and match none of these; they stay on
    ``CSafeLoader``, which accepts both.
    """
    if "\t" in content:
        return True
    for line in content.splitlines():
        if line.startswith("%"):
            return True
    return _BLOCK_SCALAR_HASH.search(content) is not None


def _loader_for(content: str) -> type:
    loader = loader_class()
    if yaml is None or loader is yaml.SafeLoader:
        return loader
    if _libyaml_markers(content) or yaml_nesting_exceeds(content):
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
