import subprocess
from pathlib import Path

import pytest

from hefesto.critical_tests.check import check_critical_tests
from hefesto.critical_tests.policy import parse_critical_tests


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


POLICY = parse_critical_tests(
    {
        "entries": [
            {
                "id": "authz",
                "requirement": "Users must not access resources they do not own.",
                "tests": ["tests/test_auth.py::test_a"],
                "enforcement": "block",
            },
            {
                "id": "billing",
                "requirement": "Charges are per user.",
                "tests": ["tests/test_bill.py::test_b"],
            },
        ]
    }
)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_auth.py").write_text("def test_a():\n    assert 1 == 1\n")
    (tests / "test_bill.py").write_text("def test_b():\n    assert 2 == 2\n")
    _commit(tmp_path, "base")
    return tmp_path


def test_untouched_mapped_files_report_nothing(repo: Path) -> None:
    (repo / "other.py").write_text("x = 1\n")
    _commit(repo, "unrelated")
    result = check_critical_tests(repo, POLICY, "main~1", "HEAD")
    assert result.findings == []
    assert result.errors == []


def test_trivialized_and_deleted_tests_carry_entry_and_enforcement(repo: Path) -> None:
    (repo / "tests" / "test_auth.py").write_text("def test_a():\n    pass\n")
    (repo / "tests" / "test_bill.py").unlink()
    _commit(repo, "weaken")
    result = check_critical_tests(repo, POLICY, "main~1", "HEAD")
    by_entry = {f.entry_id: f for f in result.findings}
    assert by_entry["authz"].rule_id == "CT_TRIVIALIZED"
    assert by_entry["authz"].enforcement == "block"
    assert by_entry["authz"].nodeid == "tests/test_auth.py::test_a"
    assert by_entry["billing"].rule_id == "CT_DELETED"
    assert by_entry["billing"].enforcement == "warn"
    assert by_entry["billing"].head_path is None


def test_renamed_file_is_compared_by_content(repo: Path) -> None:
    _git(repo, "mv", "tests/test_auth.py", "tests/test_authz.py")
    _commit(repo, "rename")
    result = check_critical_tests(repo, POLICY, "main~1", "HEAD")
    assert result.findings == []


def test_unparseable_head_is_an_error_not_a_crash(repo: Path) -> None:
    (repo / "tests" / "test_auth.py").write_text("def test_a(:\n")
    _commit(repo, "broken")
    result = check_critical_tests(repo, POLICY, "main~1", "HEAD")
    assert result.findings == []
    assert len(result.errors) == 1
    assert result.errors[0].startswith("tests/test_auth.py:")


def test_base_is_the_merge_base(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "tests" / "test_auth.py").write_text("def test_a():\n    pass\n")
    _commit(repo, "weaken on feature")
    _git(repo, "checkout", "-q", "main")
    (repo / "tests" / "test_bill.py").write_text("def test_b():\n    pass\n")
    _commit(repo, "main moves on")
    result = check_critical_tests(repo, POLICY, "main", "feature")
    assert [f.entry_id for f in result.findings] == ["authz"]


def test_owners_by_test_keeps_every_entry_in_order():
    from hefesto.critical_tests.check import _owners_by_test

    refs = [("a", "test_x"), ("b", "test_y"), ("c", "test_x")]
    assert _owners_by_test(refs) == {"test_x": ["a", "c"], "test_y": ["b"]}
