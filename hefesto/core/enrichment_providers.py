"""Load enrichment providers from installed packages (``--enrich-provider``).

A package registers a provider under the ``hefesto.enrichment_providers``
entry-point group. Only the names passed with ``--enrich-provider`` are loaded;
nothing else in the group is imported. The entry point may name a provider
class (instantiated with no arguments) or a ready provider instance.

A provider is used only if it satisfies the PRO ``EnrichmentProvider`` protocol
and its ``name`` equals the entry-point name (the PRO allow-list compares
``provider.name``). Anything missing, failing to load, or failing these checks
is reported on stderr and skipped; analysis always continues.
"""

from __future__ import annotations

import inspect
import sys
from importlib.metadata import EntryPoint, entry_points
from typing import Any, Callable, List, Optional, Sequence

ENTRY_POINT_GROUP = "hefesto.enrichment_providers"


def _warn(message: str) -> None:
    print(f"Warning: enrichment provider {message}; skipped.", file=sys.stderr)


def _entry_points() -> Sequence[EntryPoint]:
    return list(entry_points(group=ENTRY_POINT_GROUP))


def load_enrichment_providers(
    names: Sequence[str],
    protocol: Any,
    *,
    discover: Optional[Callable[[], Sequence[EntryPoint]]] = None,
) -> List[Any]:
    """Return provider objects for *names*, in the given order, skipping bad ones."""
    wanted = list(dict.fromkeys(n for n in names if n))
    if not wanted:
        return []
    try:
        available = list((discover or _entry_points)())
    except Exception as exc:  # noqa: BLE001 - metadata errors must not stop analysis
        _warn(f"discovery failed ({type(exc).__name__}: {exc})")
        return []

    providers: List[Any] = []
    for name in wanted:
        matches = [ep for ep in available if ep.name == name]
        if not matches:
            _warn(f"'{name}' is not installed (no '{ENTRY_POINT_GROUP}' entry point)")
            continue
        try:
            obj = matches[0].load()
            provider = obj() if inspect.isclass(obj) else obj
        except Exception as exc:  # noqa: BLE001 - third-party code
            _warn(f"'{name}' failed to load ({type(exc).__name__}: {exc})")
            continue
        if protocol is None or not isinstance(provider, protocol):
            _warn(f"'{name}' does not implement EnrichmentProvider (name, enrich)")
            continue
        provider_name = getattr(provider, "name", None)
        if provider_name != name:
            _warn(f"'{name}' reports name {provider_name!r}, which must match the entry point")
            continue
        providers.append(provider)
    return providers
