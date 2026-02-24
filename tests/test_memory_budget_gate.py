"""Tests for Memory Budget Gate (EPIC 4)."""

from hefesto.core.memory_budget_gate import (
    DefaultRSSProvider,
    MemoryBudgetGate,
    MemoryBudgetResult,
)


class FakeRSSProvider:
    """Injectable fake that returns pre-set RSS values."""

    def __init__(self, before_kb: int, after_kb: int):
        self._values = iter([before_kb, after_kb])

    def get_rss_kb(self) -> int:
        return next(self._values)


# ── Pass scenario ─────────────────────────────────────────────────────


def test_budget_gate_pass():
    provider = FakeRSSProvider(before_kb=100_000, after_kb=120_000)
    gate = MemoryBudgetGate(threshold_kb=50_000, rss_provider=provider)

    result, budget = gate.measure(lambda: "ok")

    assert result == "ok"
    assert budget.passed is True
    assert budget.delta_kb == 20_000
    assert budget.rss_before_kb == 100_000
    assert budget.rss_after_kb == 120_000
    assert budget.threshold_kb == 50_000
    assert "OK" in budget.message


# ── Fail scenario ─────────────────────────────────────────────────────


def test_budget_gate_fail():
    provider = FakeRSSProvider(before_kb=100_000, after_kb=200_000)
    gate = MemoryBudgetGate(threshold_kb=50_000, rss_provider=provider)

    result, budget = gate.measure(lambda: 42)

    assert result == 42
    assert budget.passed is False
    assert budget.delta_kb == 100_000
    assert "EXCEEDED" in budget.message


# ── Exact threshold boundary (passes) ─────────────────────────────────


def test_budget_gate_exact_boundary():
    provider = FakeRSSProvider(before_kb=100_000, after_kb=150_000)
    gate = MemoryBudgetGate(threshold_kb=50_000, rss_provider=provider)

    _, budget = gate.measure(lambda: None)

    assert budget.passed is True
    assert budget.delta_kb == 50_000


# ── Serialization ─────────────────────────────────────────────────────


def test_result_to_dict():
    r = MemoryBudgetResult(
        rss_before_kb=100,
        rss_after_kb=200,
        delta_kb=100,
        threshold_kb=50,
        passed=False,
        message="EXCEEDED",
    )
    d = r.to_dict()
    assert d["rss_before_kb"] == 100
    assert d["rss_after_kb"] == 200
    assert d["delta_kb"] == 100
    assert d["threshold_kb"] == 50
    assert d["passed"] is False
    assert d["message"] == "EXCEEDED"


# ── Default provider instantiates without error ───────────────────────


def test_default_provider_returns_int():
    provider = DefaultRSSProvider()
    rss = provider.get_rss_kb()
    assert isinstance(rss, int)
    assert rss > 0


# ── Environment variable threshold ────────────────────────────────────


def test_env_threshold(monkeypatch):
    monkeypatch.setenv("HEFESTO_MEMORY_BUDGET_THRESHOLD_KB", "12345")
    gate = MemoryBudgetGate()
    assert gate.threshold_kb == 12345
