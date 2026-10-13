"""check-test-contradictions must check, not pass silently (Python 3.14 regression).

On 3.14 ``ast.Num``/``ast.Str``/``ast.NameConstant`` are gone; ``_extract_value``
raised AttributeError, ``_parse_test_file`` swallowed it and the command printed PASS.
"""

import ast

import pytest
from click.testing import CliRunner

from hefesto.cli.main import cli
from hefesto.validators.test_contradictions import TestContradictionDetector

CONTRADICTORY = (
    "def test_a():\n    assert add(x, [1], None) == 3\n\n"
    "def test_b():\n    assert add(x, [1], None) == 4\n"
)


def test_non_constant_arguments_still_find_the_contradiction(tmp_path):
    (tmp_path / "test_x.py").write_text(CONTRADICTORY)
    detector = TestContradictionDetector(str(tmp_path))
    found = detector.find_contradictions()
    assert len(found) == 1
    assert found[0].arguments == "x, [1], None"


def test_extract_value_only_needs_ast_constant():
    detector = TestContradictionDetector()
    assert detector._extract_value(ast.Constant(value=None)) == "None"
    assert detector._extract_value(ast.Constant(value="s")) == "'s'"
    assert detector._extract_value(ast.Tuple(elts=[], ctx=ast.Load())) == "?"


def test_cli_exit_1_on_contradiction(tmp_path):
    (tmp_path / "test_x.py").write_text(CONTRADICTORY)
    result = CliRunner().invoke(cli, ["check-test-contradictions", str(tmp_path)])
    assert result.exit_code == 1, result.output


def test_unparseable_file_is_reported_as_skipped(tmp_path, capsys):
    (tmp_path / "test_bad.py").write_text("def test_(:\n")
    (tmp_path / "test_bin.py").write_bytes(b"\xff\xfe\x00bad")
    detector = TestContradictionDetector(str(tmp_path))
    assert detector.find_contradictions() == []
    assert sorted(p.name for p, _ in detector.skipped_files) == ["test_bad.py", "test_bin.py"]
    detector.print_report([])
    out = capsys.readouterr().out
    assert "Skipped 2 file(s)" in out and "test_bad.py" in out


def test_internal_error_exits_non_zero(tmp_path, monkeypatch):
    (tmp_path / "test_x.py").write_text(CONTRADICTORY)

    def boom(self, node):
        raise AttributeError("module 'ast' has no attribute 'Num'")

    monkeypatch.setattr(TestContradictionDetector, "_extract_value", boom)
    with pytest.raises(AttributeError):
        TestContradictionDetector(str(tmp_path)).find_contradictions()
    result = CliRunner().invoke(cli, ["check-test-contradictions", str(tmp_path)])
    assert result.exit_code not in (0, 1), result.output
    assert "PASS" not in result.output
    assert "internal error" in result.output.lower()
