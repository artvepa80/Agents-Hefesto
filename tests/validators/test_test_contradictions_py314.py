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
    "def test_a():\n    assert add(1, 2) == 3\n\n" "def test_b():\n    assert add(1, 2) == 4\n"
)
# Same call shape, but a name argument: what `issues` holds differs per test.
NON_LITERAL = (
    "def test_a():\n    assert add(x, [1], None) == 3\n\n"
    "def test_b():\n    assert add(x, [1], None) == 4\n"
)


def test_non_literal_arguments_are_not_compared(tmp_path):
    (tmp_path / "test_x.py").write_text(NON_LITERAL)
    detector = TestContradictionDetector(str(tmp_path))
    assert detector.find_contradictions() == []
    assert detector.checked_files == 1


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


# --------------------------------------------- zero checked files is never PASS


def test_empty_directory_is_not_pass(tmp_path):
    result = CliRunner().invoke(cli, ["check-test-contradictions", str(tmp_path)])
    assert result.exit_code not in (0, 1), result.output
    assert "PASS" not in result.output
    assert "No test files were checked" in result.output
    assert "0 skipped" in result.output


def test_every_file_skipped_is_not_pass(tmp_path):
    (tmp_path / "test_bad.py").write_text("def test_(:\n")
    (tmp_path / "test_bad2.py").write_text("class (:\n")
    result = CliRunner().invoke(cli, ["check-test-contradictions", str(tmp_path)])
    assert result.exit_code not in (0, 1), result.output
    assert "PASS" not in result.output
    assert "No test files were checked" in result.output
    assert "2 skipped" in result.output


def test_one_good_file_is_checked(tmp_path):
    (tmp_path / "test_bad.py").write_text("def test_(:\n")
    (tmp_path / "test_ok.py").write_text("def test_a():\n    assert f(1) == 1\n")
    detector = TestContradictionDetector(str(tmp_path))
    assert detector.find_contradictions() == []
    assert detector.checked_files == 1
    result = CliRunner().invoke(cli, ["check-test-contradictions", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


# ------------------------------------- conservative: plain function + literal args


@pytest.mark.parametrize(
    "call",
    [
        "add(1, 2)",
        "add(a=1, b='x')",
        "add([1, 2], (3, None))",
    ],
)
def test_literal_calls_on_a_plain_function_are_compared(tmp_path, call):
    src = f"def test_a():\n    assert {call} == 3\n\ndef test_b():\n    assert {call} == 4\n"
    (tmp_path / "test_x.py").write_text(src)
    found = TestContradictionDetector(str(tmp_path)).find_contradictions()
    assert len(found) == 1
    assert found[0].function_called == "add"


@pytest.mark.parametrize(
    "call",
    [
        "len(issues)",  # local name: different value in each test
        "len(result.issues)",  # attribute
        "len(get())",  # nested call
        "obj.add(1, 2)",  # method on a local object
        "self.add(1, 2)",
        "add(*args)",
        "add(**kw)",
        "add([1, x])",  # list with a non-literal element
        "add({1: 2})",  # dict renders as '{...}'
    ],
)
def test_non_literal_or_method_calls_are_not_compared(tmp_path, call):
    src = f"def test_a():\n    assert {call} == 1\n\ndef test_b():\n    assert {call} == 3\n"
    (tmp_path / "test_x.py").write_text(src)
    assert TestContradictionDetector(str(tmp_path)).find_contradictions() == []


def test_unittest_assert_equal_follows_the_same_rule(tmp_path):
    src = (
        "class T:\n"
        "    def test_a(self):\n        self.assertEqual(add(1, 2), 3)\n"
        "    def test_b(self):\n        self.assertEqual(add(1, 2), 4)\n"
        "    def test_c(self):\n        self.assertEqual(len(issues), 1)\n"
        "    def test_d(self):\n        self.assertEqual(len(issues), 3)\n"
    )
    (tmp_path / "test_x.py").write_text(src)
    found = TestContradictionDetector(str(tmp_path)).find_contradictions()
    assert [(c.function_called, c.arguments) for c in found] == [("add", "1, 2")]


def test_own_test_suite_has_no_contradictions():
    from pathlib import Path

    tests_dir = Path(__file__).resolve().parents[1]
    found = TestContradictionDetector(str(tests_dir)).find_contradictions()
    assert [(c.function_called, c.arguments, c.test1.test_file) for c in found] == []
