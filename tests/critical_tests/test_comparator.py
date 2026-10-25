"""Tests for the pure critical-test comparator (two source strings, no git).

Copyright (c) 2026 Narapa LLC, Miami, Florida
"""

import ast
import textwrap

import pytest

from hefesto.critical_tests.comparator import (
    ASSERTS_REDUCED,
    DELETED,
    SKIPPED,
    TRIVIALIZED,
    SourceParseError,
    compare_tests,
    count_assertions,
)


def src(text: str) -> str:
    return textwrap.dedent(text).lstrip()


BASE = src("""
    import pytest

    def test_owner_only():
        user = make_user()
        assert can_read(user, own_doc())
        assert not can_read(user, other_doc())

    class TestAdmin:
        def test_admin_only(self):
            assert is_admin(admin())
    """)


def kinds(changes):
    return [(c.kind, c.test) for c in changes]


def test_identical_sources_report_nothing():
    assert compare_tests(BASE, BASE, ["test_owner_only", "TestAdmin::test_admin_only"]) == []


def test_formatting_only_change_reports_nothing():
    head = BASE.replace(
        "assert not can_read(user, other_doc())",
        "assert not can_read(\n        user, other_doc()\n    )",
    )
    assert compare_tests(BASE, head, ["test_owner_only"]) == []


def test_unmapped_test_changes_are_ignored():
    head = BASE.replace("assert is_admin(admin())", "pass")
    assert compare_tests(BASE, head, ["test_owner_only"]) == []


def test_deleted_function():
    head = BASE.split("def test_owner_only")[0] + "class TestAdmin:\n    pass\n"
    changes = compare_tests(BASE, head, ["test_owner_only", "TestAdmin::test_admin_only"])
    assert kinds(changes) == [
        (DELETED, "test_owner_only"),
        (DELETED, "TestAdmin::test_admin_only"),
    ]
    assert changes[0].rule_id == "CT_DELETED"


def test_deleted_file():
    changes = compare_tests(BASE, None, ["test_owner_only"])
    assert kinds(changes) == [(DELETED, "test_owner_only")]


def test_renamed_function_is_reported_as_deleted_by_the_pure_core():
    head = BASE.replace("def test_owner_only", "def test_owner_only_v2")
    assert kinds(compare_tests(BASE, head, ["test_owner_only"])) == [(DELETED, "test_owner_only")]


def test_mapped_test_missing_in_base_is_not_reported():
    assert compare_tests(BASE, BASE, ["test_never_existed"]) == []


def test_last_definition_wins():
    head = BASE + src("""

        def test_owner_only():
            pass
        """)
    assert kinds(compare_tests(BASE, head, ["test_owner_only"])) == [
        (TRIVIALIZED, "test_owner_only")
    ]


def test_async_tests_are_supported():
    base = "async def test_a():\n    assert await ok()\n"
    head = "async def test_a():\n    await ok()\n"
    assert kinds(compare_tests(base, head, ["test_a"])) == [(TRIVIALIZED, "test_a")]


@pytest.mark.parametrize(
    "decorator",
    [
        "@pytest.mark.skip",
        "@pytest.mark.skip(reason='flaky')",
        "@pytest.mark.xfail",
        "@pytest.mark.skipif(True, reason='later')",
        "@unittest.skip('later')",
    ],
)
def test_new_skip_decorator(decorator):
    head = BASE.replace("def test_owner_only", f"{decorator}\ndef test_owner_only")
    changes = compare_tests(BASE, head, ["test_owner_only"])
    assert kinds(changes) == [(SKIPPED, "test_owner_only")]
    assert changes[0].warn_only is False


def test_skip_call_in_body():
    head = BASE.replace(
        "    user = make_user()", "    pytest.skip('later')\n    user = make_user()"
    )
    assert kinds(compare_tests(BASE, head, ["test_owner_only"])) == [(SKIPPED, "test_owner_only")]


def test_module_pytestmark():
    head = BASE.replace("import pytest\n", "import pytest\n\npytestmark = pytest.mark.skip\n")
    changes = compare_tests(BASE, head, ["test_owner_only", "TestAdmin::test_admin_only"])
    assert [c.kind for c in changes] == [SKIPPED, SKIPPED]


def test_class_pytestmark_and_class_decorator():
    head = BASE.replace(
        "class TestAdmin:\n", "class TestAdmin:\n    pytestmark = [pytest.mark.xfail]\n"
    )
    assert kinds(compare_tests(BASE, head, ["TestAdmin::test_admin_only", "test_owner_only"])) == [
        (SKIPPED, "TestAdmin::test_admin_only")
    ]
    head = BASE.replace("class TestAdmin:\n", "@pytest.mark.skip\nclass TestAdmin:\n")
    assert kinds(compare_tests(BASE, head, ["TestAdmin::test_admin_only"])) == [
        (SKIPPED, "TestAdmin::test_admin_only")
    ]


