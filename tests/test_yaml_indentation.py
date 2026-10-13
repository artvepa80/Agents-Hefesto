"""YAML_INDENTATION judges the step between nesting levels, not how many widths exist.

A normal GitHub workflow nests 2/4/6/8/10 spaces deep with a consistent 2-space
step; the old check flagged any file with more than 3 distinct widths
("Inconsistent indentation (5 levels)"). Block scalar content (`run: |`, `>-`,
`|2`, heredocs) is free text and must not count.
"""

from pathlib import Path

import pytest

from hefesto.analyzers.devops.yaml_analyzer import YamlAnalyzer

FIXTURES = Path(__file__).parent / "fixtures" / "yaml_indentation"


def _indent_issues(name, content):
    return [
        i for i in YamlAnalyzer().analyze(name, content) if i.issue_type.value == "YAML_INDENTATION"
    ]


def test_normal_workflow_with_block_scalars_is_not_flagged():
    path = FIXTURES / "workflow_ok.yml"
    assert _indent_issues(str(path), path.read_text()) == []


def test_mixed_two_and_four_space_steps_are_flagged():
    path = FIXTURES / "mixed.yml"
    issues = _indent_issues(str(path), path.read_text())
    assert len(issues) == 1
    issue = issues[0]
    assert issue.line == 4  # first line whose step differs from the usual 2
    assert "2" in issue.message and "4" in issue.message
    assert "levels" not in issue.message


def test_consistent_four_space_file_is_not_flagged():
    content = "a:\n    b:\n        c:\n            d:\n                e: 1\n"
    assert _indent_issues("x.yml", content) == []


@pytest.mark.parametrize("indicator", ["|", ">", "|-", ">+", "|2", ">-", "|+"])
def test_block_scalar_content_is_skipped(indicator):
    content = f"a:\n  b: {indicator}\n       odd text\n     more\n  c: 1\n"
    assert _indent_issues("x.yml", content) == []


def test_list_item_block_scalar_is_skipped():
    content = "steps:\n  - run: |\n         x\n      y\n  - run: echo\n"
    assert _indent_issues("x.yml", content) == []


def test_deep_nesting_alone_is_not_flagged():
    content = "".join(f"{'  ' * i}k{i}:\n" for i in range(8)) + f"{'  ' * 8}v: 1\n"
    assert _indent_issues("x.yml", content) == []


def test_multi_line_scalar_continuation_is_not_a_step():
    content = (
        "with:\n"
        "  install: autoconf automake\n"
        "           gettext texinfo\n"
        '  template: "a long \\\n'
        '    value"\n'
        "  next: 1\n"
    )
    assert _indent_issues("x.yml", content) == []


def test_compact_list_items_measure_from_the_item_content():
    content = (
        "mappings:\n"
        "- body:\n"
        "    mappings:\n"
        "    - accountId:\n"
        "        required: true\n"
        "    - currency:\n"
        "        required: true\n"
    )
    assert _indent_issues("x.yml", content) == []
