"""yaml-test-suite cases where CSafeLoader and SafeLoader disagree.

16 documents are accepted only by libyaml. 10 are accepted only by
SafeLoader. Ids are the suite directory names (``ID/NN`` is a subtest).
A tab, a line starting with ``%``, or ``[|>][0-9+-]*#`` routes the file
to SafeLoader. JR7V and WZ62 match none of those, so libyaml keeps them
and the syntax finding from 4.20.1 goes away. X4QW (``block: ># comment``)
is the block-scalar rule.
"""

import pytest
import yaml

from hefesto.core.config_parse import load_yaml, parse_scope

_HAS_C = getattr(yaml, "CSafeLoader", None) is not None
# Valid documents libyaml accepts and SafeLoader rejects, with no marker.
_RESIDUAL = {"JR7V", "WZ62"}


def _accepts(content, loader):
    try:
        list(yaml.load_all(content, Loader=loader))
    except Exception:
        return False
    return True


def _flagged(content):
    with parse_scope():
        return load_yaml(content).error is not None


LIBYAML_ONLY = [
    # Spec Example 6.1. Indentation Spaces
    (
        "6HB6",
        "  # Leading comment line spaces are\n"
        "   # neither content nor indentation.\n"
        "    \n"
        "Not indented:\n"
        " By one space: |\n"
        "    By four\n"
        "      spaces\n"
        " Flow style: [    # Leading spaces\n"
        "   By two,        # in flow style\n"
        "  Also by two,    # are neither\n"
        "  \tStill by two   # content nor\n"
        "    ]             # indentation.\n",
    ),
    # Various trailing tabs
    ("DC7X", "a: b\t\nseq:\t\n - a\t\nc: d\t#X\n"),
    # Tabs that look like indentation
    ("DK95/05", "foo: 1\n \t\nbar: 2\n"),
    # Tabs that look like indentation
    ("DK95/07", "%YAML 1.2\n\t\n---\n"),
    # Spec Example 7.12. Plain Lines
    ("HS5T", "1st non-empty\n\n 2nd non-empty \n\t3rd non-empty\n"),
    # Spec Example 5.12. Tabs and Spaces
    (
        "J3BT",
        "# Tabs and spaces\n"
        'quoted: "Quoted \t"\n'
        "block:\t|\n"
        "  void main() {\n"
        '  \tprintf("Hello, world!\\n");\n'
        "  }\n",
    ),
    # Question marks in scalars
    (
        "JR7V",
        "- a?string\n"
        "- another ? string\n"
        "- key: value?\n"
        "- [a?string]\n"
        "- [another ? string]\n"
        "- {key: value? }\n"
        "- {key: value?}\n"
        "- {key?: value }\n",
    ),
    # Tab after document header
    ("K54U", "---\tscalar\n"),
    # Directive variants
    ("MUS6/00", "%YAML 1.1#...\n---\n"),
    # Directive variants
    ("MUS6/03", "%YAML \t 1.1\n---\n"),
    # Multiline plain value with tabs on empty lines
    ("NB6Z", "key:\n  value\n  with\n  \t\n  tabs\n"),
    # Legal tab after indentation
    ("UV7Q", "x:\n - x\n  \tx\n"),
    # Spec Example 7.2. Empty Content
    ("WZ62", "{\n  foo : !!str,\n  !!str : bar,\n}\n"),
    # Comment without whitespace after block scalar indicator
    ("X4QW", "block: ># comment\n  scalar\n"),
    # Tabs in various contexts
    ("Y79Y/002", "- [\n\t\n foo\n ]\n"),
    # Tabs in various contexts
    ("Y79Y/003", "- [\n\tfoo,\n foo\n ]\n"),
]

SAFE_ONLY = [
    # Spec Example 6.13. Reserved Directives [1.3]
    ("2LFX", '%FOO  bar baz # Should be ignored\n              # with a warning.\n---\n"foo"\n'),
    # Flow Mapping Separate Values
    ("4ABK", '{\nunquoted : "separate",\nhttp://foo.com,\nomitted value:,\n}\n'),
    # Spec Example 6.13. Reserved Directives
    ("6LVF", '%FOO  bar baz # Should be ignored\n              # with a warning.\n--- "foo"\n'),
    # Leading tab content in literals
    ("96NN/00", "foo: |-\n \tbar\n"),
    # Leading tab content in literals
    ("96NN/01", "foo: |-\n \tbar"),
    # Spec Example 6.14. “YAML” directive
    ("BEC7", '%YAML 1.3 # Attempt parsing\n          # with a warning\n---\n"foo"\n'),
    # Directive variants
    ("MUS6/05", "%YAM 1.1\n---\n"),
    # Directive variants
    ("MUS6/06", "%YAMLL 1.1\n---\n"),
    # Spec Example 8.2. Block Indentation Indicator
    ("R4YG", "- |\n detected\n- >\n \n  \n  # detected\n- |1\n  explicit\n- >\n \t\n detected\n"),
    # Tabs in various contexts
    ("Y79Y/001", "foo: |\n \t\nbar: 1\n"),
]


@pytest.mark.parametrize("suite_id, content", LIBYAML_ONLY, ids=[item[0] for item in LIBYAML_ONLY])
def test_libyaml_only_suite_case(suite_id, content):
    """SafeLoader rejects these. Markers route them back, except JR7V and WZ62."""
    assert _accepts(content, yaml.SafeLoader) is False
    if _HAS_C:
        assert _accepts(content, yaml.CSafeLoader) is True
        assert _flagged(content) is (suite_id not in _RESIDUAL)
    else:
        assert _flagged(content) is True


@pytest.mark.parametrize("suite_id, content", SAFE_ONLY, ids=[item[0] for item in SAFE_ONLY])
def test_safeloader_only_suite_case(suite_id, content):
    """SafeLoader accepts these. A C rejection is reparsed and not flagged."""
    assert _accepts(content, yaml.SafeLoader) is True
    if _HAS_C:
        assert _accepts(content, yaml.CSafeLoader) is False
    assert _flagged(content) is False
