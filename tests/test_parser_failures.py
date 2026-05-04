"""Tests for parser-failure visibility (Item 1: UX gap correctivo).

Surfaces silent skips that occur when tree-sitter-dependent languages
(TS/JS/Java/Go/Rust/C#) cannot be parsed because the optional grammar pack
``[multilang]`` is not installed. Verifies:

1. Categorization (``parser_unavailable`` vs ``parse_error``)
2. Accumulation in ``self._parser_failures`` for the 6 affected languages
3. ``meta["parser_failures"]`` exposed via ``_build_meta``
4. stderr emission gated by ``quiet`` (matrix: quiet × output)

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from hefesto.core.analyzer_engine import AnalyzerEngine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Categorization (unit)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc,expected",
    [
        (ImportError("no module named 'tree_sitter_language_pack'"), "parser_unavailable"),
        (OSError("Could not load build/languages.so"), "parser_unavailable"),
        (RuntimeError("languages.so not found"), "parser_unavailable"),
        (RuntimeError("tree_sitter_language_pack version mismatch"), "parser_unavailable"),
        (UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid start byte"), "parse_error"),
        (ValueError("syntax error in source"), "parse_error"),
        (RuntimeError("unknown internal failure"), "parse_error"),
        (TypeError("incompatible AST node"), "parse_error"),
    ],
)
def test_categorize_parser_failure(exc: Exception, expected: str) -> None:
    engine = AnalyzerEngine(severity_threshold="LOW")
    assert engine._categorize_parser_failure(exc) == expected


# ---------------------------------------------------------------------------
# Accumulation across the 6 tree-sitter-dependent languages
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ext,lang_value,sample",
    [
        (".js", "javascript", "export function foo(){ return 1 }\n"),
        (".ts", "typescript", "export function foo(): number { return 1 }\n"),
        (".java", "java", "class Foo { int bar() { return 1; } }\n"),
        (".go", "go", "package main\n\nfunc Foo() int { return 1 }\n"),
        (".rs", "rust", "pub fn foo() -> i32 { 1 }\n"),
        (".cs", "csharp", "class Foo { int Bar() { return 1; } }\n"),
    ],
)
def test_parser_failure_recorded_when_factory_raises(
    ext: str, lang_value: str, sample: str, tmp_path: Path
) -> None:
    """When ParserFactory.get_parser raises, the file is recorded with the
    correct language and category."""
    _write(tmp_path / f"sample{ext}", sample)

    engine = AnalyzerEngine(severity_threshold="LOW")

    # Simulate "no [multilang] installed and no build/languages.so" by forcing
    # the factory to raise OSError — the same shape that the real code path
    # produces in a clean PyPI install (verified empirically in γ-2).
    with patch(
        "hefesto.core.analyzer_engine.ParserFactory.get_parser",
        side_effect=OSError("languages.so not found"),
    ):
        engine.analyze_files([str(tmp_path / f"sample{ext}")])

    assert len(engine._parser_failures) == 1
    failure = engine._parser_failures[0]
    assert failure["language"] == lang_value
    assert failure["category"] == "parser_unavailable"
    assert failure["exception"] == "OSError"
    assert failure["path"].endswith(f"sample{ext}")


# ---------------------------------------------------------------------------
# meta["parser_failures"] exposure
# ---------------------------------------------------------------------------


def test_build_meta_includes_parser_failures(tmp_path: Path) -> None:
    """Skips populate ``meta["parser_failures"]`` so JSON output reflects them."""
    _write(tmp_path / "a.js", "export function foo(){ return 1 }\n")

    engine = AnalyzerEngine(severity_threshold="LOW")
    with patch(
        "hefesto.core.analyzer_engine.ParserFactory.get_parser",
        side_effect=OSError("languages.so not found"),
    ):
        engine.analyze_files([str(tmp_path / "a.js")])

    meta = engine._build_meta()
    assert "parser_failures" in meta
    assert len(meta["parser_failures"]) == 1
    assert meta["parser_failures"][0]["language"] == "javascript"


def test_build_meta_omits_parser_failures_when_none(tmp_path: Path) -> None:
    """No skips → ``parser_failures`` key absent (not empty list)."""
    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.analyze_files([])
    meta = engine._build_meta()
    assert "parser_failures" not in meta


# ---------------------------------------------------------------------------
# stderr emission gated by quiet (matrix: quiet × output)
# ---------------------------------------------------------------------------


def test_emit_skip_summary_writes_to_stderr_when_not_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "a.js", "export function foo(){ return 1 }\n")

    engine = AnalyzerEngine(severity_threshold="LOW", quiet=False)
    with patch(
        "hefesto.core.analyzer_engine.ParserFactory.get_parser",
        side_effect=OSError("languages.so not found"),
    ):
        engine.analyze_files([str(tmp_path / "a.js")])

    captured = capsys.readouterr()
    assert "parser unavailable" in captured.err
    assert "javascript" in captured.err
    assert "pip install hefesto-ai[multilang]" in captured.err


def test_emit_skip_summary_silent_when_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "a.js", "export function foo(){ return 1 }\n")

    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    with patch(
        "hefesto.core.analyzer_engine.ParserFactory.get_parser",
        side_effect=OSError("languages.so not found"),
    ):
        engine.analyze_files([str(tmp_path / "a.js")])

    captured = capsys.readouterr()
    assert captured.err == ""
    # Data still available structurally for --output json consumers.
    assert "parser_failures" in engine._build_meta()


def test_emit_skip_summary_separates_categories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When both categories present, both warnings emit independently;
    actionable (parser_unavailable) goes first.

    Patches ``USE_PREBUILT=True`` to bypass the strong-signal path so the
    fallback heuristic (which discriminates by exception type/message) is
    exercised and both categories can coexist. The strong-signal path itself
    is covered by the integration test below.
    """
    _write(tmp_path / "good.js", "export function foo(){ return 1 }\n")
    _write(tmp_path / "bad.js", "export function bar(){ return 2 }\n")

    engine = AnalyzerEngine(severity_threshold="LOW", quiet=False)
    # Mix: first call raises OSError (unavailable), second raises ValueError (parse_error).
    side_effects: list[Any] = [
        OSError("languages.so not found"),
        ValueError("syntax error in source"),
    ]
    with (
        patch("hefesto.core.parsers.treesitter_parser.USE_PREBUILT", True),
        patch(
            "hefesto.core.analyzer_engine.ParserFactory.get_parser",
            side_effect=side_effects,
        ) as mock_factory,
    ):
        engine.analyze_files([str(tmp_path / "good.js"), str(tmp_path / "bad.js")])

    # Pin the assumption that the factory is called exactly once per file —
    # if a future refactor changes call frequency, this fails loudly instead
    # of producing misleading category counts.
    assert mock_factory.call_count == 2

    captured = capsys.readouterr()
    # Both warnings present
    assert "parser unavailable" in captured.err
    assert "parse error" in captured.err
    # Actionable first
    assert captured.err.index("parser unavailable") < captured.err.index("parse error")


