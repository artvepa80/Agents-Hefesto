"""C#, Go and Rust security rules (CS001-CS004, GO001-GO004, RS001-RS003)."""

from __future__ import annotations

from typing import List, Tuple

import pytest

pytest.importorskip("tree_sitter_language_pack")


def _analyzer():
    """A SecurityAnalyzer with ``--experimental lang-security`` on."""
    from hefesto.analyzers.security import SecurityAnalyzer

    analyzer = SecurityAnalyzer()
    analyzer.lang_rules = True
    return analyzer


def _rules(language: str, code: str, path: str = "src/app.x") -> List[Tuple[str, int, str]]:
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    tree = TreeSitterParser(language).parse(code, path)
    issues = _analyzer().analyze(tree, path, code)
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
    # MD5 and SHA-1 are an inventory (LOW); broken ciphers stay MEDIUM.
    ("var h = MD5.Create();", [("CS004", 3, "LOW")]),
    ("var h = SHA1.HashData(b);", [("CS004", 3, "LOW")]),
    ("var h = new SHA1CryptoServiceProvider();", [("CS004", 3, "LOW")]),
    ("var d = DES.Create();", [("CS004", 3, "MEDIUM")]),
    ("var d = TripleDES.Create();", [("CS004", 3, "MEDIUM")]),
    ("var d = new RC2CryptoServiceProvider();", [("CS004", 3, "MEDIUM")]),
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
    # GO002 was dropped from v1 (57/57 non-actionable on the measured corpus).
    ('db.Query("SELECT * FROM t WHERE a=" + a)', []),
    ('db.QueryRowContext(ctx, fmt.Sprintf("SELECT * FROM t WHERE a=%s", a))', []),
    ('tx.Exec(fmt.Sprintf("DELETE FROM %s", d))', []),
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
    assert _rules("go", code) == [("GO003", 8, "LOW"), ("GO003", 9, "LOW")]
    # A local package that happens to be called md5 is not crypto/md5.
    assert _rules("go", _go("_ = md5.Sum([]byte(d))", 'import "example.com/md5"\n')) == []


def test_go_rules_skip_test_files() -> None:
    code = _go("_ = tls.Config{InsecureSkipVerify: true}")
    assert _rules("go", code, path="pkg/client_test.go") == []


# Same-function assignments. The line numbers are the call, not the build.
GO_FLOW = [
    (
        _go('command := fmt.Sprintf("ls %s", d)\nexec.Command("sh", "-c", command)'),
        [("GO001", 5, "HIGH")],
    ),
    (
        _go('command := "rm " + d\nexec.Command("sh", "-c", command)'),
        [("GO001", 5, "HIGH")],
    ),
    (
        _go('command := "ls "\ncommand += d\nexec.Command("sh", "-c", command)'),
        [("GO001", 6, "HIGH")],
    ),
    (
        _go('command := fmt.Sprintf("ls %s", d)\nexec.CommandContext(d, "sh", "-c", command)'),
        [("GO001", 5, "HIGH")],
    ),
    (
        _go(
            'command := fmt.Sprintf("ls %s", d)\nalias := command\nexec.Command("sh", "-c", alias)'
        ),
        [("GO001", 6, "HIGH")],
    ),
    (
        _go('exec.Command("sh", "-c", ("rm " + d))'),
        [("GO001", 4, "HIGH")],
    ),
    (
        _go('exec.Command("sh", "-c", fmt.Sprintf("ls %d", a))'),
        [("GO001", 4, "HIGH")],
    ),
    (
        _go(
            'command := "ls -la"\n'
            'command = fmt.Sprintf("ls %s", d)\n'
            'exec.Command("sh", "-c", command)'
        ),
        [("GO001", 6, "HIGH")],
    ),
    (
        _go(
            "var command string\n"
            'if d != "" {\n'
            'command = fmt.Sprintf("ls %s", d)\n'
            "} else {\n"
            'command = "ls -la"\n'
            "}\n"
            'exec.Command("sh", "-c", command)'
        ),
        [("GO001", 10, "HIGH")],
    ),
    (
        _go(
            'command := "ls -la"\n'
            'if d != "" {\n'
            'command = fmt.Sprintf("ls %s", d)\n'
            "} else {\n"
            'command = "ls"\n'
            "}\n"
            'exec.Command("sh", "-c", command)'
        ),
        [("GO001", 10, "HIGH")],
    ),
    (
        _go(
            'command := fmt.Sprintf("ls %s", d)\n'
            'if d == "" {\n'
            'command = "ls"\n'
            "}\n"
            'exec.Command("sh", "-c", command)'
        ),
        [("GO001", 8, "HIGH")],
    ),
    (
        _go(
            'command := fmt.Sprintf("ls %s", d)\n'
            "{\n"
            'command := "ls -la"\n'
            'exec.Command("sh", "-c", command)\n'
            "}\n"
            'exec.Command("sh", "-c", command)'
        ),
        [("GO001", 9, "HIGH")],
    ),
    (
        _go(
            "go func() {\n"
            'command := fmt.Sprintf("ls %s", d)\n'
            'exec.Command("sh", "-c", command)\n'
            "}()"
        ),
        [("GO001", 6, "HIGH")],
    ),
    (
        _go(
            'if command := fmt.Sprintf("ls %s", d); command != "" {\n'
            'exec.Command("sh", "-c", command)\n'
            "}"
        ),
        [("GO001", 5, "HIGH")],
    ),
    (
        _go(
            "var command string\n"
            "switch d {\n"
            'case "a":\n'
            'command = fmt.Sprintf("ls %s", d)\n'
            "default:\n"
            'command = "ls"\n'
            "}\n"
            'exec.Command("sh", "-c", command)'
        ),
        [("GO001", 11, "HIGH")],
    ),
    # Negatives: literal, last write is a literal, parameter, const sprintf.
    (_go('command := "ls -la"\nexec.Command("sh", "-c", command)'), []),
    (
        _go(
            'command := fmt.Sprintf("ls %s", d)\n'
            'command = "ls -la"\n'
            'exec.Command("sh", "-c", command)'
        ),
        [],
    ),
    (
        _go(
            'command := fmt.Sprintf("ls %s", d)\n'
            'if d != "" {\n'
            'command = "ls"\n'
            "} else {\n"
            'command = "ls -la"\n'
            "}\n"
            'exec.Command("sh", "-c", command)'
        ),
        [],
    ),
    (
        _go(
            "var command string\n"
            'if d != "" {\n'
            'command = fmt.Sprintf("ls %s", d)\n'
            "} else {\n"
            'command = "ls"\n'
            "}\n"
            'command = "ls -la"\n'
            'exec.Command("sh", "-c", command)'
        ),
        [],
    ),
    (_go('exec.Command("sh", "-c", fmt.Sprintf("ls %s", "tmp"))'), []),
    (_go('const command = "ls -la"\nexec.Command("sh", "-c", command)'), []),
]


