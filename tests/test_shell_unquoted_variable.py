"""SHELL_UNQUOTED_VARIABLE (rule id ``unquoted-var``) precision tests.

The rule flags a variable expansion left unquoted where word splitting or
globbing is dangerous: ``rm`` arguments, ``cd`` and single-bracket tests.
A quoted expansion such as ``rm -f "$TMPFILE"`` is the fix the rule asks
for, so it must not be reported.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import pytest

from hefesto.analyzers.devops.shell_analyzer import ShellAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType


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
        "docker image rm app/$TAG:latest",
        "git rm $FILE",
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
    ],
)
def test_unquoted_expansion_is_reported(line: str) -> None:
    issues = _unquoted(line)
    assert len(issues) == 1, line
    assert issues[0].rule_id == "unquoted-var"
    assert issues[0].line == 3
