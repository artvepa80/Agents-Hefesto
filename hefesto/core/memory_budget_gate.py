"""
Memory Budget Gate — Opt-in deterministic RSS gate (EPIC 4)

Measures RSS delta around an analysis run and compares against a
configurable threshold.  Designed for CI pipelines that want to catch
memory-hungry analyzers before they ship.

Key design:
- ``RSSProvider`` protocol for dependency injection (testable).
- ``DefaultRSSProvider`` uses ``resource.getrusage`` with platform
  normalization (macOS reports bytes, Linux reports KB).
- Pure-Python, no new dependencies.
- Deterministic: never flaky — controlled by injectable provider.

Environment:
  HEFESTO_MEMORY_BUDGET_THRESHOLD_KB  (default: 50000 ≈ 50 MB)

Copyright 2025 Narapa LLC, Miami, Florida
"""

import os
import platform
import resource
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional, Protocol, Tuple, TypeVar

T = TypeVar("T")


# ------------------------------------------------------------------
# Provider protocol + default implementation
# ------------------------------------------------------------------


class RSSProvider(Protocol):
    """Abstraction over RSS measurement (injectable for tests)."""

    def get_rss_kb(self) -> int:
        """Return current RSS in kilobytes."""
        ...


class DefaultRSSProvider:
    """Production RSS provider via ``resource.getrusage``."""

    _IS_MACOS = platform.system() == "Darwin"

    def get_rss_kb(self) -> int:
        """Return RSS in KB.  macOS reports bytes; Linux reports KB."""
        ru = resource.getrusage(resource.RUSAGE_SELF)
        rss = ru.ru_maxrss
        if self._IS_MACOS:
            return rss // 1024
        return rss


# ------------------------------------------------------------------
# Result dataclass
# ------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryBudgetResult:
    """Outcome of a memory-budget gate check."""

    rss_before_kb: int
    rss_after_kb: int
    delta_kb: int
    threshold_kb: int
    passed: bool
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------------
# Gate
# ------------------------------------------------------------------


class MemoryBudgetGate:
    """Opt-in deterministic memory gate.

    Usage::

        gate = MemoryBudgetGate(threshold_kb=50000)
        result = gate.measure(lambda: engine.analyze_path("."))
        if not result.passed:
            sys.exit(1)
    """

    def __init__(
        self,
        threshold_kb: Optional[int] = None,
        rss_provider: Optional["RSSProvider"] = None,
    ):
        self.threshold_kb = threshold_kb or int(
            os.environ.get("HEFESTO_MEMORY_BUDGET_THRESHOLD_KB", "50000")
        )
        self._rss: RSSProvider = rss_provider or DefaultRSSProvider()

    def measure(self, fn: Callable[[], T]) -> Tuple[T, MemoryBudgetResult]:
        """Execute *fn* and measure RSS delta.

        Returns ``(fn_result, MemoryBudgetResult)``.
        """
        before = self._rss.get_rss_kb()
        result = fn()
        after = self._rss.get_rss_kb()
        delta = after - before

        passed = delta <= self.threshold_kb
        if passed:
            message = f"Memory budget OK: delta {delta} KB <= threshold {self.threshold_kb} KB"
        else:
            message = (
                f"Memory budget EXCEEDED: delta {delta} KB > threshold {self.threshold_kb} KB"
            )

        budget_result = MemoryBudgetResult(
            rss_before_kb=before,
            rss_after_kb=after,
            delta_kb=delta,
            threshold_kb=self.threshold_kb,
            passed=passed,
            message=message,
        )
        return result, budget_result


__all__ = [
    "RSSProvider",
    "DefaultRSSProvider",
    "MemoryBudgetResult",
    "MemoryBudgetGate",
]
