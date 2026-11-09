"""Enrichment providers loaded from ``hefesto.enrichment_providers`` entry points."""

from __future__ import annotations

import importlib
import json
import sys
import types
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
from typing import Any, Dict, List, Protocol, runtime_checkable

import pytest
from click.testing import CliRunner

from hefesto.core import enrichment_providers as ep_mod
from hefesto.core.enrichment_providers import ENTRY_POINT_GROUP, load_enrichment_providers

# ---------------------------------------------------------------------------
# Fake PRO enrichment API (the real one ships in the PRO package)
# ---------------------------------------------------------------------------


@runtime_checkable
class FakeProviderProtocol(Protocol):
    @property
    def name(self) -> str: ...

    def enrich(self, inp: Any, config: Any) -> Any: ...


@dataclass
class FakeConfig:
    enabled: bool = True
    local_only: bool = False
    timeout_seconds: float = 30.0
    cache_ttl_seconds: int = 300
    cache_max_size: int = 500
    providers: List[str] = field(default_factory=list)


@dataclass
class FakeInput:
    file_path: str = ""
    finding_summary: str = ""
    repo_name: str = ""
    language: Any = None
    snippet: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeResult:
    status: str = "skipped"
    provider: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "provider": self.provider, "summary": self.summary}


class FakeCache:
    def __init__(self, *, ttl: int = 300, max_size: int = 500) -> None:
        self.ttl = ttl
        self.max_size = max_size


class FakeOrchestrator:
    instances: List["FakeOrchestrator"] = []

    def __init__(self, providers=(), *, masker=None, cache=None) -> None:
        self.providers = list(providers)
        self.cache = cache
        self.calls = 0
        FakeOrchestrator.instances.append(self)

    def run(self, inp, config=None):
        self.calls += 1
        for p in self.providers:
            if config and config.providers and p.name not in config.providers:
                continue
            res = p.enrich(inp, config)
            res.provider = p.name
            if res.status == "ok":
                return res
        return FakeResult(status="skipped", provider="none")


# ---------------------------------------------------------------------------
# Fake third-party provider package
# ---------------------------------------------------------------------------


class GoodProvider:
    name = "good"

    def enrich(self, inp, config):
        return FakeResult(status="ok", summary="insight")


class WrongName:
    name = "something-else"

    def enrich(self, inp, config):
        return FakeResult(status="ok")


class NotAProvider:
    name = "noenrich"


class Boom:
    name = "boom"

    def __init__(self) -> None:
        raise RuntimeError("cannot start")


GOOD_INSTANCE = GoodProvider()


@pytest.fixture
def fake_pkg(monkeypatch):
    mod = types.ModuleType("fake_enrich_pkg")
    mod.GoodProvider = GoodProvider
    mod.WrongName = WrongName
    mod.NotAProvider = NotAProvider
    mod.Boom = Boom
    mod.GOOD_INSTANCE = GOOD_INSTANCE
    monkeypatch.setitem(sys.modules, "fake_enrich_pkg", mod)
    eps = [
        EntryPoint("good", "fake_enrich_pkg:GoodProvider", ENTRY_POINT_GROUP),
        EntryPoint("good_instance", "fake_enrich_pkg:GOOD_INSTANCE", ENTRY_POINT_GROUP),
        EntryPoint("mismatch", "fake_enrich_pkg:WrongName", ENTRY_POINT_GROUP),
        EntryPoint("noenrich", "fake_enrich_pkg:NotAProvider", ENTRY_POINT_GROUP),
        EntryPoint("boom", "fake_enrich_pkg:Boom", ENTRY_POINT_GROUP),
        EntryPoint("badimport", "no_such_module_xyz:Thing", ENTRY_POINT_GROUP),
    ]
    monkeypatch.setattr(ep_mod, "_entry_points", lambda: eps)
    return eps


def _load(names):
    return load_enrichment_providers(names, FakeProviderProtocol)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_valid_provider_class_is_instantiated(fake_pkg, capsys):
    providers = _load(["good"])
    assert [p.name for p in providers] == ["good"]
    assert isinstance(providers[0], GoodProvider)
    assert capsys.readouterr().err == ""


