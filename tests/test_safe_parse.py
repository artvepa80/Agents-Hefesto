"""Every ``ast.parse`` of analyzed code goes through ``hefesto.core.safe_parse``.

Python's compiler reports problems in the analyzed code (for example an
invalid escape sequence) as ``SyntaxWarning``. Under ``PYTHONWARNINGS=error``
or ``-W error`` that warning becomes a ``SyntaxError``, so a parse that
succeeds in one environment failed in another and the analyzers returned no
findings without saying so. These tests pin the shared helper's contract and
check that findings do not depend on the warning filters of the process.
"""

from __future__ import annotations

import ast
import json
import os
import random
import re
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

from hefesto.core import safe_parse as safe_parse_module
from hefesto.core.safe_parse import ParseResult, safe_parse

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "hefesto"

# Planted findings: eval (CRITICAL), pickle (HIGH), assert and bare except
# (MEDIUM). Line 4 has an invalid escape sequence, which makes the compiler
# emit a SyntaxWarning (DeprecationWarning before Python 3.12).
SAMPLE = (
    "import pickle\n"
    "import re\n"
    "\n"
    'PATTERN = re.compile("\\d+")\n'
    "\n"
    "\n"
    "def run(user_input):\n"
    "    try:\n"
    "        return eval(user_input)\n"
    "    except:\n"
    "        pass\n"
    "\n"
    "\n"
    "def load(blob):\n"
    "    assert blob\n"
    "    return pickle.loads(blob)\n"
)
EXPECTED_TYPES = ["ASSERT_IN_PRODUCTION", "BARE_EXCEPT", "EVAL_USAGE", "PICKLE_USAGE"]


# ---------------------------------------------------------------------------
# Helper contract
# ---------------------------------------------------------------------------


def test_valid_source_returns_tree_and_no_error() -> None:
    result = safe_parse("x = 1\n", "ok.py")
    assert isinstance(result, ParseResult)
    assert isinstance(result.tree, ast.Module)
    assert result.error is None
    assert result.exception is None
    assert result.warnings == ()


def test_invalid_escape_is_recorded_not_emitted() -> None:
    with warnings.catch_warnings(record=True) as outer:
        warnings.simplefilter("always")
        result = safe_parse('s = "\\d"\n', "esc.py")
    assert result.tree is not None
    assert outer == []
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.category in ("SyntaxWarning", "DeprecationWarning")
    assert warning.lineno == 1
    assert "escape" in warning.message


def test_invalid_escape_parses_under_error_filter() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = safe_parse('s = "\\d"\n', "esc.py")
    assert result.tree is not None
    assert result.error is None


def test_syntax_error_maps_to_syntax_and_keeps_filename() -> None:
    result = safe_parse("def broken(:\n", "pkg/broken.py")
    assert result.tree is None
    assert result.error == "syntax"
    assert isinstance(result.exception, SyntaxError)
    assert result.exception.filename == "pkg/broken.py"
    assert result.error_type == "SyntaxError"
    assert result.error_message == str(result.exception)


def test_null_bytes_never_raise() -> None:
    # SyntaxError on Python >= 3.11.4 / 3.12, ValueError on 3.10 to 3.11.3.
    result = safe_parse("x = 1\x00\n", "nul.py")
    assert result.tree is None
    assert result.error in ("syntax", "invalid_source")


@pytest.mark.parametrize(
    "exc,kind",
    [
        (SyntaxError("bad"), "syntax"),
        (ValueError("source code string cannot contain null bytes"), "invalid_source"),
        (RecursionError("maximum recursion depth exceeded"), "too_complex"),
        (MemoryError(), "too_complex"),
    ],
)
def test_exception_mapping(monkeypatch: pytest.MonkeyPatch, exc: BaseException, kind: str) -> None:
    def _raise(*_args: object, **_kwargs: object) -> ast.Module:
        raise exc

    monkeypatch.setattr(safe_parse_module.ast, "parse", _raise)
    result = safe_parse("x = 1\n", "m.py")
    assert result.tree is None
    assert result.error == kind
    assert result.exception is exc
    assert result.error_type == type(exc).__name__


def test_other_exceptions_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: object, **_kwargs: object) -> ast.Module:
        raise TypeError("not a parse failure")

    monkeypatch.setattr(safe_parse_module.ast, "parse", _raise)
    with pytest.raises(TypeError):
        safe_parse("x = 1\n", "m.py")


def test_deeply_nested_source_does_not_raise() -> None:
    result = safe_parse("x = " + "(" * 5000 + "1" + ")" * 5000 + "\n", "deep.py")
    assert result.tree is None
    assert result.error in ("syntax", "too_complex")


