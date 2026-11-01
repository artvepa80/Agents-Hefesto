"""A supported file whose tree-sitter grammar cannot be loaded is not analyzed.

With an empty grammar cache and no network, ``tree_sitter_language_pack``
cannot download the Java/Go/Rust grammars. Those files used to be counted as
plain parse errors: a repo with one Python file next to them printed
"Gate passed" under ``--fail-on`` over files it never checked. They now go to
``meta.not_analyzed`` with the missing grammar named, so the existing gate
fails closed. No test touches the network: the download is simulated.
"""

import json

import pytest
from click.testing import CliRunner

from hefesto.cli.main import cli
from hefesto.core.parsers import treesitter_parser

pack = pytest.importorskip("tree_sitter_language_pack")
DownloadError = pack.DownloadError  # what get_parser raises offline with an empty cache


@pytest.fixture
def grammar_download_fails(monkeypatch):
    """Empty cache, no network: every grammar load raises like the real pack."""

    def get_parser(name):
        raise DownloadError(f"Download error: Failed to fetch manifest for {name}")

    monkeypatch.setattr(treesitter_parser, "USE_PREBUILT", True)
    monkeypatch.setattr(treesitter_parser, "get_ts_parser", get_parser)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    monkeypatch.setenv("HEFESTO_NO_UPSELL", "1")


def _write_jvm_go_rust(root):
    (root / "A.java").write_text("public class A { int f(int x) { return x; } }\n")
    (root / "g.go").write_text("package main\nfunc F(x int) int { return x }\n")
    (root / "r.rs").write_text("fn f(x: i32) -> i32 { x }\n")


def _analyze(root, *extra):
    try:
        runner = CliRunner(mix_stderr=False)  # click < 8.2
    except TypeError:
        runner = CliRunner()  # click >= 8.2 keeps stderr apart
    return runner.invoke(cli, ["analyze", str(root), "--no-config", "--output", "json", *extra])


def _not_analyzed(result):
    return json.loads(result.stdout)["meta"].get("not_analyzed") or []


def test_mixed_repo_fails_closed_when_grammars_cannot_load(tmp_path, grammar_download_fails):
    _write_jvm_go_rust(tmp_path)
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")

    result = _analyze(tmp_path, "--fail-on", "LOW")

    assert result.exit_code == 1, result.stderr
    entries = _not_analyzed(result)
    assert sorted(e["path"].rsplit("/", 1)[-1] for e in entries) == ["A.java", "g.go", "r.rs"]
    assert {e["reason"] for e in entries} == {"grammar_unavailable"}
    assert {e["grammar"] for e in entries} == {"java", "go", "rust"}
    assert "tree-sitter grammar 'java' could not be loaded" in result.stderr


def test_allow_not_analyzed_still_opts_out(tmp_path, grammar_download_fails):
    _write_jvm_go_rust(tmp_path)
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")

    result = _analyze(tmp_path, "--fail-on", "LOW", "--allow-not-analyzed")

    assert result.exit_code == 0, result.stderr
    assert len(_not_analyzed(result)) == 3


def test_without_fail_on_exit_stays_zero(tmp_path, grammar_download_fails):
    _write_jvm_go_rust(tmp_path)
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")

    result = _analyze(tmp_path)

    assert result.exit_code == 0, result.stderr
    assert len(_not_analyzed(result)) == 3


def test_zero_files_warning_names_the_missing_grammar(tmp_path, grammar_download_fails):
    _write_jvm_go_rust(tmp_path)

    result = _analyze(tmp_path, "--fail-on", "LOW")

    assert result.exit_code == 1
    assert "no supported source files, or every file was excluded" not in result.stderr
    assert "tree-sitter grammar could not be loaded for go, java, rust" in result.stderr


