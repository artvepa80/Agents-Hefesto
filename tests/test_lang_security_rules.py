"""C#, Go and Rust security rules (CS001-CS004, GO001-GO005, RS001-RS003)."""

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
    # A value inserted into DML is GO005. Identifier-only text, placeholders and
    # non-SQL text are not. GO002 stays retired.
    ('db.Query("SELECT * FROM t WHERE a=" + a)', [("GO005", 4, "HIGH")]),
    (
        'db.QueryRowContext(ctx, fmt.Sprintf("SELECT * FROM t WHERE a=%s", a))',
        [("GO005", 4, "HIGH")],
    ),
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


_GO005 = [("GO005", 4, "HIGH")]

# Synthetic shapes. Not copies of the measured repositories.
GO_SQL = [
    (
        _go("q := fmt.Sprintf(`SELECT id FROM t WHERE id=%s`, a)\nDB.Query(q)"),
        [("GO005", 5, "HIGH")],
    ),
    (
        _go("query := fmt.Sprintf(\"SELECT '%s' AS '%s'\", a, \"col\")\nsi.db.Exec(query)"),
        [("GO005", 5, "HIGH")],
    ),
    (
        _go("query := fmt.Sprintf(\"SELECT name FROM t WHERE name = '%s'\", a)\ns.db.Query(query)"),
        [("GO005", 5, "HIGH")],
    ),
    (
        _go('q := "SELECT id FROM t WHERE id="\nq += a\ndb.Query(q)'),
        [("GO005", 6, "HIGH")],
    ),
    (
        _go("q := fmt.Sprintf(\"UPDATE t SET name='%s'\", a)\ntx.Exec(q)"),
        [("GO005", 5, "HIGH")],
    ),
    (
        _go('q := fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\ndb.QueryRowContext(d, q)'),
        [("GO005", 5, "HIGH")],
    ),
    (
        _go('q := fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\ndb.Raw(q)'),
        [("GO005", 5, "HIGH")],
    ),
    (
        _go("q := fmt.Sprintf(\"UPDATE t SET name='%s'\", a)\ndb.Exec(q)"),
        [("GO005", 5, "HIGH")],
    ),
    (_go('db.Prepare(fmt.Sprintf("SELECT id FROM t WHERE id=%s", a))'), _GO005),
    (_go('db.Queryx(fmt.Sprintf("SELECT id FROM t WHERE id=%s", a))'), _GO005),
    (_go("db.MustExec(fmt.Sprintf(\"INSERT INTO t VALUES ('%s')\", a))"), _GO005),
    (_go('db.Exec(fmt.Sprintf("INSERT INTO t VALUES (%s)", a))'), _GO005),
    (_go('db.Query(fmt.Sprintf("SELECT id FROM t WHERE n>%s", a))'), _GO005),
    (_go('db.Query(fmt.Sprintf("select id from t where id=%s", a))'), _GO005),
    (_go('db.Query(fmt.Sprintf("SELECT id FROM t WHERE id=%q", a))'), _GO005),
    (
        _go("db.Query(fmt.Sprintf(\"SELECT id FROM t WHERE id='%s' AND note='use $1'\", a))"),
        _GO005,
    ),
    (
        _go("db.Query(fmt.Sprintf(\"SELECT id FROM t WHERE note='IN (' AND id='%s'\", a))"),
        _GO005,
    ),
    (
        _go(
            "q := fmt.Sprintf(\"SELECT id FROM t WHERE id IN (%s) AND name='%s'\", a, d)\n"
            "db.Query(q)"
        ),
        [("GO005", 5, "HIGH")],
    ),
    (
        _go(
            "var q string\n"
            'if d != "" {\n'
            'q = fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\n'
            "} else {\n"
            'q = "SELECT 1"\n'
            "}\n"
            "db.Query(q)"
        ),
        [("GO005", 10, "HIGH")],
    ),
    (
        _go(
            'q := fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\n'
            "{\n"
            'q := "SELECT 1"\n'
            "db.Query(q)\n"
            "}\n"
            "db.Query(q)"
        ),
        [("GO005", 9, "HIGH")],
    ),
    (
        _go(
            "go func() {\n"
            'q := fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\n'
            "db.Query(q)\n"
            "}()"
        ),
        [("GO005", 6, "HIGH")],
    ),
    (
        _go(
            'q := fmt.Sprintf("SELECT id FROM %s WHERE id=%s", pq.QuoteIdentifier(a), d)\n'
            "db.Query(q)"
        ),
        [("GO005", 5, "HIGH")],
    ),
    # Placeholders, numeric verbs, DDL, maintenance, consts.
    (_go("db.Query(fmt.Sprintf(\"SELECT id FROM t WHERE id=? AND name='%s'\", a))"), []),
    (
        _go("q := fmt.Sprintf(\"SELECT id FROM t WHERE id=$1 AND name='%s'\", a)\ndb.Query(q)"),
        [],
    ),
    (_go('q := "SELECT id FROM t WHERE id=@name AND name=\'" + a\ndb.Query(q)'), []),
    (_go('db.Exec(fmt.Sprintf("UPDATE t SET n=%d", a))'), []),
    (_go('db.Exec(fmt.Sprintf("SELECT %t", a))'), []),
    (_go('db.Exec(fmt.Sprintf("SELECT %f", a))'), []),
    (_go('db.Exec(fmt.Sprintf("SELECT %x", a))'), []),
    (_go('db.Query(fmt.Sprintf("SELECT id FROM t WHERE id=%v", a))'), []),
    (_go('db.Exec(fmt.Sprintf("CREATE TABLE %s (id int)", a))'), []),
    (_go('db.Exec(fmt.Sprintf("ALTER TABLE %s ADD name text", a))'), []),
    (_go('db.Exec(fmt.Sprintf("DROP TABLE %s", a))'), []),
    (_go('db.Exec(fmt.Sprintf("TRUNCATE %s", a))'), []),
    (_go('db.Exec("CREATE TABLE users (id int)")'), []),
    (_go("db.Exec(fmt.Sprintf(\"SELECT setval('%s', 1)\", a))"), []),
    (_go('db.Exec(fmt.Sprintf("PRAGMA table_info(%s)", a))'), []),
    (_go('db.Exec(fmt.Sprintf("VACUUM %s", a))'), []),
    (_go('const q = "SELECT id FROM t"\ndb.Query(q)'), []),
    (_go('db.Query("SELECT id FROM t WHERE id=1")'), []),
    (_go('db.Query(fmt.Sprintf("SELECT id FROM t WHERE id=%s", "1"))'), []),
    (_go('db.Prepare("SELECT id FROM t WHERE id=?")'), []),
    # IN lists, QuoteIdentifier, other clients, keyword not at the start.
    (
        _go('q := "SELECT id FROM t WHERE id IN ("\nq += a\nq += ")"\ndb.Query(q)'),
        [],
    ),
    (_go('db.Query(fmt.Sprintf("SELECT id FROM t WHERE id IN (%s)", a))'), []),
    (_go("db.Query(fmt.Sprintf(\"SELECT id FROM t WHERE id IN ('%s')\", a))"), []),
    (_go('q := "SELECT id FROM t WHERE id IN (" + a\ndb.Query(q)'), []),
    (_go('q := "SELECT id FROM t WHERE id IN (" + a\ndb.Query(sqlx.In(q, a))'), []),
    (
        _go(
            "q := fmt.Sprintf(\"SELECT id FROM t WHERE id='%s'\", a)\n"
            "q = db.Rebind(q)\n"
            "db.Query(q)"
        ),
        [],
    ),
    (
        _go(
            "q := fmt.Sprintf(\"SELECT id FROM t WHERE name='%s'\", pq.QuoteIdentifier(a))\n"
            "db.Query(q)"
        ),
        [],
    ),
    (
        _go(
            "id := pq.QuoteIdentifier(a)\n"
            "q := fmt.Sprintf(\"DELETE FROM t WHERE name='%s'\", id)\n"
            "tx.Exec(q)"
        ),
        [],
    ),
    (_go('dockerClient.Exec(fmt.Sprintf("SELECT id FROM t WHERE id=%s", a))'), []),
    (_go('kubeClient.Query(fmt.Sprintf("SELECT id FROM t WHERE id=%s", a))'), []),
    (_go("clientset.Exec(fmt.Sprintf(\"UPDATE t SET name='%s'\", a))"), []),
    (_go('q := "note SELECT " + a\ndb.Query(q)'), []),
    (_go('db.Query(fmt.Sprintf("-- SELECT %s", a))'), []),
    (_go('db.Exec(fmt.Sprintf("UPDATE %s SET a=1", d))'), []),
    (_go('db.Query(fmt.Sprintf("SELECT id FROM %s", d))'), []),
    (_go('db.Exec(fmt.Sprintf("INSERT INTO %s VALUES (1)", d))'), []),
    (_go('db.Get(out, fmt.Sprintf("SELECT id FROM t WHERE id=%s", a))'), []),
    (_go('db.Select(out, fmt.Sprintf("SELECT id FROM t WHERE id=%s", a))'), []),
    (
        _go(
            'q := fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\n' 'q = "SELECT 1"\n' "db.Query(q)"
        ),
        [],
    ),
    (
        _go(
            'q := fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\n'
            'if d != "" {\n'
            'q = "SELECT 1"\n'
            "} else {\n"
            'q = "SELECT 2"\n'
            "}\n"
            "db.Query(q)"
        ),
        [],
    ),
    (
        _go(
            'q := fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\n'
            "go func() {\n"
            "db.Query(q)\n"
            "}()"
        ),
        [],
    ),
]


