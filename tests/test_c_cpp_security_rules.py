"""C and C++ security rules (CC001-CC004)."""

from __future__ import annotations

from typing import List, Tuple

import pytest

pytest.importorskip("tree_sitter_language_pack")


def _rules(language: str, code: str, path: str = "src/app.c") -> List[Tuple[str, int, str]]:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    analyzer = SecurityAnalyzer()
    analyzer.lang_rules = True
    tree = TreeSitterParser(language).parse(code, path)
    issues = analyzer.analyze(tree, path, code)
    return sorted((i.rule_id, i.line, i.severity.value) for i in issues if i.rule_id)


def _c(body: str) -> str:
    return "void f(char *d, const char *s, int n) {\n" + body + "\n}\n"


C_CASES = [
    # CC001 gets
    ("char b[8]; gets(b);", [("CC001", 2, "HIGH")]),
    # CC002 unbounded copy / write
    ("strcpy(d, s);", [("CC002", 2, "MEDIUM")]),
    ("strcat(d, s);", [("CC002", 2, "MEDIUM")]),
    ('sprintf(d, "%s/x", s);', [("CC002", 2, "MEDIUM")]),
    ('scanf("%s", d);', [("CC002", 2, "MEDIUM")]),
    ('sscanf(s, "%d %s", &n, d);', [("CC002", 2, "MEDIUM")]),
    # bounded or literal forms are not reported
    ('strcpy(d, "abc");', []),
    ('sprintf(d, "%d", n);', []),
    ('sprintf(d, "%.8s", s);', []),
    ('sprintf(d, "%8s", s);', [("CC002", 2, "MEDIUM")]),
    ('scanf("%7s", d);', []),
    ('snprintf(d, 8, "%s", s);', []),
    ("strncpy(d, s, 8);", []),
    # CC003 format string that is not a literal
    ("printf(s);", [("CC003", 2, "MEDIUM")]),
    ("fprintf(stderr, s);", [("CC003", 2, "MEDIUM")]),
    ("snprintf(d, 8, s);", [("CC003", 2, "MEDIUM")]),
    ("syslog(3, s);", [("CC003", 2, "MEDIUM")]),
    ('printf("%s", s);', []),
    ('printf("a" "b");', []),
    ("printf(MSG_FMT);", []),
    # CC004 command built at runtime
    ("system(s);", [("CC004", 2, "HIGH")]),
    ('popen(s, "r");', [("CC004", 2, "HIGH")]),
    ('system("ls -l");', []),
    ('popen("date", "r");', []),
    # comments and strings never match
    ('/* gets(b); strcpy(d, s); */ const char *t = "system(s)";', []),
]


@pytest.mark.parametrize("body,expected", C_CASES)
def test_c_rules(body: str, expected) -> None:
    assert _rules("c", _c(body)) == expected


CPP_CASES = [
    ("std::system(s);", [("CC004", 2, "HIGH")]),
    ("::strcpy(d, s);", [("CC002", 2, "MEDIUM")]),
    ("std::printf(s);", [("CC003", 2, "MEDIUM")]),
    ("obj.system(s);", []),
    ("std::string t(s); std::cout << t;", []),
]


@pytest.mark.parametrize("body,expected", CPP_CASES)
def test_cpp_rules(body: str, expected) -> None:
    assert _rules("cpp", _c(body), "src/app.cpp") == expected


def test_test_paths_are_skipped() -> None:
    assert _rules("c", _c("gets(d);"), "tests/t.c") == []


def test_off_by_default() -> None:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _c("gets(d); system(s);")
    tree = TreeSitterParser("c").parse(code, "src/a.c")
    issues = SecurityAnalyzer().analyze(tree, "src/a.c", code)
    assert not [i for i in issues if (i.rule_id or "").startswith("CC")]


def test_cwe_and_types() -> None:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _c("gets(d); strcpy(d, s); printf(s); system(s);")
    analyzer = SecurityAnalyzer()
    analyzer.lang_rules = True
    tree = TreeSitterParser("c").parse(code, "src/a.c")
    got = {
        i.rule_id: (i.issue_type.value, i.metadata.get("cwe"))
        for i in analyzer.analyze(tree, "src/a.c", code)
        if i.rule_id
    }
    assert got == {
        "CC001": ("UNSAFE_BUFFER_FUNCTION", "CWE-242"),
        "CC002": ("UNSAFE_BUFFER_FUNCTION", "CWE-120"),
        "CC003": ("FORMAT_STRING_RISK", "CWE-134"),
        "CC004": ("COMMAND_INJECTION", "CWE-78"),
    }


def test_system_line_is_reported_once() -> None:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _c('char c[64]; sprintf(c, "rm %s", s); system(c);')
    analyzer = SecurityAnalyzer()
    analyzer.lang_rules = True
    tree = TreeSitterParser("c").parse(code, "src/a.c")
    cmd = [
        i
        for i in analyzer.analyze(tree, "src/a.c", code)
        if i.issue_type.value == "COMMAND_INJECTION"
    ]
    assert len(cmd) == 1 and cmd[0].rule_id == "CC004"
