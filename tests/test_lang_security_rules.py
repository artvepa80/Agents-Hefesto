"""C#, Go and Rust security rules (CS001-CS004, GO001-GO004, RS001-RS003)."""

from __future__ import annotations

from typing import List, Tuple

import pytest

pytest.importorskip("tree_sitter_language_pack")


def _rules(language: str, code: str, path: str = "src/app.x") -> List[Tuple[str, int, str]]:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    tree = TreeSitterParser(language).parse(code, path)
    issues = SecurityAnalyzer().analyze(tree, path, code)
    return sorted((i.rule_id, i.line, i.severity.value) for i in issues if i.rule_id)


def _cs(body: str) -> str:
    return "class A {\n void M(string id, string x) {\n" + body + "\n }\n}\n"


def _go(body: str, imports: str = "") -> str:
    return f"package p\n{imports}\nfunc f(d string, a string) {{\n{body}\n}}\n"


def _rs(body: str) -> str:
    return "fn f(d: &str) {\n" + body + "\n}\n"


# --- C# ---------------------------------------------------------------------

CS_CASES = [
    # CS001 SQL built from strings
    ('var c = new SqlCommand("SELECT * FROM u WHERE id=" + id, conn);', [("CS001", 3, "HIGH")]),
    ('var c = new SqlCommand($"DELETE FROM u WHERE id={id}");', [("CS001", 3, "HIGH")]),
    ('cmd.CommandText = "UPDATE u SET a=1 WHERE id=" + id;', [("CS001", 3, "HIGH")]),
    ('ctx.Database.ExecuteSqlRaw(string.Format("DROP TABLE {0}", x));', [("CS001", 3, "HIGH")]),
    ('var c = new SqlCommand("SELECT * FROM u WHERE id=@id", conn);', []),
    ('var c = new SqlCommand("SELECT * FROM u " + "WHERE id=@id", conn);', []),
    ('var c = new SqlCommand($"SELECT * FROM u");', []),
    ("var c = new SqlCommand(query, conn);", []),
    # CS002 dangerous formatters
    ("var f = new BinaryFormatter();", [("CS002", 3, "HIGH")]),
    (
        "var f = new System.Runtime.Serialization.Formatters.Soap.SoapFormatter();",
        [("CS002", 3, "HIGH")],
    ),
    ("var f = new LosFormatter();", [("CS002", 3, "HIGH")]),
    ("var f = new XmlSerializer(typeof(A));", []),
    # CS003 Process.Start with a built string
    ('Process.Start("cmd.exe", "/c del " + x);', [("CS003", 3, "MEDIUM")]),
    ('System.Diagnostics.Process.Start($"/bin/sh -c {x}");', [("CS003", 3, "MEDIUM")]),
    ('var p = new ProcessStartInfo("git", "log " + x);', [("CS003", 3, "MEDIUM")]),
    ('Process.Start("notepad.exe", path);', []),
    ('Process.Start("git", "status");', []),
    # CS004 broken algorithms
    ("var h = MD5.Create();", [("CS004", 3, "MEDIUM")]),
    ("var h = new SHA1CryptoServiceProvider();", [("CS004", 3, "MEDIUM")]),
    ("var d = DES.Create();", [("CS004", 3, "MEDIUM")]),
    ("var h = SHA256.Create();", []),
    ("var h = Aes.Create();", []),
]


@pytest.mark.parametrize("body, expected", CS_CASES)
def test_csharp_rules(body: str, expected) -> None:
    assert _rules("c_sharp", _cs(body)) == expected


# --- Go ---------------------------------------------------------------------

GO_CASES = [
    ('exec.Command("sh", "-c", fmt.Sprintf("ls %s", d))', [("GO001", 4, "HIGH")]),
    ('exec.CommandContext(ctx, "/bin/bash", "-c", "rm -rf "+d)', [("GO001", 4, "HIGH")]),
    ('exec.Command("ls", d)', []),
    ('exec.Command("sh", "-c", "ls -la")', []),
    ('exec.Command("sh", "-c", d)', []),
    ('db.Query("SELECT * FROM t WHERE a=" + a)', [("GO002", 4, "HIGH")]),
    (
        'db.QueryRowContext(ctx, fmt.Sprintf("SELECT * FROM t WHERE a=%s", a))',
        [("GO002", 4, "HIGH")],
    ),
    ('tx.Exec(fmt.Sprintf("DELETE FROM %s", d))', [("GO002", 4, "HIGH")]),
    ('db.Query("SELECT * FROM t WHERE a=$1", a)', []),
    ('r.Exec(fmt.Sprintf("hello %s", d))', []),
    ("_ = tls.Config{InsecureSkipVerify: true}", [("GO004", 4, "HIGH")]),
    ("_ = tls.Config{InsecureSkipVerify: false}", []),
    ("_ = tls.Config{InsecureSkipVerify: cfg.Insecure}", []),
]