@pytest.mark.parametrize("where", ["module", "class"])
def test_dunder_test_false(where):
    if where == "module":
        head = BASE.replace("import pytest\n", "import pytest\n__test__ = False\n")
    else:
        head = BASE.replace("class TestAdmin:\n", "class TestAdmin:\n    __test__ = False\n")
    changes = compare_tests(BASE, head, ["TestAdmin::test_admin_only"])
    assert kinds(changes) == [(SKIPPED, "TestAdmin::test_admin_only")]


def test_existing_skip_is_not_reported_again():
    base = BASE.replace("def test_owner_only", "@pytest.mark.skip\ndef test_owner_only")
    assert compare_tests(base, base, ["test_owner_only"]) == []


@pytest.mark.parametrize(
    "condition",
    [
        "sys.platform == 'win32'",
        "sys.platform.startswith('win')",
        "os.name == 'nt'",
        "platform.system() == 'Darwin'",
        "sys.platform == 'win32' or os.name == 'nt'",
    ],
)
def test_platform_only_skipif_is_warn_only(condition):
    head = BASE.replace(
        "def test_owner_only",
        f"@pytest.mark.skipif({condition}, reason='posix only')\ndef test_owner_only",
    )
    changes = compare_tests(BASE, head, ["test_owner_only"])
    assert kinds(changes) == [(SKIPPED, "test_owner_only")]
    assert changes[0].warn_only is True


def test_non_platform_skipif_is_not_warn_only():
    head = BASE.replace(
        "def test_owner_only",
        "@pytest.mark.skipif(os.environ.get('CI'), reason='x')\ndef test_owner_only",
    )
    assert compare_tests(BASE, head, ["test_owner_only"])[0].warn_only is False


@pytest.mark.parametrize(
    "body",
    [
        "pass",
        "...",
        "assert True",
        "assert 1",
        '"""Docstring only."""',
        "return\n    assert can_read(make_user(), own_doc())",
        "if False:\n        assert can_read(make_user(), own_doc())",
        "make_user()",
    ],
)
def test_trivialized(body):
    head = BASE.replace(
        "    user = make_user()\n"
        "    assert can_read(user, own_doc())\n"
        "    assert not can_read(user, other_doc())\n",
        f"    {body}\n",
    )
    changes = compare_tests(BASE, head, ["test_owner_only"])
    assert kinds(changes) == [(TRIVIALIZED, "test_owner_only")]
    assert (changes[0].base_assertions, changes[0].head_assertions) == (2, 0)


def test_asserts_reduced_is_warn_only():
    head = BASE.replace("    assert not can_read(user, other_doc())\n", "")
    changes = compare_tests(BASE, head, ["test_owner_only"])
    assert kinds(changes) == [(ASSERTS_REDUCED, "test_owner_only")]
    assert changes[0].warn_only is True
    assert (changes[0].base_assertions, changes[0].head_assertions) == (2, 1)


def test_more_assertions_is_fine():
    head = BASE.replace("assert is_admin(admin())", "assert is_admin(admin())\n        assert x")
    assert compare_tests(BASE, head, ["TestAdmin::test_admin_only"]) == []


def test_skip_and_trivialized_both_reported():
    head = BASE.replace(
        "class TestAdmin:\n    def test_admin_only(self):\n        assert is_admin(admin())",
        "class TestAdmin:\n    @pytest.mark.skip\n    def test_admin_only(self):\n        pass",
    )
    assert [c.kind for c in compare_tests(BASE, head, ["TestAdmin::test_admin_only"])] == [
        SKIPPED,
        TRIVIALIZED,
    ]


@pytest.mark.parametrize(
    "body, expected",
    [
        ("assert x", 1),
        ("assert x, 'msg'", 1),
        ("assert True", 0),
        ("with pytest.raises(ValueError):\n    f()", 1),
        ("pytest.raises(ValueError, f)", 1),
        ("with pytest.warns(UserWarning):\n    f()", 1),
        ("self.assertEqual(a, b)", 1),
        ("self.assertTrue(a)", 1),
        ("mock.assert_called_once_with(1)", 1),
        ("m.method.assert_not_called()", 1),
        ("assert_valid(doc)", 1),
        ("check_invariants(doc)", 1),
        ("helpers.verify_signature(doc)", 1),
        ("checker(doc)", 0),
        ("def inner():\n    assert x", 0),
        ("for i in items:\n    assert i", 1),
        ("if False:\n    assert x\nelse:\n    assert y", 1),
        ("assert a\nreturn\nassert b", 1),
    ],
)
def test_count_assertions(body, expected):
    source = "def test_x():\n" + textwrap.indent(body, "    ") + "\n"
    func = ast.parse(source).body[0]
    assert count_assertions(func) == expected


def test_unparsable_source_raises():
    with pytest.raises(SourceParseError, match="head"):
        compare_tests(BASE, "def test_owner_only(:\n", ["test_owner_only"])
    with pytest.raises(SourceParseError, match="base"):
        compare_tests("def (", BASE, ["test_owner_only"])
