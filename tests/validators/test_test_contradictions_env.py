"""Nullary calls whose result depends on the environment are not contradictions.

``check-test-contradictions`` compares a plain call only when every argument is
a literal. A call with no arguments satisfies that vacuously, so two tests that
call ``feature()`` and expect different values were reported even when each
test had set a different environment (env vars, monkeypatch, platform, clock).

Literal-argument contradictions, and nullary calls whose tests set the same
environment (or none), stay reported.
"""

from click.testing import CliRunner

from hefesto.cli.main import cli
from hefesto.validators.test_contradictions import TestContradictionDetector


def _write(tmp_path, source: str) -> TestContradictionDetector:
    (tmp_path / "test_env.py").write_text(source)
    return TestContradictionDetector(str(tmp_path))


def _names(found):
    return [(c.function_called, c.arguments) for c in found]


# ------------------------------------------------------- false positive: environment


def test_different_monkeypatch_env_is_not_a_contradiction(tmp_path):
    """Reproduction: the 4.17.0 false positive (feature flag via monkeypatch)."""
    src = """
def test_on(monkeypatch):
    monkeypatch.delenv("FLAG", raising=False)
    assert feature_enabled() == True

def test_off(monkeypatch):
    monkeypatch.setenv("FLAG", "0")
    assert feature_enabled() == False
"""
    found = _write(tmp_path, src).find_contradictions()
    assert found == []


def test_different_os_environ_assignments_are_not_a_contradiction(tmp_path):
    src = """
def test_on():
    os.environ["FLAG"] = "1"
    assert feature_enabled() == True

def test_off():
    os.environ["FLAG"] = "0"
    assert feature_enabled() == False
"""
    assert _write(tmp_path, src).find_contradictions() == []


def test_patch_dict_environments_are_not_a_contradiction(tmp_path):
    src = """
def test_off():
    with patch.dict(os.environ, {"FLAG": "0"}):
        assert feature_enabled() == False

def test_on():
    with mock.patch.dict(os.environ, {"FLAG": "1"}):
        assert feature_enabled() == True
"""
    assert _write(tmp_path, src).find_contradictions() == []


def test_different_platform_skipif_is_not_a_contradiction(tmp_path):
    src = """
@pytest.mark.skipif(sys.platform == "win32", reason="posix")
def test_posix():
    assert separator() == "/"

@pytest.mark.skipif(sys.platform != "win32", reason="windows")
def test_windows():
    assert separator() == "\\\\"
"""
    assert _write(tmp_path, src).find_contradictions() == []


def test_platform_branch_before_the_assert_is_not_a_contradiction(tmp_path):
    src = """
def test_posix():
    if sys.platform == "win32":
        pytest.skip("windows")
    assert separator() == "/"

def test_windows():
    if sys.platform != "win32":
        pytest.skip("posix")
    assert separator() == "\\\\"
"""
    assert _write(tmp_path, src).find_contradictions() == []


def test_different_freeze_time_is_not_a_contradiction(tmp_path):
    src = """
@freeze_time("2020-01-01 08:00")
def test_morning():
    assert greeting() == "morning"

@freeze_time("2020-01-01 20:00")
def test_evening():
    assert greeting() == "evening"
"""
    assert _write(tmp_path, src).find_contradictions() == []


def test_monkeypatch_setattr_of_the_clock_is_not_a_contradiction(tmp_path):
    src = """
def test_epoch(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1)
    assert now() == 1

def test_later(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 2)
    assert now() == 2
"""
    assert _write(tmp_path, src).find_contradictions() == []


def test_uncontrolled_clock_read_is_not_a_contradiction(tmp_path):
    """The wall clock differs between tests even when the source looks the same."""
    src = """
def test_a():
    _ = datetime.now()
    assert stamp() == "a"

def test_b():
    _ = time.time()
    assert stamp() == "b"
"""
    assert _write(tmp_path, src).find_contradictions() == []