@pytest.mark.parametrize("code, expected", GO_SQL)
def test_go_sql_value_injection(code: str, expected) -> None:
    assert _rules("go", code) == expected


def test_go_sql_parameter_and_other_function_are_not_tracked() -> None:
    param = "package p\n\nfunc f(q string) {\ndb.Query(q)\n}\n"
    assert _rules("go", param) == []
    other = (
        "package p\n\n"
        "func helper(a string) string {\n"
        'return fmt.Sprintf("SELECT id FROM t WHERE id=%s", a)\n'
        "}\n\n"
        "func f(a string) {\n"
        "q := helper(a)\n"
        "db.Query(q)\n"
        "}\n"
    )
    assert _rules("go", other) == []


def test_go_sql_skips_test_files_and_migration_directories() -> None:
    code = _go('db.Query(fmt.Sprintf("SELECT id FROM t WHERE id=%s", a))')
    assert _rules("go", code, path="pkg/q_test.go") == []
    assert _rules("go", code, path="db/migrations/001.go") == []
    assert _rules("go", code, path="db/migrations.go") == _GO005
    both = _go(
        'command := fmt.Sprintf("ls %s", d)\n'
        'exec.Command("sh", "-c", command)\n'
        'db.Query(fmt.Sprintf("SELECT id FROM t WHERE id=%s", a))'
    )
    assert _rules("go", both, path="db/migrations/001.go") == [("GO001", 5, "HIGH")]


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


def test_go_sql_value_is_go005_and_identifier_is_not() -> None:
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = _go('db.Query("SELECT * FROM t WHERE a=" + a)')
    tree = TreeSitterParser("go").parse(code, "a.go")
    issues = [i for i in _analyzer().analyze(tree, "a.go", code) if i.rule_id]
    assert [(i.rule_id, i.issue_type.value, i.metadata.get("cwe")) for i in issues] == [
        ("GO005", "SQL_INJECTION_RISK", "CWE-89")
    ]
    assert _rules("go", _go('tx.Exec(fmt.Sprintf("DELETE FROM %s", d))')) == []


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