@pytest.mark.parametrize("code, expected", GO_FLOW)
def test_go_command_follows_same_function_assignments(code: str, expected) -> None:
    assert _rules("go", code) == expected


def test_go_command_parameter_is_not_tracked() -> None:
    code = 'package p\n\nfunc f(command string) {\nexec.Command("sh", "-c", command)\n}\n'
    assert _rules("go", code) == []


def test_go_command_from_another_function_is_not_tracked() -> None:
    code = (
        "package p\n\n"
        "func helper(d string) string {\n"
        'return fmt.Sprintf("ls %s", d)\n'
        "}\n\n"
        "func f(d string) {\n"
        "command := helper(d)\n"
        'exec.Command("sh", "-c", command)\n'
        "}\n"
    )
    assert _rules("go", code) == []


def test_go_command_closure_does_not_see_outer_build() -> None:
    code = _go(
        'command := fmt.Sprintf("ls %s", d)\n'
        "go func() {\n"
        'exec.Command("sh", "-c", command)\n'
        "}()"
    )
    assert _rules("go", code) == []


def test_go_command_flow_skips_test_files() -> None:
    code = _go('command := fmt.Sprintf("ls %s", d)\nexec.Command("sh", "-c", command)')
    assert _rules("go", code, path="pkg/f_test.go") == []


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
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _cs("var f = new BinaryFormatter();\nvar h = MD5.Create();")
    tree = TreeSitterParser("c_sharp").parse(code, "a.cs")
    got = {
        i.rule_id: (i.issue_type.value, i.metadata.get("cwe"))
        for i in _analyzer().analyze(tree, "a.cs", code)
    }
    assert got == {
        "CS002": ("INSECURE_DESERIALIZATION", "CWE-502"),
        "CS004": ("INSECURE_CRYPTOGRAPHY", "CWE-327"),
    }


def test_go_broken_ciphers_stay_medium() -> None:
    imports = 'import (\n\t"crypto/des"\n\t"crypto/rc4"\n)\n'
    code = _go("_, _ = des.NewTripleDESCipher(k)\n_, _ = rc4.NewCipher(k)", imports)
    assert _rules("go", code) == [("GO003", 8, "MEDIUM"), ("GO003", 9, "MEDIUM")]


def test_weak_hash_message_says_inventory() -> None:
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _cs("var h = MD5.Create();")
    tree = TreeSitterParser("c_sharp").parse(code, "a.cs")
    msgs = [i.message for i in _analyzer().analyze(tree, "a.cs", code) if i.rule_id]
    assert len(msgs) == 1 and "(inventory)" in msgs[0]


def test_go_sql_has_no_rule_finding() -> None:
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _go('db.Query("SELECT * FROM t WHERE a=" + a)')
    tree = TreeSitterParser("go").parse(code, "a.go")
    assert [i.rule_id for i in _analyzer().analyze(tree, "a.go", code) if i.rule_id] == []


def test_strings_and_comments_never_match() -> None:
    code = _go('_ = "InsecureSkipVerify: true"\n// exec.Command("sh", "-c", fmt.Sprintf("%s", d))')
    assert _rules("go", code) == []
    code = _cs('var s = "new BinaryFormatter()";\n// MD5.Create();')
    assert _rules("c_sharp", code) == []


def test_both_deserialization_types_carry_cwe_502_in_sarif(tmp_path) -> None:
    """INSECURE_DESERIALIZATION (C#) and PICKLE_USAGE (Python) are both CWE-502 in SARIF."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "A.cs").write_text("class A { void F() { var f = new BinaryFormatter(); } }\n")
    (tmp_path / "b.py").write_text("import pickle\n")
    out = subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", str(tmp_path)]
        + ["--output", "sarif", "--severity", "LOW", "--quiet", "--experimental", "lang-security"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    ).stdout
    rules = json.loads(out)["runs"][0]["tool"]["driver"]["rules"]
    tags = {r["id"]: r["properties"]["tags"] for r in rules}
    assert "external/cwe/cwe-502" in tags["CS002"]
    assert "external/cwe/cwe-502" in tags["PICKLE_USAGE"]