def test_instance_entry_point_is_used_as_is(fake_pkg):
    class Named(GoodProvider):
        name = "good_instance"

    sys.modules["fake_enrich_pkg"].GOOD_INSTANCE = Named()
    providers = _load(["good_instance"])
    assert providers[0] is sys.modules["fake_enrich_pkg"].GOOD_INSTANCE


def test_only_requested_names_are_loaded(fake_pkg, monkeypatch):
    loaded = []
    real_load = EntryPoint.load

    def spy(self):
        loaded.append(self.name)
        return real_load(self)

    monkeypatch.setattr(EntryPoint, "load", spy)
    _load(["good"])
    assert loaded == ["good"]


def test_no_names_does_not_discover(monkeypatch):
    def fail():
        raise AssertionError("discovery must not run")

    monkeypatch.setattr(ep_mod, "_entry_points", fail)
    assert _load([]) == []


def test_missing_provider_warns_and_continues(fake_pkg, capsys):
    providers = _load(["absent", "good"])
    assert [p.name for p in providers] == ["good"]
    err = capsys.readouterr().err
    assert "'absent' is not installed" in err and "skipped" in err


@pytest.mark.parametrize("name", ["boom", "badimport"])
def test_load_failure_warns_and_continues(fake_pkg, capsys, name):
    providers = _load([name, "good"])
    assert [p.name for p in providers] == ["good"]
    assert f"'{name}' failed to load" in capsys.readouterr().err


def test_name_mismatch_is_rejected(fake_pkg, capsys):
    assert _load(["mismatch"]) == []
    err = capsys.readouterr().err
    assert "must match the entry point" in err and "'something-else'" in err


def test_non_provider_is_rejected(fake_pkg, capsys):
    assert _load(["noenrich"]) == []
    assert "does not implement EnrichmentProvider" in capsys.readouterr().err


def test_missing_protocol_rejects_everything(fake_pkg, capsys):
    assert load_enrichment_providers(["good"], None) == []
    assert "does not implement" in capsys.readouterr().err


def test_discovery_error_is_a_warning(monkeypatch, capsys):
    def broken():
        raise OSError("bad metadata")

    monkeypatch.setattr(ep_mod, "_entry_points", broken)
    assert _load(["good"]) == []
    assert "discovery failed" in capsys.readouterr().err


def test_duplicate_names_load_once(fake_pkg):
    assert len(_load(["good", "good"])) == 1


# ---------------------------------------------------------------------------
# Engine + CLI wiring with a fake PRO package
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_pro(monkeypatch, fake_pkg):
    pro = types.ModuleType("hefesto_pro")
    enr = types.ModuleType("hefesto_pro.enrichment")
    enr.EnrichmentConfig = FakeConfig
    enr.EnrichmentInput = FakeInput
    enr.EnrichmentOrchestrator = FakeOrchestrator
    enr.EnrichmentCache = FakeCache
    enr.EnrichmentProvider = FakeProviderProtocol
    monkeypatch.setitem(sys.modules, "hefesto_pro", pro)
    monkeypatch.setitem(sys.modules, "hefesto_pro.enrichment", enr)
    import hefesto.pro_optional

    importlib.reload(hefesto.pro_optional)
    FakeOrchestrator.instances.clear()
    yield
    for key in list(sys.modules):
        if key.startswith("hefesto_pro"):
            monkeypatch.delitem(sys.modules, key, raising=False)
    importlib.reload(hefesto.pro_optional)


def test_engine_passes_providers_and_cache(fake_pro):
    from hefesto.core.analyzer_engine import AnalyzerEngine

    AnalyzerEngine(
        enrich_config=FakeConfig(providers=["good"], cache_ttl_seconds=7, cache_max_size=9)
    )
    orch = FakeOrchestrator.instances[-1]
    assert [p.name for p in orch.providers] == ["good"]
    assert isinstance(orch.cache, FakeCache)
    assert (orch.cache.ttl, orch.cache.max_size) == (7, 9)


def _sample(tmp_path):
    src = tmp_path / "app.py"
    src.write_text(
        "import os\n"
        "import pickle\n"
        "password = 'hunter2hunter2'\n"
        "def f(x):\n"
        "    eval(x)\n"
        "    os.system(x)\n"
        "    return pickle.loads(x)\n"
    )
    return src