def test_sequential_env_changes_in_one_test_are_not_a_contradiction(tmp_path):
    src = """
def test_both(monkeypatch):
    monkeypatch.delenv("FLAG", raising=False)
    assert feature_enabled() == True
    monkeypatch.setenv("FLAG", "0")
    assert feature_enabled() == False
"""
    assert _write(tmp_path, src).find_contradictions() == []


def test_cli_exits_0_when_only_the_environment_differs(tmp_path):
    src = """
def test_on(monkeypatch):
    monkeypatch.delenv("FLAG", raising=False)
    assert feature_enabled() == True

def test_off(monkeypatch):
    monkeypatch.setenv("FLAG", "0")
    assert feature_enabled() == False
"""
    (tmp_path / "test_env.py").write_text(src)
    result = CliRunner().invoke(cli, ["check-test-contradictions", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


# --------------------------------------------- real contradictions stay reported


def test_literal_arguments_are_still_a_contradiction(tmp_path):
    src = """
def test_a():
    assert add(1, 2) == 3

def test_b():
    assert add(1, 2) == 4
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("add", "1, 2")]


def test_literal_arguments_contradict_even_with_a_clock_read(tmp_path):
    src = """
def test_a():
    _ = datetime.now()
    assert add(1, 2) == 3

def test_b():
    _ = time.time()
    assert add(1, 2) == 4
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("add", "1, 2")]


def test_literal_arguments_contradict_even_when_the_env_differs(tmp_path):
    src = """
def test_a(monkeypatch):
    monkeypatch.setenv("FLAG", "0")
    assert add(1, 2) == 3

def test_b(monkeypatch):
    monkeypatch.setenv("FLAG", "1")
    assert add(1, 2) == 4
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("add", "1, 2")]


def test_nullary_call_without_environment_is_still_a_contradiction(tmp_path):
    src = """
def test_a():
    assert func() == 1

def test_b():
    assert func() == 2
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("func", "")]


def test_nullary_call_with_the_same_environment_is_still_a_contradiction(tmp_path):
    src = """
def test_a(monkeypatch):
    monkeypatch.setenv("FLAG", "1")
    assert feature_enabled() == True

def test_b(monkeypatch):
    monkeypatch.setenv("FLAG", "1")
    assert feature_enabled() == False
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("feature_enabled", "")]


def test_same_freeze_time_is_still_a_contradiction(tmp_path):
    src = """
@freeze_time("2020-01-01 08:00")
def test_a():
    seen = datetime.now()
    assert stamp() == "a"

@freeze_time("2020-01-01 08:00")
def test_b():
    seen = datetime.now()
    assert stamp() == "b"
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("stamp", "")]


def test_same_platform_skipif_is_still_a_contradiction(tmp_path):
    src = """
@pytest.mark.skipif(sys.platform == "win32", reason="posix")
def test_a():
    assert separator() == "/"

@pytest.mark.skipif(sys.platform == "win32", reason="not windows")
def test_b():
    assert separator() == "\\\\"
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("separator", "")]


def test_unittest_assert_equal_nullary_is_still_a_contradiction(tmp_path):
    src = """
class T:
    def test_a(self):
        self.assertEqual(func(), 1)

    def test_b(self):
        self.assertEqual(func(), 2)

    def test_off(self):
        self.monkeypatch.setenv("FLAG", "0")
        self.assertEqual(feature_enabled(), False)

    def test_on(self):
        self.monkeypatch.setenv("FLAG", "1")
        self.assertEqual(feature_enabled(), True)
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("func", "")]


def test_keyword_literals_are_still_a_contradiction(tmp_path):
    src = """
def test_a():
    assert add(a=1, b=2) == 3

def test_b():
    assert add(a=1, b=2) == 4
"""
    found = _write(tmp_path, src).find_contradictions()
    assert _names(found) == [("add", "a=1, b=2")]
