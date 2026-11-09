"""SHELL_UNQUOTED_VARIABLE (rule id ``unquoted-var``) precision tests.

The rule flags a variable expansion left unquoted where word splitting or
globbing is dangerous: ``rm`` arguments, ``cd`` and single-bracket tests.
A quoted expansion such as ``rm -f "$TMPFILE"`` is the fix the rule asks
for, so it must not be reported.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import sys

import pytest

from hefesto.analyzers.devops.shell_analyzer import ShellAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType
from hefesto.core.analyzer_engine import AnalyzerEngine


def _unquoted(line: str):
    code = "#!/bin/bash\nset -euo pipefail\n" + line + "\n"
    issues = ShellAnalyzer().analyze("script.sh", code)
    return [i for i in issues if i.issue_type == AnalysisIssueType.SHELL_UNQUOTED_VARIABLE]


@pytest.mark.parametrize(
    "line",
    [
        'rm -f "$SARIF_FILE"',
        'rm -f "$TMPOUT"',
        'rm -rf "${BUILD_DIR}"',
        'rm -rf "$BUILD_DIR"/cache',
        'rm -f "$DIR/$NAME"',
        "rm -f '$LITERAL'",
        "echo perform $ACTION",
        "docker run --rm $IMAGE",
        "[[ -f $CONFIG ]]",
        '[ -f "$CONFIG" ]',
        'cd "$WORKDIR" && make',
        'echo "next: rm -f $TMPFILE"',
        'rm -f "$OUT" && echo $DONE',
        r"rm -f \$NOT_A_VAR",
        'rm -rf "$(version_path "iojs-${VERSION}")"',
        'rm "$(echo $X)"',
        'rm -f "$(echo $X)"',
        'rm "$(echo "$X")"',
        'rm "$(echo $(cat $F))"',
        'cd "$(echo $X)"',
        'rm -f "$SAFE" # $(echo $X)',
        '/bin/rm -f "$FILE"',
        './rm -f "$FILE"',
        r'\rm -f "$FILE"',
        'case $X in *) rm -f "$FILE" ;; esac',
        'start) rm -f "$PIDFILE" ;;',
        "rm -f file$((N+1))",
        'rm -f "file$((N+1))"',
        'rm "$(echo "a)" $V)"',
        'rm "`cat "$LIST"`"',
        'echo "rm `cat $LIST`"',
        '$HOME/bin/rm -f "$FILE"',
        '${PREFIX}/bin/rm -f "$FILE"',
        'echo "$HOME/bin/rm -f $FILE"',
        "docker image rm app/$TAG:latest",
        "git rm $FILE",
        'a)rm "$f";;',
        'clean)rm -f "$TMPFILE";;',
        "$(echo hi)rm -f $X",
        "$(echo hi) rm -f $X",
        "echo $(echo hi) rm -f $X",
        "\vrm -f $X",
        "\frm -f $X",
        "\rrm -f $X",
        "xargs -0 rm -f $FILE",
        "sudo -u root rm -f $FILE",
        "env A=1 rm -f $FILE",
        "trap 'rm -f $FILE' EXIT",
    ],
)
def test_quoted_or_safe_expansion_is_not_reported(line: str) -> None:
    assert _unquoted(line) == [], line


@pytest.mark.parametrize(
    "line",
    [
        "rm -f $TMPFILE",
        "rm -rf $BUILD_DIR/cache",
        "rm -rf ${BUILD_DIR}",
        'rm -f "$KEEP" $X',
        "sudo rm -rf $DIR",
        "make clean; rm -f $OUT",
        "[ -f $CONFIG ]",
        "cd $WORKDIR && make",
        'rm -rf "$(version_path v1)" $FILE',
        "if true; then rm -f $OUT; fi",
        "[ -e $X ] && rm -R ../$X",
        "(cd $DIR)",
        "if [ -d $DIR ]; then echo ok; fi",
        "if true; then :; elif [ -f $X ]; then :; fi",
        "while [ -e $LOCK ]; do sleep 1; done",
        "until [ -f $READY ]; do sleep 1; done",
        "time rm -rf $CACHE",
        "find . -name x | xargs rm -f $EXTRA",
        "rm $(echo $X)",
        "rm -f $(echo $X)",
        'rm $(echo "$X")',
        "rm $(echo hello)",
        'rm "$KEEP" $(echo $X)',
        "rm $(echo $X) # note",
        "rm $(echo $(cat $F))",
        "cd $(echo $X)",
        "/bin/rm -f $FILE",
        "./rm -f $FILE",
        r"\rm -f $FILE",
        "case $X in *) rm -f $FILE ;; esac",
        "start) rm -f $PIDFILE ;;",
        "case $X in *) rm -f $F ;; esac",
        "sudo /bin/rm -f $FILE",
        "rm `echo $X`",
        'rm `cat "$LIST"`',
        "rm `cat $LIST`",
        "$HOME/bin/rm -f $FILE",
        "${PREFIX}/bin/rm -f $FILE",
        "$HOME/bin/cd $DIR",
        "*)rm -f $X;;",
        "foo)rm -rf $DIR",
        "a)cd $D;;",
        "clean)rm -f $TMPFILE;;",
    ],
)
def test_unquoted_expansion_is_reported(line: str) -> None:
    issues = _unquoted(line)
    assert len(issues) == 1, line
    assert issues[0].rule_id == "unquoted-var"
    assert issues[0].line == 3


@pytest.mark.parametrize(
    "line",
    [
        'if [ -d "$DIR" ]; then echo ok; fi',
        'while [ -e "$LOCK" ]; do sleep 1; done',
        'time rm -rf "$CACHE"',
        'find . -name x | xargs rm -f "$EXTRA"',
        "echo time $X",
    ],
)
def test_keyword_prefix_with_quoted_expansion_is_not_reported(line: str) -> None:
    assert _unquoted(line) == [], line


def test_quote_scan_runs_once_on_a_line_of_many_commands(monkeypatch) -> None:
    calls = {"n": 0}
    orig = ShellAnalyzer._scan_quotes.__get__(None, ShellAnalyzer)

    def wrapped(text):
        calls["n"] += 1
        return orig(text)

    monkeypatch.setattr(ShellAnalyzer, "_scan_quotes", staticmethod(wrapped))
    line = "; ".join(['rm -f "$A"'] * 40)
    ShellAnalyzer()._check_unquoted_vars("script.sh", 1, line)
    assert calls["n"] == 1


def _reported(line: str) -> bool:
    return bool(ShellAnalyzer()._check_unquoted_vars("script.sh", 1, line))


# Space and tab are POSIX blanks. Newline separates commands. Every other
# character for which str.isspace() is true, including vertical tab, form
# feed and carriage return, is not a shell separator.
_POSIX_COMMAND_WHITESPACE = set(" \t\n")


def test_every_python_isspace_is_total_and_only_posix_whitespace_separates() -> None:
    chars = [chr(i) for i in range(sys.maxunicode + 1) if chr(i).isspace()]
    assert _POSIX_COMMAND_WHITESPACE <= set(chars)
    assert {"\v", "\f", "\r"} <= set(chars)
    for char in chars:
        separates = char in _POSIX_COMMAND_WHITESPACE
        assert _reported(f"{char}rm -f $X") is separates
        assert _reported(f"{char}cd $D") is separates
        assert _reported(f'{char}rm -f "$X"') is False
        assert _reported(f'{char}cd "$D"') is False
        assert _reported(f"*){char}rm -f $X") is separates
        assert _reported(f'a){char}rm -f "$F"') is False


def test_every_byte_prefix_is_total() -> None:
    analyzer = ShellAnalyzer()
    for code in range(256):
        char = chr(code)
        for line in (f"{char}rm -f $X", f'{char}rm -f "$X"', f"a{char}cd $D;;"):
            analyzer._check_unquoted_vars("script.sh", 1, line)


_COMMAND_INTRODUCERS = [
    "",
    " ",
    "\t",
    "\n",
    ";",
    "&",
    "|",
    "(",
    ")",
    "*)",
    "foo)",
    "a)",
    "clean)",
    "sudo ",
    "xargs ",
    "time ",
    "*) ",
    "a) ",
]
_NOT_INTRODUCERS = [
    "echo ",
    "git ",
    "docker ",
    "-0 ",
    "\v",
    "\f",
    "\r",
    "\x00",
    "$(echo hi)",
    "echo $(echo hi) ",
]


@pytest.mark.parametrize("prefix", _COMMAND_INTRODUCERS)
@pytest.mark.parametrize(
    ("tail", "expect"),
    [
        ("rm -f $X", True),
        ('rm -f "$X"', False),
        ("cd $D", True),
        ('cd "$D"', False),
    ],
)
def test_command_boundary_grid(prefix: str, tail: str, expect: bool) -> None:
    assert _reported(prefix + tail) is expect


@pytest.mark.parametrize("prefix", _NOT_INTRODUCERS)
@pytest.mark.parametrize(
    "tail",
    ["rm -f $X", 'rm -f "$X"', "cd $D", 'cd "$D"'],
)
def test_non_separator_prefix_is_quiet(prefix: str, tail: str) -> None:
    assert _reported(prefix + tail) is False


def test_bounded_hostile_lines_do_not_raise() -> None:
    lines = [
        "",
        ")",
        "rm",
        "$" * 300,
        "'" * 300 + "rm -f $X",
        '"' * 300 + 'rm -f "$X"',
        ("$(" * 40) + "rm -f $X" + (")" * 40),
        ("`" * 40) + "rm -f $X",
        ")rm -f $X;;" * 40,
        "".join(chr(i) for i in range(128)) + "rm -f $X;;",
        "case " + ("*)" * 30) + "rm -f $X;;",
        "\n".join(["*)rm -f $X;;", 'clean)rm -f "$TMPFILE";;', "\vrm -f $X"]),
    ]
    analyzer = ShellAnalyzer()
    for line in lines:
        analyzer._check_unquoted_vars("script.sh", 1, line)
    analyzer.analyze("script.sh", "#!/bin/bash\nset -euo pipefail\n" + "\n".join(lines) + "\n")


def test_compact_case_script_is_analyzed_end_to_end(tmp_path) -> None:
    script = tmp_path / "clean.sh"
    script.write_text(
        "\n".join(
            [
                "#!/bin/bash",
                "set -euo pipefail",
                "case $X in",
                "*)rm -f $X;;",
                "foo)rm -rf $DIR",
                "a)cd $D;;",
                'a)rm "$f";;',
                'clean)rm -f "$TMPFILE";;',
                "esac",
                "",
            ]
        ),
        encoding="utf-8",
    )
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    report = engine.analyze_path(str(script))
    assert [item.get("exception") for item in engine._not_analyzed] == []
    assert len(report.file_results) == 1
    found = [
        issue
        for result in report.file_results
        for issue in result.issues
        if issue.issue_type == AnalysisIssueType.SHELL_UNQUOTED_VARIABLE
    ]
    assert [issue.line for issue in found] == [4, 5, 6]
    assert [issue.rule_id for issue in found] == ["unquoted-var"] * 3


# One physical line, one finding. A $(...) or backtick body is its own command
# context: quotes around the substitution do not quote the body, and quotes
# inside the body do. Arithmetic $((...)) is not a body. Labels are the shell
# reading used when comparing with main; they are not a second scanner.
COMMAND_CONTEXT_MATRIX = [
    ("x=$(cd $D && pwd)", True, "inner-unquoted"),
    ("DIR=$(cd $DIR && pwd)", True, "inner-unquoted"),
    ("out=$(rm -f $FILE)", True, "inner-unquoted"),
    ("echo $(rm -rf $DIR)", True, "inner-unquoted"),
    ("x=`cd $DIR && pwd`", True, "inner-unquoted"),
    ('x="$(cd $D && pwd)"', True, "inner-unquoted-outer-quoted"),
    ('echo "$(rm -rf $DIR)"', True, "inner-unquoted-outer-quoted"),
    ('echo "`cd $DIR && pwd`"', True, "inner-unquoted-outer-quoted"),
    ('out="$(rm -f $FILE)"', True, "inner-unquoted-outer-quoted"),
    ('rm "$(cd $D && pwd)"', True, "inner-unquoted-outer-quoted"),
    ("x=$(cd $DIR)", True, "inner-unquoted"),
    ("x=$(cd $D&& pwd)", True, "inner-unquoted"),
    ("x=$(cd $(echo $D) && pwd)", True, "inner-unquoted-result"),
    ('x=$(echo "$(rm -f $FILE)")', True, "nested-inner-unquoted"),
    ('x=$(echo "$(cd $DIR && pwd)")', True, "nested-inner-unquoted"),
    ("x=$(/bin/rm -f $FILE)", True, "inner-path"),
    ("x=$(./rm -f $FILE)", True, "inner-path"),
    ("x=$(\\rm -f $FILE)", True, "inner-escaped"),
    ("x=$($HOME/bin/rm -f $FILE)", True, "inner-var-prefix"),
    ("x=$(${PREFIX}/bin/rm -f $FILE)", True, "inner-var-prefix"),
    ("x=$(case $Z in *)rm -f $FILE;; esac)", True, "inner-case-compact"),
    ("x=$(case $Z in *) rm -f $FILE ;; esac)", True, "inner-case-spaced"),
    ("x=$(cd $D && pwd", True, "inner-unquoted-unclosed"),
    ("rm -f $FILE", True, "outer-unquoted"),
    ("rm $(echo $X)", True, "outer-unquoted-result"),
    ('rm $(echo "$X")', True, "outer-unquoted-result"),
    ("sudo rm -f $FILE", True, "outer-prefix"),
    ('x=$(cd "$DIR" && pwd)', False, "quoted-inner"),
    ('out=$(rm -f "$FILE")', False, "quoted-inner"),
    ('x="$(cd "$DIR" && pwd)"', False, "quoted-inner-outer-quoted"),
    ('out="$(rm -f "$FILE")"', False, "quoted-inner-outer-quoted"),
    ('x=`cd "$DIR" && pwd`', False, "quoted-inner"),
    ('echo "$(rm -f "$FILE")"', False, "quoted-inner-outer-quoted"),
    ('x=$(echo "$(rm -f "$FILE")")', False, "nested-quoted-inner"),
    ('x=$(echo "$(cd "$DIR" && pwd)")', False, "nested-quoted-inner"),
    ('x=$(cd "$(echo $D)" && pwd)', False, "quoted-inner-result"),
    ('x=$(/bin/rm -f "$FILE")', False, "quoted-inner"),
    ('x=$($HOME/bin/rm -f "$FILE")', False, "quoted-inner"),
    ("x=$(echo $((N+1)))", False, "arithmetic"),
    ("rm -f file$((N+1))", False, "arithmetic"),
    ("echo '$(cd $DIR && pwd)'", False, "single-quoted-text"),
    ('echo "cd $DIR"', False, "string-not-command"),
    ('echo "rm -f $FILE"', False, "string-not-command"),
    ('echo "\\$(cd $DIR)"', False, "escaped-dollar"),
    ('rm "$(echo $X)"', False, "quoted-result-not-rm"),
    ('cd "$(echo $X)"', False, "quoted-result"),
    ("echo $(echo hi) rm -f $X", False, "glued-not-command"),
    ("$(echo hi)rm -f $X", False, "glued-not-command"),
    ("git rm $FILE", False, "not-command-word"),
    ("xargs -0 rm -f $FILE", False, "unsupported-wrapper"),
    ("sudo -u root rm -f $FILE", False, "unsupported-wrapper"),
    ("env A=1 rm -f $FILE", False, "unsupported-wrapper"),
    ("trap 'rm -f $FILE' EXIT", False, "unsupported-wrapper"),
    ('x=$(cd "$DIR" && pwd) # cd $ELSE', False, "comment"),
    ("# x=$(cd $D && pwd)", False, "comment"),
    ("x=$(cd $D && pwd) # ok", True, "inner-unquoted"),
]


@pytest.mark.parametrize(
    ("line", "expect", "semantics"),
    COMMAND_CONTEXT_MATRIX,
    ids=[row[2] + "-" + str(i) for i, row in enumerate(COMMAND_CONTEXT_MATRIX)],
)
def test_command_context_matrix(line: str, expect: bool, semantics: str) -> None:
    assert bool(_unquoted(line)) is expect, semantics


def test_deep_substitution_nesting_reports_inner_cd() -> None:
    depth = 400
    line = "x=" + ("$(echo " * depth) + "$(cd $D && pwd)" + (")" * depth)
    assert _unquoted(line)


def test_deep_nesting_and_unclosed_text_do_not_raise() -> None:
    _unquoted("$(" * 2000)
    _unquoted("`" * 2000)
    _unquoted("x=" + ("$(echo " * 2000))
    _unquoted("rm -f $FILE" + (")" * 2000))


def test_quote_scan_runs_once_when_a_line_has_many_substitutions(monkeypatch) -> None:
    calls = {"n": 0}
    orig = ShellAnalyzer._scan_quotes.__get__(None, ShellAnalyzer)

    def wrapped(text):
        calls["n"] += 1
        return orig(text)

    monkeypatch.setattr(ShellAnalyzer, "_scan_quotes", staticmethod(wrapped))
    line = "; ".join(['x=$(cd "$D" && pwd)'] * 40)
    ShellAnalyzer()._check_unquoted_vars("script.sh", 1, line)
    assert calls["n"] == 1


def test_repeated_rm_without_a_separator_classifies_each_index_once(monkeypatch) -> None:
    """``(rm `` repeated has no ``$`` and no ``;|&``, so every match used to rescan the suffix."""
    calls = {"n": 0}
    orig = ShellAnalyzer._index_is_expansion

    def wrapped(self, line, index):
        calls["n"] += 1
        return orig(self, line, index)

    monkeypatch.setattr(ShellAnalyzer, "_index_is_expansion", wrapped)
    line = "(rm " * 200
    assert ShellAnalyzer()._check_unquoted_vars("s.sh", 1, line) == []
    assert calls["n"] <= len(line)