def _run(args):
    from hefesto.cli.main import cli

    res = CliRunner().invoke(cli, args)
    out = res.stdout if hasattr(res, "stdout") else res.output
    report = json.loads(out[out.index("{") :])
    issues = [i for f in report.get("files", []) for i in f.get("issues", [])]
    return res.exit_code, issues


def _base_args(path):
    return ["analyze", str(path), "--output", "json", "--quiet", "--severity", "LOW"]


def test_enrichment_does_not_change_exit_code_or_severities(fake_pro, tmp_path):
    src = _sample(tmp_path)
    code_off, issues_off = _run(_base_args(src))
    code_on, issues_on = _run(_base_args(src) + ["--enrich", "remote", "--enrich-provider", "good"])
    assert issues_off, "sample must produce findings"
    assert code_on == code_off
    key = lambda i: (i.get("line"), i.get("type"), i.get("severity"))  # noqa: E731
    assert sorted(map(key, issues_on)) == sorted(map(key, issues_off))
    enriched = [i for i in issues_on if "enrichment" in i.get("metadata", {})]
    assert enriched and all(i["metadata"]["enrichment"]["status"] == "ok" for i in enriched)


def test_cap_limits_enrichment_calls(fake_pro, tmp_path):
    src = _sample(tmp_path)
    args = _base_args(src) + ["--enrich", "remote", "--enrich-provider", "good"]
    _, issues = _run(args + ["--enrich-max-findings", "1", "--enrich-min-severity", "LOW"])
    assert FakeOrchestrator.instances[-1].calls == 1
    enriched = [i for i in issues if "enrichment" in i.get("metadata", {})]
    assert len(enriched) == 1
    rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    assert rank[enriched[0]["severity"]] == max(rank[i["severity"]] for i in issues)


def test_severity_floor_skips_lower_findings(fake_pro, tmp_path):
    src = _sample(tmp_path)
    args = _base_args(src) + ["--enrich", "remote", "--enrich-provider", "good"]
    _, issues = _run(args + ["--enrich-min-severity", "CRITICAL", "--enrich-max-findings", "500"])
    for i in issues:
        has = "enrichment" in i.get("metadata", {})
        assert has == (i["severity"] == "CRITICAL")


def test_zero_cap_means_no_calls(fake_pro, tmp_path):
    src = _sample(tmp_path)
    _run(
        _base_args(src)
        + ["--enrich", "remote", "--enrich-provider", "good", "--enrich-max-findings", "0"]
    )
    assert FakeOrchestrator.instances[-1].calls == 0


def test_missing_provider_cli_warns_and_exit_code_unchanged(fake_pro, tmp_path):
    src = _sample(tmp_path)
    code_off, _ = _run(_base_args(src))
    from hefesto.cli.main import cli

    res = CliRunner().invoke(
        cli, _base_args(src) + ["--enrich", "remote", "--enrich-provider", "absent"]
    )
    assert res.exit_code == code_off
    assert "'absent' is not installed" in res.stderr


def _ep_from(dist_name: str, value: str) -> EntryPoint:
    ep = EntryPoint("good", value, ENTRY_POINT_GROUP)
    return ep._for(types.SimpleNamespace(name=dist_name))  # type: ignore[arg-type]


class OtherGood(GoodProvider):
    pass


@pytest.mark.parametrize("order", [("zeta-pkg", "alpha-pkg"), ("alpha-pkg", "zeta-pkg")])
def test_duplicate_name_warns_and_uses_first_deterministically(
    fake_pkg, monkeypatch, capsys, order
):
    sys.modules["fake_enrich_pkg"].OtherGood = OtherGood
    value = {"alpha-pkg": "fake_enrich_pkg:GoodProvider", "zeta-pkg": "fake_enrich_pkg:OtherGood"}
    eps = [_ep_from(d, value[d]) for d in order]
    monkeypatch.setattr(ep_mod, "_entry_points", lambda: eps)
    providers = _load(["good"])
    assert len(providers) == 1
    assert type(providers[0]) is GoodProvider  # alpha-pkg wins regardless of discovery order
    err = capsys.readouterr().err
    assert "'good' is registered by more than one package (alpha-pkg, zeta-pkg)" in err
    assert "using alpha-pkg" in err