def test_bytes_utf8_parse() -> None:
    result = safe_parse('s = "caf\u00e9"\n'.encode("utf-8"), "u.py")
    assert result.tree is not None


def test_bytes_with_encoding_declaration_use_declaration() -> None:
    source = '# -*- coding: latin-1 -*-\ns = "caf\u00e9"\n'.encode("latin-1")
    result = safe_parse(source, "decl.py", fallback_text="unused = 1\n")
    assert result.tree is not None
    assign = result.tree.body[0]
    assert isinstance(assign, ast.Assign)
    assert isinstance(assign.value, ast.Constant)
    assert assign.value.value == "caf\u00e9"


def test_non_utf8_bytes_without_declaration_fall_back_to_decoded_text() -> None:
    raw = 's = "caf\u00e9"\n'.encode("latin-1")
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")
    result = safe_parse(raw, "latin.py", fallback_text=raw.decode("latin-1"))
    assert result.tree is not None
    assert result.error is None


def test_non_utf8_bytes_without_fallback_report_syntax() -> None:
    raw = 's = "caf\u00e9"\n'.encode("latin-1")
    result = safe_parse(raw, "latin.py")
    assert result.tree is None
    assert result.error == "syntax"


def test_warning_filters_unchanged_after_calls() -> None:
    before = list(warnings.filters)
    for source in ('s = "\\d"\n', "def broken(:\n", "x = 1\x00\n", "x = 1\n"):
        safe_parse(source, "f.py")
    assert warnings.filters == before


# ---------------------------------------------------------------------------
# Seeded fuzz loop (no third-party dependency)
# ---------------------------------------------------------------------------


def test_fuzz_random_bytes_never_raise() -> None:
    from hefesto.core.parsers.python_parser import PythonParser

    rng = random.Random(20261025)
    fragments = [
        b"def f(",
        b"):\n    ",
        b'"\\d"',
        b"\x00",
        b"\xff\xfe",
        b"(" * 50,
        b"\n",
        b"# coding: latin-1\n",
    ]
    parser = PythonParser()
    before = list(warnings.filters)
    for _ in range(400):
        if rng.random() < 0.5:
            raw = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 200)))
        else:
            raw = b"".join(rng.choice(fragments) for _ in range(rng.randint(0, 12)))
        text = raw.decode("latin-1")
        for result in (safe_parse(raw, "fuzz.py", fallback_text=text), safe_parse(text, "fuzz.py")):
            assert (result.tree is None) == (result.error is not None)
            assert result.error in (None, "syntax", "invalid_source", "too_complex")
        if "\x00" not in text:
            parser.parse(text, "fuzz.py")
    assert warnings.filters == before


# ---------------------------------------------------------------------------
# Every ast.parse call goes through the helper
# ---------------------------------------------------------------------------

_PARSE_CALL = re.compile(r"\bast\.parse\(|_ast\.parse\(|from\s+ast\s+import\s+[^\n]*\bparse\b")


def test_no_direct_ast_parse_outside_helper() -> None:
    offenders = []
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        if path.name == "safe_parse.py" and path.parent.name == "core":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _PARSE_CALL.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert offenders == [], "use hefesto.core.safe_parse.safe_parse:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# End to end: stderr and findings do not depend on warning filters
# ---------------------------------------------------------------------------


def _run_analyze(
    target: Path, pythonwarnings: Optional[str]
) -> Tuple[int, List[Tuple[str, int]], str]:
    env: Dict[str, str] = dict(os.environ)
    env.pop("PYTHONWARNINGS", None)
    env["HEFESTO_TELEMETRY"] = "0"
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    if pythonwarnings is not None:
        env["PYTHONWARNINGS"] = pythonwarnings
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "hefesto",
            "analyze",
            str(target),
            "--severity",
            "low",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        cwd=str(target.parent),
    )
    report = json.loads(proc.stdout)
    findings = sorted(
        (issue["type"], issue["line"]) for entry in report["files"] for issue in entry["issues"]
    )
    return proc.returncode, findings, proc.stderr


@pytest.fixture()
def sample_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.py"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def test_analyze_writes_no_python_warnings_to_stderr(sample_file: Path) -> None:
    for mode in (None, "always", "default"):
        _, _, stderr = _run_analyze(sample_file, mode)
        assert "SyntaxWarning" not in stderr, (mode, stderr)
        assert "DeprecationWarning" not in stderr, (mode, stderr)


def test_findings_identical_with_and_without_warnings_as_errors(sample_file: Path) -> None:
    code_default, default, _ = _run_analyze(sample_file, None)
    code_error, as_error, _ = _run_analyze(sample_file, "error")
    assert sorted({kind for kind, _ in default}) == EXPECTED_TYPES
    assert as_error == default
    assert code_error == code_default