def test_an_error_outside_the_grammar_pack_stays_a_skip(tmp_path, monkeypatch):
    """Only the pack's own errors mean "grammar not loaded"; others keep the old path."""

    def get_parser(name):
        raise ValueError("not a grammar problem")

    monkeypatch.setattr(treesitter_parser, "USE_PREBUILT", True)
    monkeypatch.setattr(treesitter_parser, "get_ts_parser", get_parser)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    (tmp_path / "A.java").write_text("public class A {}\n")
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")

    result = _analyze(tmp_path, "--fail-on", "LOW")

    assert result.exit_code == 0, result.stderr
    assert _not_analyzed(result) == []


def test_a_real_parse_error_is_not_reported_as_a_missing_grammar(tmp_path, monkeypatch):
    """Only a failure to load the grammar is reclassified, not one while parsing."""

    def boom(self, code, file_path):
        raise RuntimeError("parse exploded")

    monkeypatch.setattr(treesitter_parser.TreeSitterParser, "parse", boom)
    monkeypatch.setattr(treesitter_parser.TreeSitterParser, "__init__", lambda self, lang: None)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    (tmp_path / "A.java").write_text("public class A {}\n")
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")

    result = _analyze(tmp_path, "--fail-on", "LOW")

    assert result.exit_code == 0, result.stderr
    assert _not_analyzed(result) == []


def test_a_failed_grammar_is_loaded_once_per_run(tmp_path, monkeypatch):
    """A hanging network costs one timeout per grammar, not one per file.

    Every file that needs the failed grammar is still reported as not analyzed.
    """
    calls = []

    def get_parser(name):
        calls.append(name)
        raise DownloadError(f"Download error: timed out fetching {name}")

    monkeypatch.setattr(treesitter_parser, "USE_PREBUILT", True)
    monkeypatch.setattr(treesitter_parser, "get_ts_parser", get_parser)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    monkeypatch.setenv("HEFESTO_NO_UPSELL", "1")
    for i in range(4):
        (tmp_path / f"a{i}.js").write_text(f"function f{i}(x) {{ return x; }}\n")
        (tmp_path / f"G{i}.java").write_text(f"public class G{i} {{ }}\n")
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")

    result = _analyze(tmp_path, "--fail-on", "LOW")

    assert result.exit_code == 1, result.stderr
    assert sorted(calls) == ["java", "javascript"]
    entries = _not_analyzed(result)
    assert len(entries) == 8
    assert {e["reason"] for e in entries} == {"grammar_unavailable"}
    assert {e["grammar"] for e in entries} == {"java", "javascript"}


def test_a_new_run_tries_the_failed_grammar_again(tmp_path, monkeypatch):
    """The failure is remembered for one run only, never across runs."""
    calls = []

    def get_parser(name):
        calls.append(name)
        raise DownloadError(f"Download error: timed out fetching {name}")

    monkeypatch.setattr(treesitter_parser, "USE_PREBUILT", True)
    monkeypatch.setattr(treesitter_parser, "get_ts_parser", get_parser)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    (tmp_path / "A.java").write_text("public class A {}\n")
    (tmp_path / "B.java").write_text("public class B {}\n")

    _analyze(tmp_path)
    _analyze(tmp_path)

    assert calls == ["java", "java"]


def test_concurrent_parser_requests_share_one_failed_load(monkeypatch):
    """Threads asking for the same grammar wait for one load, not one each."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    from hefesto.core.analyzer_engine import AnalyzerEngine
    from hefesto.core.language_detector import Language

    calls = []

    def get_parser(name):
        calls.append(name)
        time.sleep(0.05)  # a slow download that then fails
        raise DownloadError(f"Download error: timed out fetching {name}")

    monkeypatch.setattr(treesitter_parser, "USE_PREBUILT", True)
    monkeypatch.setattr(treesitter_parser, "get_ts_parser", get_parser)
    engine = AnalyzerEngine()
    errors = []

    def worker():
        try:
            engine._get_parser(Language.GO)
        except DownloadError as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for _ in range(6):
            pool.submit(worker)

    assert calls == ["go"]
    assert len(errors) == 6
