"""Security rules for C#, Go and Rust.

The rules read the tree-sitter syntax tree that the multi-language parser
builds, so string literals and comments never match. Each rule reports one
finding per construct with a stable ``rule_id``:

* C#: CS001 SQL built from strings, CS002 dangerous formatters, CS003
  ``Process.Start`` with a built string, CS004 broken hash or cipher.
* Go: GO001 shell ``-c`` with a built string, GO002 SQL built from strings,
  GO003 ``crypto/md5``, ``crypto/sha1``, ``crypto/des`` or ``crypto/rc4``,
  GO004 ``InsecureSkipVerify: true``.
* Rust: RS001 ``unsafe`` inventory, RS002 ``mem::transmute``, RS003 shell
  ``-c`` with a ``format!`` string.

Test files are skipped.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, Iterator, List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST, GenericNode

LANGUAGES = frozenset({"c_sharp", "go", "rust"})

_SQL_WORDS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC)\b", re.I)
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "/bin/sh", "/bin/bash", "/usr/bin/env"})


def _ts(node: GenericNode) -> str:
    return str(node.metadata.get("treesitter_type", ""))


def _named(node: GenericNode) -> List[GenericNode]:
    return [c for c in node.children if c.metadata.get("named", True) and "comment" not in _ts(c)]


def _walk(node: GenericNode) -> Iterator[GenericNode]:
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def _last_name(text: str) -> str:
    text = re.sub(r"<.*>$", "", text.strip())
    return re.split(r"[.:]+", text)[-1]


class _Ctx:
    def __init__(self, file_path: str, language: str) -> None:
        self.file_path = file_path
        self.language = language
        self.issues: List[AnalysisIssue] = []
        self.seen: set = set()

    def add(
        self,
        node: GenericNode,
        rule_id: str,
        issue_type: AnalysisIssueType,
        severity: AnalysisIssueSeverity,
        message: str,
        suggestion: str,
        cwe: Optional[str] = None,
    ) -> None:
        key = (rule_id, node.line_start, node.column_start)
        if key in self.seen:
            return
        self.seen.add(key)
        metadata: Dict[str, object] = {"language": self.language}
        if cwe:
            metadata["cwe"] = cwe
        self.issues.append(
            AnalysisIssue(
                file_path=self.file_path,
                line=node.line_start,
                column=node.column_start,
                issue_type=issue_type,
                severity=severity,
                message=message,
                suggestion=suggestion,
                code_snippet=node.text.splitlines()[0][:200] if node.text else None,
                metadata=metadata,
                engine="internal:security",
                rule_id=rule_id,
                source="code",
            )
        )


# --- shared ------------------------------------------------------------------

_LITERALS = frozenset(
    {
        "string_literal",
        "verbatim_string_literal",
        "raw_string_literal",
        "interpreted_string_literal",
        "character_literal",
        "integer_literal",
        "int_literal",
        "string",
    }
)


def _is_literal(node: GenericNode) -> bool:
    t = _ts(node)
    if t in _LITERALS:
        return True
    if t == "interpolated_string_expression":
        return not any(_ts(n) == "interpolation" for n in _walk(node))
    if t in ("parenthesized_expression",):
        return all(_is_literal(c) for c in _named(node))
    if t == "binary_expression":
        return all(_is_literal(c) for c in _named(node))
    return False


def _literal_text(node: GenericNode) -> str:
    return " ".join(n.text for n in _walk(node) if _ts(n) in _LITERALS or "string" in _ts(n))


def _built_string(node: GenericNode) -> bool:
    """True when ``node`` builds a string from a literal and a non-literal."""
    t = _ts(node)
    if t == "interpolated_string_expression":
        return any(_ts(n) == "interpolation" for n in _walk(node))
    if t == "binary_expression":
        ops = [c.text for c in node.children if not c.metadata.get("named", True)]
        if "+" not in ops:
            return False
        parts = _named(node)
        has_literal = any(_is_literal(p) or _built_string(p) for p in parts)
        return has_literal and not all(_is_literal(p) for p in parts)
    if t in ("invocation_expression", "call_expression"):
        func = _named(node)[0] if _named(node) else None
        if func is None:
            return False
        name = func.text.replace(" ", "")
        if name in ("string.Format", "String.Format", "fmt.Sprintf"):
            return len(_args(node)) > 1
    if t == "parenthesized_expression":
        return any(_built_string(c) for c in _named(node))
    return False


def _args(call: GenericNode) -> List[GenericNode]:
    for child in _named(call):
        if _ts(child) in ("argument_list", "arguments"):
            out = []
            for arg in _named(child):
                if _ts(arg) == "argument":
                    inner = _named(arg)
                    out.append(inner[-1] if inner else arg)
                else:
                    out.append(arg)
            return out
    return []


def _string_value(node: GenericNode) -> Optional[str]:
    if _ts(node) in ("string_literal", "interpreted_string_literal", "raw_string_literal"):
        return node.text.strip('"`')
    return None


# --- C# ------------------------------------------------------------------------

_CS_SQL_TYPES = frozenset(
    {"SqlCommand", "OleDbCommand", "OdbcCommand", "NpgsqlCommand", "MySqlCommand", "SqliteCommand"}
)
_CS_SQL_RAW = frozenset(
    {"ExecuteSqlRaw", "ExecuteSqlRawAsync", "FromSqlRaw", "SqlQueryRaw", "ExecuteSqlCommand"}
)
_CS_FORMATTERS = frozenset(
    {
        "BinaryFormatter",
        "SoapFormatter",
        "NetDataContractSerializer",
        "LosFormatter",
        "ObjectStateFormatter",
    }
)
_CS_WEAK_FACTORIES = frozenset({"MD5", "SHA1", "DES", "TripleDES", "RC2"})
_CS_WEAK_TYPES = frozenset(
    {
        "MD5CryptoServiceProvider",
        "SHA1CryptoServiceProvider",
        "SHA1Managed",
        "DESCryptoServiceProvider",
        "TripleDESCryptoServiceProvider",
        "RC2CryptoServiceProvider",
    }
)


def _cs_sql(ctx: _Ctx, node: GenericNode) -> None:
    ctx.add(
        node,
        "CS001",
        AnalysisIssueType.SQL_INJECTION_RISK,
        AnalysisIssueSeverity.HIGH,
        "SQL command text is built from strings",
        "Use parameters (@name with Parameters.Add) instead of concatenation or interpolation.",
        "CWE-89",
    )


def _cs_process(ctx: _Ctx, node: GenericNode) -> None:
    ctx.add(
        node,
        "CS003",
        AnalysisIssueType.COMMAND_INJECTION,
        AnalysisIssueSeverity.MEDIUM,
        "Process started with a command line built from strings",
        "Pass a fixed program and use ProcessStartInfo.ArgumentList for each argument.",
        "CWE-78",
    )


def _cs_weak(ctx: _Ctx, node: GenericNode, name: str) -> None:
    ctx.add(
        node,
        "CS004",
        AnalysisIssueType.INSECURE_CRYPTOGRAPHY,
        AnalysisIssueSeverity.MEDIUM,
        f"Broken or weak algorithm: {name}",
        "Use SHA256 or stronger for hashing and Aes (GCM) for encryption.",
        "CWE-327",
    )


def _check_csharp(ctx: _Ctx, root: GenericNode) -> None:
    for node in _walk(root):
        t = _ts(node)
        if t == "object_creation_expression":
            parts = _named(node)
            type_name = _last_name(parts[0].text) if parts else ""
            args = _args(node)
            if type_name in _CS_SQL_TYPES and args and _built_string(args[0]):
                _cs_sql(ctx, node)
            elif type_name in _CS_FORMATTERS:
                ctx.add(
                    node,
                    "CS002",
                    AnalysisIssueType.INSECURE_DESERIALIZATION,
                    AnalysisIssueSeverity.HIGH,
                    f"{type_name} deserializes untrusted data unsafely",
                    "Use System.Text.Json or DataContractSerializer with known types.",
                    "CWE-502",
                )
            elif type_name == "ProcessStartInfo" and any(_built_string(a) for a in args):
                _cs_process(ctx, node)
            elif type_name in _CS_WEAK_TYPES:
                _cs_weak(ctx, node, type_name)
        elif t == "invocation_expression":
            parts = _named(node)
            if not parts:
                continue
            func = parts[0].text.replace(" ", "")
            member = _last_name(func)
            args = _args(node)
            if member in _CS_SQL_RAW and args and _built_string(args[0]):
                _cs_sql(ctx, node)
            elif (func == "Process.Start" or func.endswith(".Process.Start")) and any(
                _built_string(a) for a in args
            ):
                _cs_process(ctx, node)
            elif "." in func:
                owner = _last_name(func.rsplit(".", 1)[0])
                if owner in _CS_WEAK_FACTORIES and member in ("Create", "HashData"):
                    _cs_weak(ctx, node, owner)
        elif t == "assignment_expression":
            parts = _named(node)
            if (
                len(parts) >= 2
                and _last_name(parts[0].text) == "CommandText"
                and _built_string(parts[-1])
            ):
                _cs_sql(ctx, node)


# --- Go ------------------------------------------------------------------------

_GO_SQL_METHODS = {
    "Query": 0,
    "QueryRow": 0,
    "Exec": 0,
    "Prepare": 0,
    "QueryContext": 1,
    "QueryRowContext": 1,
    "ExecContext": 1,
    "PrepareContext": 1,
}
_GO_WEAK = {
    "crypto/md5": ("md5", {"New", "Sum"}),
    "crypto/sha1": ("sha1", {"New", "Sum"}),
    "crypto/des": ("des", {"NewCipher", "NewTripleDESCipher"}),
    "crypto/rc4": ("rc4", {"NewCipher"}),
}


def _go_imports(root: GenericNode) -> Dict[str, str]:
    """Map local package name -> import path for the crypto packages."""
    out: Dict[str, str] = {}
    for node in _walk(root):
        if _ts(node) != "import_spec":
            continue
        parts = _named(node)
        path = parts[-1].text.strip('"`') if parts else ""
        if path not in _GO_WEAK:
            continue
        alias = parts[0].text if len(parts) == 2 else _GO_WEAK[path][0]
        out[alias] = path
    return out


def _check_go(ctx: _Ctx, root: GenericNode) -> None:
    imports = _go_imports(root)
    for node in _walk(root):
        t = _ts(node)
        if t == "call_expression":
            parts = _named(node)
            if not parts:
                continue
            func = parts[0].text.replace(" ", "")
            args = _args(node)
            if func in ("exec.Command", "exec.CommandContext"):
                rest = args[1:] if func == "exec.CommandContext" else args
                if (
                    len(rest) >= 3
                    and _string_value(rest[0]) in _SHELLS
                    and _string_value(rest[1]) == "-c"
                    and any(_built_string(a) for a in rest[2:])
                ):
                    ctx.add(
                        node,
                        "GO001",
                        AnalysisIssueType.COMMAND_INJECTION,
                        AnalysisIssueSeverity.HIGH,
                        "Shell command built from strings and run with -c",
                        "Call the program directly with exec.Command(name, args...).",
                        "CWE-78",
                    )
                continue
            if _ts(parts[0]) == "selector_expression" and "." in func:
                owner, method = func.rsplit(".", 1)
                index = _GO_SQL_METHODS.get(method)
                if index is not None and len(args) > index:
                    sql = args[index]
                    if _built_string(sql) and _SQL_WORDS.search(_literal_text(sql)):
                        ctx.add(
                            node,
                            "GO002",
                            AnalysisIssueType.SQL_INJECTION_RISK,
                            AnalysisIssueSeverity.HIGH,
                            "SQL query built from strings",
                            "Use placeholders ($1 or ?) and pass values as arguments.",
                            "CWE-89",
                        )
                    continue
                path = imports.get(owner)
                if path and method in _GO_WEAK[path][1]:
                    ctx.add(
                        node,
                        "GO003",
                        AnalysisIssueType.INSECURE_CRYPTOGRAPHY,
                        AnalysisIssueSeverity.MEDIUM,
                        f"Broken or weak algorithm: {path}",
                        "Use crypto/sha256 or stronger, and crypto/aes with GCM.",
                        "CWE-327",
                    )
        elif t == "keyed_element":
            parts = _named(node)
            if (
                len(parts) == 2
                and parts[0].text.strip() == "InsecureSkipVerify"
                and parts[1].text.strip() == "true"
            ):
                ctx.add(
                    node,
                    "GO004",
                    AnalysisIssueType.INSECURE_COMMUNICATION,
                    AnalysisIssueSeverity.HIGH,
                    "TLS certificate verification is disabled",
                    "Remove InsecureSkipVerify, or set RootCAs to trust a private CA.",
                    "CWE-295",
                )


# --- Rust ----------------------------------------------------------------------

_RS_TRANSMUTE = frozenset(
    {"transmute", "mem::transmute", "std::mem::transmute", "core::mem::transmute"}
)
_RS_SHELL_CHAIN = re.compile(r'Command::new\(\s*"(?:/bin/)?(?:sh|bash|zsh|dash)"\s*\)')
_RS_DASH_C = re.compile(r'(?:\.arg\(\s*"-c"\s*\)|\.args\(\s*[\[&]*\s*"-c")')


def _check_rust(ctx: _Ctx, root: GenericNode) -> None:
    def visit(node: GenericNode, parent_type: str) -> None:
        t = _ts(node)
        if t == "unsafe_block":
            ctx.add(
                node,
                "RS001",
                AnalysisIssueType.UNSAFE_CODE,
                AnalysisIssueSeverity.LOW,
                "unsafe block",
                "Keep unsafe blocks small and document the invariants (// SAFETY:).",
            )
        elif t == "function_item" and any(
            _ts(c) == "function_modifiers" and "unsafe" in c.text for c in node.children
        ):
            ctx.add(
                node,
                "RS001",
                AnalysisIssueType.UNSAFE_CODE,
                AnalysisIssueSeverity.LOW,
                "unsafe fn",
                "Document the caller's obligations in a # Safety section.",
            )
        elif t == "call_expression":
            parts = _named(node)
            func = parts[0] if parts else None
            if func is not None:
                name = func.text.replace(" ", "")
                if _ts(func) == "generic_function":
                    name = re.sub(r"::<.*>$", "", name)
                if name in _RS_TRANSMUTE:
                    ctx.add(
                        node,
                        "RS002",
                        AnalysisIssueType.UNSAFE_CODE,
                        AnalysisIssueSeverity.MEDIUM,
                        "mem::transmute reinterprets bits without checks",
                        "Prefer from_bits/to_bits, from_ne_bytes or a safe cast.",
                        "CWE-843",
                    )
            if parent_type not in ("field_expression", "call_expression"):
                text = node.text
                if _RS_SHELL_CHAIN.search(text) and _RS_DASH_C.search(text) and "format!" in text:
                    ctx.add(
                        node,
                        "RS003",
                        AnalysisIssueType.COMMAND_INJECTION,
                        AnalysisIssueSeverity.HIGH,
                        "Shell command built with format! and run with -c",
                        "Call the program directly with Command::new(program).args(...).",
                        "CWE-78",
                    )
        for child in node.children:
            visit(child, t)

    visit(root, "")


_CHECKS: Dict[str, Callable[[_Ctx, GenericNode], None]] = {
    "c_sharp": _check_csharp,
    "go": _check_go,
    "rust": _check_rust,
}


def find_language_rule_issues(tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
    """Run the C#, Go or Rust rules for ``tree``; other languages return []."""
    check = _CHECKS.get(tree.language)
    if check is None:
        return []
    ctx = _Ctx(file_path, tree.language)
    check(ctx, tree.root)
    return ctx.issues


def rule_lines(issues: List[AnalysisIssue]) -> Tuple[set, set]:
    """Lines already reported as SQL and command injection by these rules."""
    sql = {i.line for i in issues if i.issue_type == AnalysisIssueType.SQL_INJECTION_RISK}
    cmd = {i.line for i in issues if i.issue_type == AnalysisIssueType.COMMAND_INJECTION}
    return sql, cmd