@pytest.mark.parametrize("body, expected", GO_CASES)
def test_go_rules(body: str, expected) -> None:
    assert _rules("go", _go(body)) == expected


def test_go_weak_hash_only_from_crypto_packages() -> None:
    imports = 'import (\n\t"crypto/md5"\n\t"crypto/sha1"\n)\n'
    code = _go("_ = md5.Sum([]byte(d))\n_ = sha1.New()", imports)
    assert _rules("go", code) == [("GO003", 8, "MEDIUM"), ("GO003", 9, "MEDIUM")]
    # A local package that happens to be called md5 is not crypto/md5.
    assert _rules("go", _go("_ = md5.Sum([]byte(d))", 'import "example.com/md5"\n')) == []


def test_go_rules_skip_test_files() -> None:
    code = _go("_ = tls.Config{InsecureSkipVerify: true}")
    assert _rules("go", code, path="pkg/client_test.go") == []


# --- Rust -------------------------------------------------------------------

RS_CASES = [
    ("unsafe { do_it(); }", [("RS001", 2, "LOW")]),
    (
        "let x: u32 = unsafe { std::mem::transmute(y) };",
        [("RS001", 2, "LOW"), ("RS002", 2, "MEDIUM")],
    ),
    (
        "let x = unsafe { mem::transmute::<f32, u32>(y) };",
        [("RS001", 2, "LOW"), ("RS002", 2, "MEDIUM")],
    ),
    (
        'Command::new("sh").arg("-c").arg(format!("ls {}", d)).output();',
        [("RS003", 2, "HIGH")],
    ),
    ('Command::new("bash").args(["-c", &format!("ls {}", d)]).status();', [("RS003", 2, "HIGH")]),
    ('Command::new("ls").arg(format!("{}", d)).output();', []),
    ('Command::new("sh").arg("-c").arg("ls -la").output();', []),
    ('let s = "unsafe { }";', []),
]


@pytest.mark.parametrize("body, expected", RS_CASES)
def test_rust_rules(body: str, expected) -> None:
    assert _rules("rust", _rs(body)) == expected


def test_rust_unsafe_fn_is_inventoried() -> None:
    assert _rules("rust", "unsafe fn raw() {}\n") == [("RS001", 1, "LOW")]


def test_rule_issue_types_and_cwe() -> None:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _cs("var f = new BinaryFormatter();\nvar h = MD5.Create();")
    tree = TreeSitterParser("c_sharp").parse(code, "a.cs")
    got = {
        i.rule_id: (i.issue_type.value, i.metadata.get("cwe"))
        for i in SecurityAnalyzer().analyze(tree, "a.cs", code)
    }
    assert got == {
        "CS002": ("INSECURE_DESERIALIZATION", "CWE-502"),
        "CS004": ("INSECURE_CRYPTOGRAPHY", "CWE-327"),
    }


def test_rule_replaces_the_generic_finding_on_the_same_line() -> None:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _go('db.Query("SELECT * FROM t WHERE a=" + a)')
    tree = TreeSitterParser("go").parse(code, "a.go")
    sql = [
        i
        for i in SecurityAnalyzer().analyze(tree, "a.go", code)
        if i.issue_type.value == "SQL_INJECTION_RISK"
    ]
    assert [(i.rule_id, i.line) for i in sql] == [("GO002", 4)]


def test_strings_and_comments_never_match() -> None:
    code = _go('_ = "InsecureSkipVerify: true"\n// exec.Command("sh", "-c", fmt.Sprintf("%s", d))')
    assert _rules("go", code) == []
    code = _cs('var s = "new BinaryFormatter()";\n// MD5.Create();')
    assert _rules("c_sharp", code) == []