def test_no_emission_when_no_failures(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Clean run produces no stderr noise."""
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=False)
    engine.analyze_files([])
    captured = capsys.readouterr()
    assert captured.err == ""


# ---------------------------------------------------------------------------
# Integration — end-to-end CLI reproduction (no mocks)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_cli_real_silent_skip_emits_warning_and_json_meta(tmp_path: Path) -> None:
    """End-to-end: run ``hefesto analyze`` via subprocess on a .js file in a
    venv that does NOT have ``[multilang]`` installed. Verifies the real path
    (no mocks): silent skip is detected, stderr warning emits, JSON output
    has ``meta.parser_failures`` populated.

    Skips automatically when the grammar pack IS installed (``USE_PREBUILT``
    is True), since the silent-skip precondition cannot be reproduced.
    """
    import json
    import os
    import subprocess
    import sys

    from hefesto.core.parsers.treesitter_parser import USE_PREBUILT

    if USE_PREBUILT:
        pytest.skip(
            "tree-sitter-language-pack is installed in this venv; "
            "silent-skip precondition not reproducible"
        )

    js_file = tmp_path / "a.js"
    js_file.write_text("export function foo(){ return 1 }\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hefesto.cli.main",
            "analyze",
            str(tmp_path),
            "--severity",
            "LOW",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "HEFESTO_TELEMETRY": "0"},
    )

    # Must not crash — that would be Caso 2 (real bug, not the UX gap we fix here).
    assert result.returncode == 0, f"hefesto analyze crashed: {result.stderr}"

    # stdout is pure JSON (per cli/main.py policy)
    data = json.loads(result.stdout)
    assert "meta" in data, "expected meta key in JSON output"
    assert (
        "parser_failures" in data["meta"]
    ), f"expected meta.parser_failures, got meta keys: {list(data['meta'].keys())}"

    failures = data["meta"]["parser_failures"]
    assert len(failures) == 1
    assert failures[0]["language"] == "javascript"
    assert failures[0]["category"] == "parser_unavailable"

    # stderr warning emitted (real behavior, not mock)
    assert "parser unavailable" in result.stderr
    assert "javascript" in result.stderr
    assert "pip install hefesto-ai[multilang]" in result.stderr
