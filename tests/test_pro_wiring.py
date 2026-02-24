"""
Tests for OSS ↔ PRO wiring (STOP 7).

Validates that:
A) CLI flags don't crash when PRO is not installed.
B) pro_optional fallbacks work correctly.
C) Simulated PRO via monkeypatch exercises the wiring.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import importlib
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
from click.testing import CliRunner

from hefesto.cli.main import cli

# ---------------------------------------------------------------------------
# A) pro_optional fallbacks (no PRO installed)
# ---------------------------------------------------------------------------


class TestProOptionalFallbacks:
    """Verify fallbacks when hefesto_pro is NOT installed."""

    def test_has_flags_are_false(self):
        from hefesto.pro_optional import HAS_ENRICHMENT, HAS_MULTILANG, HAS_SCOPE_GATING

        assert HAS_SCOPE_GATING is False
        assert HAS_MULTILANG is False
        assert HAS_ENRICHMENT is False

    def test_filter_paths_noop(self):
        from hefesto.pro_optional import ScopeGatingConfig, filter_paths

        paths = [Path("a.py"), Path("b.py")]
        config = ScopeGatingConfig()
        included, skipped = filter_paths(paths, config)
        assert included == paths
        assert skipped == []

    def test_build_scope_summary_empty(self):
        from hefesto.pro_optional import build_scope_summary

        assert build_scope_summary([]) == {}

    def test_multilang_sentinels_are_none(self):
        from hefesto.pro_optional import SkipReport, TsJsParser

        assert TsJsParser is None
        assert SkipReport is None

    def test_enrichment_sentinels_are_none(self):
        from hefesto.pro_optional import (
            EnrichmentConfig,
            EnrichmentInput,
            EnrichmentOrchestrator,
        )

        assert EnrichmentConfig is None
        assert EnrichmentInput is None
        assert EnrichmentOrchestrator is None

    def test_api_hardening_flag_false(self):
        from hefesto.pro_optional import HAS_API_HARDENING

        assert HAS_API_HARDENING is False

    def test_apply_hardening_noop(self):
        from hefesto.pro_optional import apply_hardening

        # Should not raise, even with a mock app
        apply_hardening(object())

    def test_hardening_settings_is_none(self):
        from hefesto.pro_optional import HardeningSettings

        assert HardeningSettings is None


# ---------------------------------------------------------------------------
# B) CLI flags don't crash without PRO
# ---------------------------------------------------------------------------


def _has_tree_sitter() -> bool:
    try:
        import tree_sitter  # noqa: F401

        return True
    except ModuleNotFoundError:
        return False


class TestCLIFlagsNoCrash:
    """All new flags must be accepted by Click even without PRO."""

    def test_scope_flags_accepted(self, tmp_path):
        sample = tmp_path / "hello.py"
        sample.write_text("x = 1\n")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                str(sample),
                "--include-third-party",
                "--include-generated",
                "--include-fixtures",
                "--scope-allow",
                "src/",
                "--scope-deny",
                "vendor/",
                "--quiet",
            ],
        )
        # Click should parse all flags (exit 0 or 1, never 2 = Click usage error)
        assert result.exit_code != 2, f"Click usage error: {result.output}"

    def test_enrich_flags_accepted(self, tmp_path):
        sample = tmp_path / "hello.py"
        sample.write_text("x = 1\n")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                str(sample),
                "--enrich",
                "local",
                "--enrich-provider",
                "MyProvider",
                "--enrich-timeout",
                "10",
                "--enrich-cache-ttl",
                "60",
                "--enrich-cache-max",
                "100",
                "--quiet",
            ],
        )
        assert result.exit_code != 2, f"Click usage error: {result.output}"

    @pytest.mark.skipif(not _has_tree_sitter(), reason="tree_sitter not installed")
    def test_json_output_no_meta_without_pro(self, tmp_path):
        # Use YAML file — tree-sitter needed for engine import
        sample = tmp_path / "config.yml"
        sample.write_text("key: value\n")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", str(sample), "--output", "json", "--quiet", "--severity", "LOW"],
        )
        assert result.exit_code in (0, 1), f"Unexpected exit: {result.exit_code}"
        report = json.loads(result.output)
        # Without PRO, meta should be absent (empty dict is omitted)
        assert "meta" not in report


# ---------------------------------------------------------------------------
# C) Simulated PRO via monkeypatch
# ---------------------------------------------------------------------------

# --- Fake PRO modules ---


@dataclass
class _FakeScopeGatingConfig:
    include_third_party: bool = False
    include_generated: bool = False
    include_fixtures: bool = False
    extra_allow: List[str] = field(default_factory=list)
    extra_deny: List[str] = field(default_factory=list)


def _fake_filter_paths(paths: List[Path], config: Any) -> Tuple[List[Path], List[Dict[str, Any]]]:
    """Simulates scope gating: skips any path containing 'vendor'."""
    included = []
    skipped = []
    for p in paths:
        if "vendor" in str(p):
            skipped.append({"path": str(p), "kind": "third_party", "reason": "vendored"})
        else:
            included.append(p)
    return included, skipped


def _fake_build_scope_summary(skipped: List[Any]) -> Dict[str, Any]:
    return {"total_skipped": len(skipped), "entries": skipped}


@dataclass
class _FakeParseResult:
    imports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""


class _FakeTsJsParser:
    def parse_text(self, file_path, code):
        return _FakeParseResult(
            imports=["react"],
            functions=["render"],
            classes=["App"],
            exports=["default"],
        )

    def parse_bytes(self, file_path, data):
        return _FakeParseResult(skipped=True, skip_reason="binary")


class _FakeSkipReport:
    def __init__(self):
        self._entries = []

    def add(self, path, reason, detail=None):
        self._entries.append({"path": str(path), "reason": reason})

    def to_dict(self):
        return {"total_skipped": len(self._entries), "entries": self._entries}

    def to_markdown(self):
        return "\n".join(f"- {e['path']}: {e['reason']}" for e in self._entries)


@dataclass
class _FakeEnrichmentConfig:
    enabled: bool = True
    local_only: bool = False
    timeout_seconds: float = 30.0
    cache_ttl_seconds: int = 300
    cache_max_size: int = 500
    max_prompt_chars: int = 4000
    max_snippet_chars: int = 2000
    providers: List[str] = field(default_factory=list)


@dataclass
class _FakeEnrichmentInput:
    file_path: str = ""
    finding_summary: str = ""
    repo_name: str = ""
    language: str = ""
    snippet: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _FakeEnrichmentResult:
    status: str = "skipped"
    provider: str = ""
    summary: str = ""
    error: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {"status": self.status, "provider": self.provider}


class _FakeEnrichmentOrchestrator:
    def __init__(self, providers=None, **kwargs):
        self.call_count = 0

    def run(self, inp, config=None):
        self.call_count += 1
        return _FakeEnrichmentResult(status="skipped", provider="none")


def _inject_fake_pro(monkeypatch):
    """Register fake hefesto_pro modules in sys.modules."""
    # Create module hierarchy
    pro = types.ModuleType("hefesto_pro")
    sg = types.ModuleType("hefesto_pro.scope_gating")
    sg_cls = types.ModuleType("hefesto_pro.scope_gating.classifier")
    sg_orch = types.ModuleType("hefesto_pro.scope_gating.orchestrator")
    ml = types.ModuleType("hefesto_pro.multilang")
    ml_parser = types.ModuleType("hefesto_pro.multilang.parser")
    ml_skip = types.ModuleType("hefesto_pro.multilang.skip_report")
    enr = types.ModuleType("hefesto_pro.enrichment")

    # Wire scope gating
    sg_cls.ScopeGatingConfig = _FakeScopeGatingConfig
    sg_orch.filter_paths = _fake_filter_paths
    sg_orch.build_scope_summary = _fake_build_scope_summary

    # Wire multilang
    ml_parser.TsJsParser = _FakeTsJsParser
    ml_skip.SkipReport = _FakeSkipReport

    # Wire enrichment
    enr.EnrichmentConfig = _FakeEnrichmentConfig
    enr.EnrichmentInput = _FakeEnrichmentInput
    enr.EnrichmentOrchestrator = _FakeEnrichmentOrchestrator

    # Wire api_hardening (no-op stubs to match pro_optional expectations)
    ah = types.ModuleType("hefesto_pro.api_hardening")
    ah.HardeningSettings = type("HardeningSettings", (), {"__init__": lambda self: None})
    ah.apply_hardening = lambda app, **kw: None

    modules = {
        "hefesto_pro": pro,
        "hefesto_pro.scope_gating": sg,
        "hefesto_pro.scope_gating.classifier": sg_cls,
        "hefesto_pro.scope_gating.orchestrator": sg_orch,
        "hefesto_pro.multilang": ml,
        "hefesto_pro.multilang.parser": ml_parser,
        "hefesto_pro.multilang.skip_report": ml_skip,
        "hefesto_pro.enrichment": enr,
        "hefesto_pro.api_hardening": ah,
    }

    for name, mod in modules.items():
        monkeypatch.setitem(sys.modules, name, mod)

    # Reload pro_optional so it picks up fake modules
    import hefesto.pro_optional

    importlib.reload(hefesto.pro_optional)


def _cleanup_pro_optional(monkeypatch):
    """Reload pro_optional to restore real (no-PRO) state."""
    # Remove fake PRO modules BEFORE reloading; monkeypatch hasn't
    # restored sys.modules yet, so the reload would see fakes and
    # set HAS_*=True, leaking into subsequent tests.
    for key in list(sys.modules):
        if key.startswith("hefesto_pro"):
            monkeypatch.delitem(sys.modules, key, raising=False)

    import hefesto.pro_optional

    importlib.reload(hefesto.pro_optional)


class TestSimulatedProScopeGating:
    """With fake PRO injected, scope gating filters paths and populates meta."""

    def test_scope_gating_filters_and_builds_meta(self, monkeypatch, tmp_path):
        _inject_fake_pro(monkeypatch)
        try:
            from hefesto.pro_optional import HAS_SCOPE_GATING, ScopeGatingConfig, filter_paths

            assert HAS_SCOPE_GATING is True

            paths = [Path("src/app.py"), Path("vendor/x.js")]
            config = ScopeGatingConfig()
            included, skipped = filter_paths(paths, config)

            assert len(included) == 1
            assert included[0] == Path("src/app.py")
            assert len(skipped) == 1
            assert skipped[0]["kind"] == "third_party"
        finally:
            _cleanup_pro_optional(monkeypatch)

    def test_scope_summary_in_report_meta(self, monkeypatch, tmp_path):
        _inject_fake_pro(monkeypatch)
        try:
            from hefesto.pro_optional import build_scope_summary

            skipped = [{"path": "vendor/x.js", "kind": "third_party"}]
            summary = build_scope_summary(skipped)

            assert summary["total_skipped"] == 1
            assert summary["entries"] == skipped
        finally:
            _cleanup_pro_optional(monkeypatch)


class TestSimulatedProMultilang:
    """With fake PRO, multilang parser extracts symbols."""

    def test_tsjs_parser_extracts_symbols(self, monkeypatch):
        _inject_fake_pro(monkeypatch)
        try:
            from hefesto.pro_optional import HAS_MULTILANG, TsJsParser

            assert HAS_MULTILANG is True
            assert TsJsParser is not None

            parser = TsJsParser()
            result = parser.parse_text(Path("app.tsx"), "import React from 'react';")

            assert "react" in result.imports
            assert "render" in result.functions
            assert "App" in result.classes
        finally:
            _cleanup_pro_optional(monkeypatch)


class TestSimulatedProEnrichment:
    """With fake PRO, enrichment orchestrator attaches per-finding metadata."""

    def test_enrichment_orchestrator_returns_skipped(self, monkeypatch):
        _inject_fake_pro(monkeypatch)
        try:
            from hefesto.pro_optional import (
                HAS_ENRICHMENT,
                EnrichmentConfig,
                EnrichmentInput,
                EnrichmentOrchestrator,
            )

            assert HAS_ENRICHMENT is True

            orch = EnrichmentOrchestrator([])
            inp = EnrichmentInput(file_path="a.py", finding_summary="test")
            result = orch.run(inp, EnrichmentConfig())

            assert result.status == "skipped"
            d = result.to_dict()
            assert d["status"] == "skipped"
        finally:
            _cleanup_pro_optional(monkeypatch)

    @pytest.mark.skipif(not _has_tree_sitter(), reason="tree_sitter not installed")
    def test_enrichment_off_by_default(self, tmp_path):
        """Without --enrich flag, no enrichment metadata in findings."""
        # Use YAML with a known issue pattern — tree-sitter needed for engine import
        sample = tmp_path / "ci.yml"
        sample.write_text("password: admin123\n")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", str(sample), "--output", "json", "--quiet", "--severity", "LOW"],
        )
        assert result.exit_code in (0, 1), f"Unexpected: {result.exit_code}"
        assert (
            result.output.strip()
        ), f"CLI produced no JSON (exit={result.exit_code}, exc={result.exception})"
        report = json.loads(result.output)
        for file_entry in report.get("files", []):
            for issue in file_entry.get("issues", []):
                meta = issue.get("metadata", {})
                assert "enrichment" not in meta


class TestEngineMultiPathAccumulation:
    """Scope skipped list accumulates across multiple analyze_path() calls."""

    @pytest.mark.skipif(not _has_tree_sitter(), reason="tree_sitter not installed")
    def test_scope_skipped_extends_not_replaces(self, monkeypatch, tmp_path):
        _inject_fake_pro(monkeypatch)
        try:
            from hefesto.core.analyzer_engine import AnalyzerEngine
            from hefesto.pro_optional import ScopeGatingConfig

            # Create two directories, each with a vendor file
            d1 = tmp_path / "pkg1"
            d1.mkdir()
            (d1 / "app.py").write_text("x = 1\n")
            v1 = d1 / "vendor"
            v1.mkdir()
            (v1 / "dep.js").write_text("var x = 1;\n")

            d2 = tmp_path / "pkg2"
            d2.mkdir()
            (d2 / "lib.py").write_text("y = 2\n")
            v2 = d2 / "vendor"
            v2.mkdir()
            (v2 / "dep2.js").write_text("var y = 2;\n")

            engine = AnalyzerEngine(
                severity_threshold="LOW",
                verbose=False,
                scope_config=ScopeGatingConfig(),
            )

            engine.analyze_path(str(d1))
            engine.analyze_path(str(d2))

            # Should have accumulated skipped from BOTH paths
            assert len(engine._scope_skipped) >= 2
        finally:
            _cleanup_pro_optional(monkeypatch)


# ---------------------------------------------------------------------------
# D) Simulated PRO API Hardening wiring
# ---------------------------------------------------------------------------


class TestApiHardeningWiring:
    """Test api_hardening wiring with simulated PRO modules."""

    def setup_method(self):
        """Reload pro_optional to clear any stale state from simulated PRO tests."""
        import hefesto.pro_optional

        importlib.reload(hefesto.pro_optional)

    def test_serve_without_pro_shows_error(self):
        """hefesto serve should show PRO-required message without PRO installed."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve"])
        assert result.exit_code != 0
        assert "PRO/OMEGA" in result.output or "PRO/OMEGA" in (result.stderr or "")

    def test_apply_hardening_fallback_is_noop(self):
        """apply_hardening fallback should be a no-op that doesn't crash."""
        from hefesto.pro_optional import apply_hardening

        class FakeApp:
            pass

        # Should not raise
        apply_hardening(FakeApp())

    def test_has_api_hardening_false_without_pro(self):
        from hefesto.pro_optional import HAS_API_HARDENING

        assert HAS_API_HARDENING is False

    @pytest.mark.skipif(
        not importlib.util.find_spec("fastapi"),
        reason="fastapi not installed (server extra)",
    )
    def test_server_module_creates_app(self):
        """server.py create_app should return a FastAPI instance."""
        from hefesto.server import create_app

        app = create_app()
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health" in route_paths
        assert "/analyze" in route_paths
