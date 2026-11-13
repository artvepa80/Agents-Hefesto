"""Security rules for C#, Go, Rust, C and C++.

The rules read the tree-sitter syntax tree that the multi-language parser
builds, so string literals and comments never match. Each rule reports one
finding per construct with a stable ``rule_id``:

* C#: CS001 SQL built from strings, CS002 dangerous formatters, CS003
  ``Process.Start`` with a built string, CS004 MD5/SHA-1 (LOW inventory) or broken
  cipher (MEDIUM).
* Go: GO001 shell ``-c`` with a string built in the same function, GO003
  ``crypto/md5``, ``crypto/sha1`` (LOW inventory), ``crypto/des`` or
  ``crypto/rc4`` (MEDIUM), GO004 ``InsecureSkipVerify: true``, GO005 a SQL
  value built in the same function. GO002 (SQL built from strings) was
  dropped from v1: every measured hit was non-actionable.
* Rust: RS001 ``unsafe`` inventory, RS002 ``mem::transmute``, RS003 shell
  ``-c`` with a ``format!`` string in the same call or built earlier in the
  same function.
* C and C++: CC001 ``gets``, CC002 unbounded copy or write (``strcpy``,
  ``strcat``, ``sprintf`` with ``%s``, ``scanf`` ``%s`` without a width),
  CC003 format string that is not a literal, CC004 ``system``/``popen`` with
  a command that is not a literal.

Test files are skipped.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, Iterator, List, Optional, Tuple

from hefesto.analyzers.lang_go_flow import _HOLE, _GoString, visit_go_calls
from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST, GenericNode

LANGUAGES = frozenset({"c_sharp", "go", "rust", "c", "cpp"})

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


def _concat_builds_string(node: GenericNode) -> bool:
    """``"a" + x``: a ``+`` with a literal part and a non-literal part."""
    ops = [c.text for c in node.children if not c.metadata.get("named", True)]
    if "+" not in ops:
        return False
    parts = _named(node)
    has_literal = any(_is_literal(p) or _built_string(p) for p in parts)
    return has_literal and not all(_is_literal(p) for p in parts)


def _format_call_builds_string(node: GenericNode) -> bool:
    """``string.Format(fmt, x)`` or ``fmt.Sprintf(fmt, x)`` with at least one value."""
    parts = _named(node)
    if not parts:
        return False
    name = parts[0].text.replace(" ", "")
    return name in ("string.Format", "String.Format", "fmt.Sprintf") and len(_args(node)) > 1


def _built_string(node: GenericNode) -> bool:
    """True when ``node`` builds a string from a literal and a non-literal."""
    t = _ts(node)
    if t == "interpolated_string_expression":
        return any(_ts(n) == "interpolation" for n in _walk(node))
    if t == "binary_expression":
        return _concat_builds_string(node)
    if t in ("invocation_expression", "call_expression"):
        return _format_call_builds_string(node)
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


_WEAK_HASH_NAMES = frozenset(
    {
        "MD5",
        "SHA1",
        "MD5CryptoServiceProvider",
        "SHA1CryptoServiceProvider",
        "SHA1Managed",
        "crypto/md5",
        "crypto/sha1",
    }
)


def _weak_algorithm(ctx: _Ctx, node: GenericNode, rule: str, name: str, suggestion: str) -> None:
    """MD5/SHA-1 are an inventory (LOW): most uses are checksums or protocol-mandated.

    Broken ciphers (DES, 3DES, RC2, RC4) stay MEDIUM.
    """
    if name in _WEAK_HASH_NAMES:
        severity = AnalysisIssueSeverity.LOW
        message = (
            f"Weak hash {name} (inventory): fine for checksums, not for passwords or signatures"
        )
    else:
        severity = AnalysisIssueSeverity.MEDIUM
        message = f"Broken cipher: {name}"
    ctx.add(
        node,
        rule,
        AnalysisIssueType.INSECURE_CRYPTOGRAPHY,
        severity,
        message,
        suggestion,
        "CWE-327",
    )


def _cs_weak(ctx: _Ctx, node: GenericNode, name: str) -> None:
    _weak_algorithm(
        ctx, node, "CS004", name, "Use SHA256 or stronger for hashing and Aes (GCM) for encryption."
    )


def _cs_creation(ctx: _Ctx, node: GenericNode) -> None:
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


def _cs_weak_factory(func: str) -> Optional[str]:
    """``MD5`` for ``MD5.Create``/``HashData``; None for anything else."""
    if "." not in func:
        return None
    owner = _last_name(func.rsplit(".", 1)[0])
    if owner in _CS_WEAK_FACTORIES and _last_name(func) in ("Create", "HashData"):
        return owner
    return None


def _cs_invocation(ctx: _Ctx, node: GenericNode) -> None:
    parts = _named(node)
    if not parts:
        return
    func = parts[0].text.replace(" ", "")
    args = _args(node)
    is_process = func == "Process.Start" or func.endswith(".Process.Start")
    weak = _cs_weak_factory(func)
    if _last_name(func) in _CS_SQL_RAW and args and _built_string(args[0]):
        _cs_sql(ctx, node)
    elif is_process and any(_built_string(a) for a in args):
        _cs_process(ctx, node)
    elif weak:
        _cs_weak(ctx, node, weak)


def _cs_assignment(ctx: _Ctx, node: GenericNode) -> None:
    parts = _named(node)
    if len(parts) < 2:
        return
    if _last_name(parts[0].text) == "CommandText" and _built_string(parts[-1]):
        _cs_sql(ctx, node)


_CS_HANDLERS: Dict[str, Callable[[_Ctx, GenericNode], None]] = {
    "object_creation_expression": _cs_creation,
    "invocation_expression": _cs_invocation,
    "assignment_expression": _cs_assignment,
}


def _check_csharp(ctx: _Ctx, root: GenericNode) -> None:
    for node in _walk(root):
        handler = _CS_HANDLERS.get(_ts(node))
        if handler is not None:
            handler(ctx, node)


# --- Go ------------------------------------------------------------------------

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


def _report_go_shell(
    ctx: _Ctx,
    node: GenericNode,
    func: GenericNode,
    args: List[GenericNode],
    facts: List[_GoString],
) -> None:
    """``exec.Command("sh", "-c", cmd)`` when ``cmd`` was built in this function."""
    name = "".join(func.text.split())
    if name not in ("exec.Command", "exec.CommandContext"):
        return
    offset = 1 if name == "exec.CommandContext" else 0
    if len(args) < offset + 3 or _string_value(args[offset]) not in _SHELLS:
        return
    if _string_value(args[offset + 1]) != "-c":
        return
    if any(item.built for item in facts[offset + 2 :]):
        ctx.add(
            node,
            "GO001",
            AnalysisIssueType.COMMAND_INJECTION,
            AnalysisIssueSeverity.HIGH,
            "Shell command built from strings and run with -c",
            "Call the program directly with exec.Command(name, args...).",
            "CWE-78",
        )


def _go_weak(ctx: _Ctx, node: GenericNode, path: str) -> None:
    _weak_algorithm(
        ctx, node, "GO003", path, "Use crypto/sha256 or stronger, and crypto/aes with GCM."
    )


def _go_method_call(
    ctx: _Ctx, node: GenericNode, func: str, args: List[GenericNode], imports: Dict[str, str]
) -> None:
    owner, method = func.rsplit(".", 1)
    path = imports.get(owner)
    if path and method in _GO_WEAK[path][1]:
        _go_weak(ctx, node, path)


def _go_call(ctx: _Ctx, node: GenericNode, imports: Dict[str, str]) -> None:
    parts = _named(node)
    if not parts:
        return
    func = parts[0].text.replace(" ", "")
    if _ts(parts[0]) == "selector_expression" and "." in func:
        _go_method_call(ctx, node, func, _args(node), imports)


def _go_keyed(ctx: _Ctx, node: GenericNode) -> None:
    parts = _named(node)
    if len(parts) != 2 or parts[0].text.strip() != "InsecureSkipVerify":
        return
    if parts[1].text.strip() == "true":
        ctx.add(
            node,
            "GO004",
            AnalysisIssueType.INSECURE_COMMUNICATION,
            AnalysisIssueSeverity.HIGH,
            "TLS certificate verification is disabled",
            "Remove InsecureSkipVerify, or set RootCAs to trust a private CA.",
            "CWE-295",
        )


_GO_SQL_ARG = {
    "Query": 0,
    "QueryRow": 0,
    "Exec": 0,
    "Prepare": 0,
    "Raw": 0,
    "Queryx": 0,
    "QueryRowx": 0,
    "NamedQuery": 0,
    "NamedExec": 0,
    "MustExec": 0,
    "QueryContext": 1,
    "QueryRowContext": 1,
    "ExecContext": 1,
    "PrepareContext": 1,
    "QueryxContext": 1,
    "QueryRowxContext": 1,
    "NamedQueryContext": 1,
    "NamedExecContext": 1,
    "MustExecContext": 1,
}
_GO_SQL_START = re.compile(r"(?is)^\s*(SELECT|INSERT|UPDATE|DELETE)\b")
_GO_SQL_MAINT = re.compile(r"(?i)\b(?:setval|PRAGMA|VACUUM)\b")
_GO_PLACEHOLDER = re.compile(r"\?|\$\d+|@[A-Za-z_][A-Za-z0-9_]*")
_GO_NON_SQL = re.compile(r"(?i)kubernetes|k8s\.io|clientset|docker|containerd|podman|kube")
_GO_QUOTES = "'\""
_GO_WS = " \t\r\n"


def _go_migration(path: str) -> bool:
    return "migrations" in path.replace("\\", "/").split("/")


def _skip_sql_string(text: str, start: int) -> int:
    quote = text[start]
    i = start + 1
    n = len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] != quote:
            i += 1
            continue
        if quote == "'" and i + 1 < n and text[i + 1] == "'":
            i += 2
            continue
        return i + 1
    return n


def _mask_sql_strings(text: str) -> str:
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] not in _GO_QUOTES:
            out.append(text[i])
            i += 1
            continue
        end = _skip_sql_string(text, i)
        out.append(text[i])
        out.append(" " * max(end - i - 1, 0))
        i = end
    return "".join(out)


def _has_placeholder(text: str) -> bool:
    return _GO_PLACEHOLDER.search(_mask_sql_strings(text)) is not None


def _word_edge(ch: str) -> bool:
    return not (ch.isalnum() or ch == "_")


def _at_in(text: str, i: int) -> bool:
    if i + 2 > len(text) or text[i : i + 2].lower() != "in":
        return False
    before = text[i - 1] if i else " "
    after = text[i + 2] if i + 2 < len(text) else " "
    return _word_edge(before) and _word_edge(after)


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i] in _GO_WS:
        i += 1
    return i


def _skip_ws_back(text: str, i: int) -> int:
    while i >= 0 and text[i] in _GO_WS:
        i -= 1
    return i


def _paren_delta(ch: str) -> int:
    if ch == "(":
        return 1
    if ch == ")":
        return -1
    return 0


def _close_paren(text: str, open_at: int) -> int:
    depth = 0
    i = open_at
    while i < len(text):
        if text[i] in _GO_QUOTES:
            i = _skip_sql_string(text, i)
            continue
        depth += _paren_delta(text[i])
        if depth == 0:
            return i
        i += 1
    return len(text)


def _take_in_span(text: str, i: int, spans: List[Tuple[int, int]]) -> int:
    j = _skip_ws(text, i + 2)
    if j < len(text) and text[j] == "(":
        spans.append((j + 1, _close_paren(text, j)))
        return j + 1
    return i + 2


def _in_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] in _GO_QUOTES:
            i = _skip_sql_string(text, i)
            continue
        if _at_in(text, i):
            i = _take_in_span(text, i, spans)
            continue
        i += 1
    return spans


def _hole_positions(text: str) -> List[int]:
    found: List[int] = []
    start = 0
    while True:
        pos = text.find(_HOLE, start)
        if pos < 0:
            return found
        found.append(pos)
        start = pos + len(_HOLE)


def _holes_only_in_in(text: str) -> bool:
    spans = _in_spans(text)
    positions = _hole_positions(text)
    if not spans or not positions:
        return False
    return all(any(start <= pos < end for start, end in spans) for pos in positions)


def _in_sql_string(text: str, pos: int) -> bool:
    i = 0
    while i < pos:
        if text[i] not in _GO_QUOTES:
            i += 1
            continue
        nxt = _skip_sql_string(text, i)
        if nxt > pos:
            return True
        i = nxt
    return False


def _values_before(text: str, paren: int) -> bool:
    end = _skip_ws_back(text, paren - 1)
    start = end - 5
    if start < 0 or text[start : end + 1].lower() != "values":
        return False
    before = text[start - 1] if start else " "
    return _word_edge(before)


def _after_value_mark(text: str, pos: int) -> bool:
    j = _skip_ws_back(text, pos - 1)
    if j < 0:
        return False
    if text[j] in "=<>!":
        return True
    if text[j] == "(":
        return _values_before(text, j)
    return False


def _has_value_hole(text: str) -> bool:
    for pos in _hole_positions(text):
        if _in_sql_string(text, pos) or _after_value_mark(text, pos):
            return True
    return False


def _go_sql_shaped(fact: _GoString) -> bool:
    """True when ``fact`` is a DML string with a value inserted in this function."""
    text = fact.text
    if text is None or _HOLE not in text or fact.quote_ident_holes:
        return False
    if _GO_SQL_START.match(text) is None or _GO_SQL_MAINT.search(text):
        return False
    if _has_placeholder(text) or _holes_only_in_in(text):
        return False
    return _has_value_hole(text)


def _go_field_name(func: GenericNode) -> str:
    for child in _named(func):
        if _ts(child) == "field_identifier":
            return child.text
    return ""


def _go_sql_index(func: GenericNode) -> Optional[int]:
    if _ts(func) != "selector_expression":
        return None
    return _GO_SQL_ARG.get(_go_field_name(func))


def _report_go_sql(ctx: _Ctx, node: GenericNode, func: GenericNode, facts: List[_GoString]) -> None:
    if _go_migration(ctx.file_path) or _GO_NON_SQL.search(func.text):
        return
    index = _go_sql_index(func)
    if index is None or index >= len(facts) or not facts[index].sql_risk:
        return
    ctx.add(
        node,
        "GO005",
        AnalysisIssueType.SQL_INJECTION_RISK,
        AnalysisIssueSeverity.HIGH,
        "SQL query built from strings and passed to a query function",
        "Use placeholders (? or $1) and pass values as arguments.",
        "CWE-89",
    )


def _on_go_flow(
    ctx: _Ctx,
    node: GenericNode,
    func: GenericNode,
    args: List[GenericNode],
    facts: List[_GoString],
) -> None:
    _report_go_shell(ctx, node, func, args, facts)
    _report_go_sql(ctx, node, func, facts)


def _check_go(ctx: _Ctx, root: GenericNode) -> None:
    imports = _go_imports(root)
    for node in _walk(root):
        t = _ts(node)
        if t == "call_expression":
            _go_call(ctx, node, imports)
        elif t == "keyed_element":
            _go_keyed(ctx, node)
    visit_go_calls(root, lambda *parts: _on_go_flow(ctx, *parts), _go_sql_shaped)


# --- Rust ----------------------------------------------------------------------

_RS_TRANSMUTE = frozenset(
    {"transmute", "mem::transmute", "std::mem::transmute", "core::mem::transmute"}
)
_RS_SHELL_CHAIN = re.compile(r'Command::new\(\s*"(?:/bin/)?(?:sh|bash|zsh|dash)"\s*\)')
_RS_DASH_C = re.compile(r'(?:\.arg\(\s*"-c"\s*\)|\.args\(\s*[\[&]*\s*"-c")')
_RS_SHELLS = frozenset(
    {"sh", "bash", "zsh", "dash", "/bin/sh", "/bin/bash", "/bin/zsh", "/bin/dash"}
)
_RS_PASSTHROUGH = frozenset(
    {"as_str", "as_mut_str", "as_ref", "to_string", "to_owned", "into", "trim"}
)
_RS_BUILT = "built"
_RS_CONST = "const"
_RS_UNKNOWN = "unknown"
_RS_HOLE = re.compile(r"\{([^{}]*)\}")
_RS_LET_SKIP = frozenset(
    {
        "mutable_specifier",
        "identifier",
        "type_identifier",
        "generic_type",
        "reference_type",
        "primitive_type",
        "scoped_type_identifier",
        "tuple_type",
        "array_type",
        "function_type",
        "lifetime",
    }
)


def _walk_with_parent(root: GenericNode) -> Iterator[Tuple[GenericNode, str]]:
    """Pre-order walk yielding each node with its parent's tree-sitter type."""
    stack: List[Tuple[GenericNode, str]] = [(root, "")]
    while stack:
        node, parent_type = stack.pop()
        yield node, parent_type
        t = _ts(node)
        stack.extend((child, t) for child in reversed(node.children))


def _rs_unsafe(ctx: _Ctx, node: GenericNode, message: str, suggestion: str) -> None:
    ctx.add(
        node, "RS001", AnalysisIssueType.UNSAFE_CODE, AnalysisIssueSeverity.LOW, message, suggestion
    )


def _rs_is_unsafe_fn(node: GenericNode) -> bool:
    return any(_ts(c) == "function_modifiers" and "unsafe" in c.text for c in node.children)


def _rs_transmute(ctx: _Ctx, node: GenericNode) -> None:
    parts = _named(node)
    if not parts:
        return
    name = parts[0].text.replace(" ", "")
    if _ts(parts[0]) == "generic_function":
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


def _rs_report_shell(ctx: _Ctx, node: GenericNode) -> None:
    ctx.add(
        node,
        "RS003",
        AnalysisIssueType.COMMAND_INJECTION,
        AnalysisIssueSeverity.HIGH,
        "Shell command built with format! and run with -c",
        "Call the program directly with Command::new(program).args(...).",
        "CWE-78",
    )


class _RsBindings:
    """Names bound in one function. ``True`` was built with ``format!``.

    A closure reads the enclosing function but its assignments stay local:
    the closure may not run. A nested function does not see the outer names.
    """

    def __init__(self, parent: Optional["_RsBindings"] = None, local_only: bool = False) -> None:
        self.parent = parent
        self.local_only = local_only
        self.vals: Dict[str, Optional[bool]] = {}

    def get(self, name: str) -> Optional[bool]:
        if name in self.vals:
            return self.vals[name]
        if self.parent is not None:
            return self.parent.get(name)
        return None

    def let_name(self, name: str, built: Optional[bool]) -> None:
        self.vals[name] = built

    def assign(self, name: str, built: Optional[bool]) -> None:
        if self.local_only or name in self.vals or self.parent is None:
            self.vals[name] = built
            return
        self.parent.assign(name, built)


def _rs_merge(kinds: List[str]) -> str:
    """One built branch makes the value built; every branch constant keeps it constant."""
    if any(kind == _RS_BUILT for kind in kinds):
        return _RS_BUILT
    if kinds and all(kind == _RS_CONST for kind in kinds):
        return _RS_CONST
    return _RS_UNKNOWN


def _rs_stored(kind: str) -> Optional[bool]:
    if kind == _RS_BUILT:
        return True
    if kind == _RS_CONST:
        return False
    return None


def _rs_string_body(node: GenericNode) -> Optional[str]:
    if _ts(node) not in ("string_literal", "raw_string_literal"):
        return None
    return "".join(c.text for c in node.children if _ts(c) == "string_content")


def _rs_class(node: Optional[GenericNode], scope: _RsBindings) -> str:
    """``built`` when a ``format!`` hole is not a constant; calls are not opened."""
    if node is None:
        return _RS_UNKNOWN
    kind = _RS_CLASS.get(_ts(node))
    if kind is None:
        return _RS_UNKNOWN
    return kind(node, scope)


def _rs_const_literal(node: GenericNode, scope: _RsBindings) -> str:
    return _RS_CONST


def _rs_ident_class(node: GenericNode, scope: _RsBindings) -> str:
    known = scope.get(node.text)
    if known is True:
        return _RS_BUILT
    if known is False:
        return _RS_CONST
    return _RS_UNKNOWN


def _rs_unwrap_class(node: GenericNode, scope: _RsBindings) -> str:
    kids = _named(node)
    return _rs_class(kids[0], scope) if kids else _RS_UNKNOWN


def _rs_block_tail(node: GenericNode) -> Optional[GenericNode]:
    skipped = {
        "let_declaration",
        "expression_statement",
        "use_declaration",
        "function_item",
        "const_item",
        "attribute_item",
        "inner_attribute_item",
    }
    for child in reversed(_named(node)):
        if _ts(child) not in skipped:
            return child
    return None


def _rs_block_class(node: GenericNode, scope: _RsBindings) -> str:
    return _rs_class(_rs_block_tail(node), scope)


def _rs_if_class(node: GenericNode, scope: _RsBindings) -> str:
    branches: List[GenericNode] = []
    for child in _named(node):
        if _ts(child) == "block":
            branches.append(child)
        elif _ts(child) == "else_clause":
            inner = _named(child)
            if inner:
                branches.append(inner[-1])
    return _rs_merge([_rs_class(branch, scope) for branch in branches])


def _rs_match_class(node: GenericNode, scope: _RsBindings) -> str:
    block = next((c for c in _named(node) if _ts(c) == "match_block"), None)
    if block is None:
        return _RS_UNKNOWN
    kinds: List[str] = []
    for arm in _named(block):
        if _ts(arm) != "match_arm":
            continue
        values = [c for c in _named(arm) if _ts(c) != "match_pattern"]
        kinds.append(_rs_class(values[-1], scope) if values else _RS_UNKNOWN)
    return _rs_merge(kinds)


def _rs_binary_class(node: GenericNode, scope: _RsBindings) -> str:
    ops = [c.text for c in node.children if not c.metadata.get("named", True)]
    if "+" not in ops:
        return _RS_UNKNOWN
    return _rs_merge([_rs_class(c, scope) for c in _named(node)])


def _rs_call_name(func: GenericNode) -> str:
    return func.text.replace(" ", "")


def _rs_passthrough_class(func: GenericNode, args: List[GenericNode], scope: _RsBindings) -> str:
    named = _named(func)
    if len(named) < 2 or named[-1].text not in _RS_PASSTHROUGH or args:
        return _RS_UNKNOWN
    return _rs_class(named[0], scope)


def _rs_call_class(node: GenericNode, scope: _RsBindings) -> str:
    """A call is not a build. ``as_str``/``String::from`` keep the receiver's kind."""
    parts = _named(node)
    if len(parts) < 1:
        return _RS_UNKNOWN
    func, args = parts[0], _args(node)
    if _ts(func) == "field_expression":
        return _rs_passthrough_class(func, args, scope)
    name = _rs_call_name(func)
    if (name == "String::from" or name.endswith("::String::from")) and len(args) == 1:
        return _rs_class(args[0], scope)
    if name == "String::new" or name.endswith("::String::new"):
        return _RS_CONST
    return _RS_UNKNOWN


def _rs_token_items(token: GenericNode) -> List[GenericNode]:
    return [c for c in token.children if _ts(c) not in ("(", ")", ",")]


def _rs_macro_parts(node: GenericNode) -> Tuple[str, List[GenericNode]]:
    named = _named(node)
    name = named[0].text if named else ""
    token = next((c for c in named if _ts(c) == "token_tree"), None)
    return name, [] if token is None else _rs_token_items(token)


def _rs_named_arg(items: List[GenericNode], index: int) -> bool:
    return (
        _ts(items[index]) == "identifier"
        and index + 2 < len(items)
        and items[index + 1].text == "="
    )


def _rs_format_lists(items: List[GenericNode]) -> Tuple[List[GenericNode], Dict[str, GenericNode]]:
    """Positional arguments, and ``name = value`` arguments, after the template."""
    positional: List[GenericNode] = []
    named: Dict[str, GenericNode] = {}
    index = 0
    while index < len(items):
        if _rs_named_arg(items, index):
            named[items[index].text] = items[index + 2]
            index += 3
            continue
        positional.append(items[index])
        index += 1
    return positional, named


def _rs_hole_dynamic(
    body: str,
    positional: List[GenericNode],
    named: Dict[str, GenericNode],
    scope: _RsBindings,
    cursor: List[int],
) -> bool:
    head = body.split(":", 1)[0].strip()
    if head.isdigit():
        arg = positional[int(head)] if int(head) < len(positional) else None
        return arg is None or _rs_class(arg, scope) != _RS_CONST
    if head == "":
        arg = positional[cursor[0]] if cursor[0] < len(positional) else None
        cursor[0] += 1
        return arg is None or _rs_class(arg, scope) != _RS_CONST
    if head in named:
        return _rs_class(named[head], scope) != _RS_CONST
    # ``format!("{name}")`` reads ``name`` from the function. A known constant does not.
    return scope.get(head) is not False


def _rs_format_class(node: GenericNode, scope: _RsBindings) -> str:
    _name, items = _rs_macro_parts(node)
    if not items or _rs_string_body(items[0]) is None:
        return _RS_UNKNOWN
    body = _rs_string_body(items[0]) or ""
    holes = _RS_HOLE.findall(body.replace("{{", "").replace("}}", ""))
    if not holes:
        return _RS_CONST
    positional, named = _rs_format_lists(items[1:])
    cursor = [0]
    dynamic = any(_rs_hole_dynamic(hole, positional, named, scope, cursor) for hole in holes)
    return _RS_BUILT if dynamic else _RS_CONST


def _rs_macro_class(node: GenericNode, scope: _RsBindings) -> str:
    name, items = _rs_macro_parts(node)
    if name == "format":
        return _rs_format_class(node, scope)
    if name == "concat":
        bodies = [_rs_string_body(item) for item in items]
        return _RS_CONST if bodies and all(body is not None for body in bodies) else _RS_UNKNOWN
    return _RS_UNKNOWN


_RS_CLASS: Dict[str, Callable[[GenericNode, _RsBindings], str]] = {
    "string_literal": _rs_const_literal,
    "raw_string_literal": _rs_const_literal,
    "integer_literal": _rs_const_literal,
    "char_literal": _rs_const_literal,
    "float_literal": _rs_const_literal,
    "identifier": _rs_ident_class,
    "reference_expression": _rs_unwrap_class,
    "parenthesized_expression": _rs_unwrap_class,
    "block": _rs_block_class,
    "if_expression": _rs_if_class,
    "match_expression": _rs_match_class,
    "binary_expression": _rs_binary_class,
    "call_expression": _rs_call_class,
    "macro_invocation": _rs_macro_class,
}


def _rs_let_name(node: GenericNode) -> Optional[str]:
    for child in _named(node):
        if _ts(child) == "identifier":
            return child.text
    return None


def _rs_let_value(node: GenericNode) -> Optional[GenericNode]:
    for child in _named(node):
        if _ts(child) not in _RS_LET_SKIP:
            return child
    return None


def _rs_chain(call: GenericNode) -> List[Tuple[str, List[GenericNode]]]:
    """Method chain from the inside out: ``(Command::new, args)`` then ``.arg``."""
    links: List[Tuple[str, List[GenericNode]]] = []
    current: Optional[GenericNode] = call
    while current is not None and _ts(current) == "call_expression":
        named = _named(current)
        if not named:
            break
        func = named[0]
        if _ts(func) == "field_expression":
            field = _named(func)
            method = field[-1].text if field else ""
            links.append((method, _args(current)))
            current = field[0] if field else None
            continue
        links.append((_rs_call_name(func), _args(current)))
        break
    links.reverse()
    return links


def _rs_is_shell_name(node: GenericNode) -> bool:
    return _rs_string_body(node) in _RS_SHELLS


def _rs_array_after_dash_c(node: GenericNode) -> List[GenericNode]:
    if _ts(node) == "reference_expression":
        kids = _named(node)
        return _rs_array_after_dash_c(kids[0]) if kids else []
    if _ts(node) != "array_expression":
        return []
    elems = _named(node)
    for index, elem in enumerate(elems):
        if _rs_string_body(elem) == "-c" and index + 1 < len(elems):
            return [elems[index + 1]]
    return []


def _rs_one_payload(
    method: str, args: List[GenericNode], expect: bool
) -> Tuple[List[GenericNode], bool]:
    """The ``-c`` command from one ``.arg`` or ``.args`` link, and whether the next is it."""
    if method == "arg" and args and _rs_string_body(args[0]) == "-c":
        return [], True
    if method == "arg" and expect and args:
        return [args[0]], False
    if method == "args" and args:
        return _rs_array_after_dash_c(args[0]), False
    return [], False


def _rs_shell_payloads(call: GenericNode) -> List[GenericNode]:
    links = _rs_chain(call)
    if not links or "Command::new" not in links[0][0]:
        return []
    head_args = links[0][1]
    if not head_args or not _rs_is_shell_name(head_args[0]):
        return []
    payloads: List[GenericNode] = []
    expect = False
    for method, args in links[1:]:
        found, expect = _rs_one_payload(method, args, expect)
        payloads.extend(found)
    return payloads


def _rs_payload_built(call: GenericNode, scope: _RsBindings) -> bool:
    return any(_rs_class(payload, scope) == _RS_BUILT for payload in _rs_shell_payloads(call))


def _rs_shell_flow(ctx: _Ctx, node: GenericNode, scope: _RsBindings) -> None:
    text = node.text
    if not (_RS_SHELL_CHAIN.search(text) and _RS_DASH_C.search(text)):
        return
    # ``format!`` anywhere in the chain keeps the previous same-call behaviour.
    if "format!" in text or _rs_payload_built(node, scope):
        _rs_report_shell(ctx, node)


def _rs_push_receiver(node: GenericNode) -> Optional[str]:
    """The identifier ``push_str`` is called on, or None."""
    named = _named(node)
    if len(named) < 2 or _ts(named[0]) != "field_expression":
        return None
    field = _named(named[0])
    if len(field) < 2 or field[-1].text != "push_str":
        return None
    receiver = field[0]
    if _ts(receiver) == "reference_expression":
        inner = _named(receiver)
        receiver = inner[0] if inner else receiver
    return receiver.text if _ts(receiver) == "identifier" else None


def _rs_push_str(node: GenericNode, scope: _RsBindings) -> None:
    name = _rs_push_receiver(node)
    args = _args(node)
    if name and args and _rs_class(args[0], scope) == _RS_BUILT:
        scope.assign(name, True)


def _rs_bind_let(ctx: _Ctx, node: GenericNode, scope: _RsBindings) -> None:
    value = _rs_let_value(node)
    if value is not None:
        _rs_exec(ctx, value, scope)
    name = _rs_let_name(node)
    if name:
        scope.let_name(name, _rs_stored(_rs_class(value, scope)))


def _rs_bind_assign(ctx: _Ctx, node: GenericNode, scope: _RsBindings) -> None:
    parts = _named(node)
    if len(parts) < 2:
        return
    _rs_exec(ctx, parts[-1], scope)
    if _ts(parts[0]) == "identifier":
        scope.assign(parts[0].text, _rs_stored(_rs_class(parts[-1], scope)))


def _rs_bind_append(ctx: _Ctx, node: GenericNode, scope: _RsBindings) -> None:
    if not any(child.text == "+=" for child in node.children):
        _rs_exec_children(ctx, node, scope)
        return
    parts = _named(node)
    if len(parts) < 2:
        return
    _rs_exec(ctx, parts[-1], scope)
    if _ts(parts[0]) == "identifier" and _rs_class(parts[-1], scope) == _RS_BUILT:
        scope.assign(parts[0].text, True)


def _rs_exec_children(ctx: _Ctx, node: GenericNode, scope: _RsBindings) -> None:
    parent = _ts(node)
    for child in node.children:
        _rs_exec(ctx, child, scope, parent)


def _rs_exec_call(ctx: _Ctx, node: GenericNode, scope: _RsBindings, parent: str) -> None:
    # One finding per chain: inner ``.arg`` calls are not reported again.
    if parent not in ("field_expression", "call_expression"):
        _rs_shell_flow(ctx, node, scope)
    _rs_push_str(node, scope)
    _rs_exec_children(ctx, node, scope)


def _rs_exec_block(ctx: _Ctx, node: GenericNode, scope: _RsBindings) -> None:
    _rs_exec_children(ctx, node, _RsBindings(scope))


def _rs_exec_closure(ctx: _Ctx, node: GenericNode, scope: _RsBindings) -> None:
    _rs_exec_children(ctx, node, _RsBindings(scope, local_only=True))


def _rs_exec_fn(ctx: _Ctx, node: GenericNode) -> None:
    fresh = _RsBindings(None)
    for child in node.children:
        if _ts(child) == "block":
            _rs_exec_block(ctx, child, fresh)


def _rs_exec(ctx: _Ctx, node: GenericNode, scope: _RsBindings, parent: str = "") -> None:
    handler = _RS_EXEC.get(_ts(node))
    if handler is not None:
        handler(ctx, node, scope, parent)
        return
    _rs_exec_children(ctx, node, scope)


def _rs_on_let(ctx: _Ctx, node: GenericNode, scope: _RsBindings, parent: str) -> None:
    _rs_bind_let(ctx, node, scope)


def _rs_on_assign(ctx: _Ctx, node: GenericNode, scope: _RsBindings, parent: str) -> None:
    _rs_bind_assign(ctx, node, scope)


def _rs_on_append(ctx: _Ctx, node: GenericNode, scope: _RsBindings, parent: str) -> None:
    _rs_bind_append(ctx, node, scope)


def _rs_on_block(ctx: _Ctx, node: GenericNode, scope: _RsBindings, parent: str) -> None:
    _rs_exec_block(ctx, node, scope)


def _rs_on_closure(ctx: _Ctx, node: GenericNode, scope: _RsBindings, parent: str) -> None:
    _rs_exec_closure(ctx, node, scope)


def _rs_on_fn(ctx: _Ctx, node: GenericNode, scope: _RsBindings, parent: str) -> None:
    _rs_exec_fn(ctx, node)


_RS_EXEC: Dict[str, Callable[[_Ctx, GenericNode, _RsBindings, str], None]] = {
    "function_item": _rs_on_fn,
    "closure_expression": _rs_on_closure,
    "block": _rs_on_block,
    "let_declaration": _rs_on_let,
    "assignment_expression": _rs_on_assign,
    "compound_assignment_expr": _rs_on_append,
    "call_expression": _rs_exec_call,
}


def _rs_call(ctx: _Ctx, node: GenericNode) -> None:
    _rs_transmute(ctx, node)


def _check_rust(ctx: _Ctx, root: GenericNode) -> None:
    for node, _parent_type in _walk_with_parent(root):
        t = _ts(node)
        if t == "unsafe_block":
            _rs_unsafe(
                ctx,
                node,
                "unsafe block",
                "Keep unsafe blocks small and document the invariants (// SAFETY:).",
            )
        elif t == "function_item" and _rs_is_unsafe_fn(node):
            _rs_unsafe(
                ctx, node, "unsafe fn", "Document the caller's obligations in a # Safety section."
            )
        elif t == "call_expression":
            _rs_call(ctx, node)
    _rs_exec(ctx, root, _RsBindings(None))


# --- C and C++ -------------------------------------------------------------------

# Copy/append functions with no size limit (the source is not a literal).
_CC_COPY = frozenset(
    {"strcpy", "strcat", "wcscpy", "wcscat", "lstrcpy", "lstrcat", "StrCpy", "StrCat"}
)
# scanf family -> index of the format argument.
_CC_SCANF = {"scanf": 0, "vscanf": 0, "sscanf": 1, "fscanf": 1, "vsscanf": 1, "vfscanf": 1}
# printf family -> index of the format argument.
_CC_FORMAT = {
    "printf": 0,
    "vprintf": 0,
    "fprintf": 1,
    "vfprintf": 1,
    "dprintf": 1,
    "sprintf": 1,
    "vsprintf": 1,
    "snprintf": 2,
    "vsnprintf": 2,
    "syslog": 1,
    "vsyslog": 1,
    "err": 1,
    "warn": 0,
    "warnx": 0,
    "errx": 1,
}
_CC_SHELL = {"system": 0, "popen": 0, "_popen": 0, "_wsystem": 0, "_wpopen": 0}
_CC_UNBOUNDED_S = re.compile(r"%(?:\d+\$)?[-+ #0]*(?:\d+|\*)?l?s")
_CC_SCANF_S = re.compile(r"%\*?(?:s|\[)")
_CC_STRING_TYPES = frozenset({"string_literal", "concatenated_string", "raw_string_literal"})


def _cc_strip_qualifiers(text: str) -> Optional[str]:
    """``::gets`` and ``std::gets`` become ``gets``; other qualifiers are None."""
    if text.startswith("::"):
        text = text[2:]
    if text.startswith("std::"):
        text = text[5:]
    return text if re.fullmatch(r"[A-Za-z_]\w*", text) else None


def _cc_func_name(call: GenericNode) -> Optional[str]:
    """``gets``, ``std::gets`` or ``::gets``; None for ``obj.f`` and ``p->f``."""
    parts = _named(call)
    if not parts:
        return None
    func = parts[0]
    t = _ts(func)
    if t == "identifier":
        return func.text
    if t == "qualified_identifier":
        return _cc_strip_qualifiers(func.text.replace(" ", ""))
    return None


def _cc_args(call: GenericNode) -> List[GenericNode]:
    for child in _named(call):
        if _ts(child) == "argument_list":
            return _named(child)
    return []


def _cc_literal(node: GenericNode) -> Optional[str]:
    """The text of a string literal (adjacent literals joined); None otherwise."""
    if _ts(node) in _CC_STRING_TYPES:
        return node.text
    return None


_CC_GETTEXT = frozenset({"_", "N_", "gettext", "dgettext", "ngettext"})


def _cc_const_binary(node: GenericNode, kids: List[GenericNode]) -> bool:
    return len(kids) == 2 and "+" in node.text and _cc_const(kids[0])


def _cc_const_ternary(node: GenericNode, kids: List[GenericNode]) -> bool:
    return len(kids) == 3 and _cc_const(kids[1]) and _cc_const(kids[2])


def _cc_const_call(node: GenericNode, kids: List[GenericNode]) -> bool:
    args = _cc_args(node)
    return _cc_func_name(node) in _CC_GETTEXT and bool(args) and _cc_const(args[-1])


def _cc_const_paren(node: GenericNode, kids: List[GenericNode]) -> bool:
    return bool(kids) and _cc_const(kids[0])


_CC_CONST_CHECKS: Dict[str, Callable[[GenericNode, List[GenericNode]], bool]] = {
    "binary_expression": _cc_const_binary,
    "conditional_expression": _cc_const_ternary,
    "call_expression": _cc_const_call,
    "parenthesized_expression": _cc_const_paren,
}


def _cc_const(node: GenericNode) -> bool:
    """True when ``node`` always yields a constant string.

    Covers literals, ALL-CAPS macro names, ``"lit" + n``, ``c ? "a" : "b"``
    and gettext calls on a literal such as ``_("text")``.
    """
    t = _ts(node)
    if t in _CC_STRING_TYPES:
        return True
    if t == "identifier":
        return node.text.isupper()
    check = _CC_CONST_CHECKS.get(t)
    return check is not None and check(node, _named(node))


def _cc_add(ctx: _Ctx, node: GenericNode, rule: str, func: str) -> None:
    if rule == "CC001":
        ctx.add(
            node,
            "CC001",
            AnalysisIssueType.UNSAFE_BUFFER_FUNCTION,
            AnalysisIssueSeverity.HIGH,
            "gets() reads a line with no size limit",
            "Use fgets(buf, sizeof buf, stdin).",
            "CWE-242",
        )
    elif rule == "CC002":
        ctx.add(
            node,
            "CC002",
            AnalysisIssueType.UNSAFE_BUFFER_FUNCTION,
            AnalysisIssueSeverity.MEDIUM,
            f"{func}() writes into a buffer with no size limit",
            "Use a bounded form (snprintf, strlcpy/strncat with the buffer size, "
            "or a width such as %31s) and check the length.",
            "CWE-120",
        )
    elif rule == "CC003":
        ctx.add(
            node,
            "CC003",
            AnalysisIssueType.FORMAT_STRING_RISK,
            AnalysisIssueSeverity.MEDIUM,
            f"{func}() format string is not a literal",
            'Pass a literal format, for example printf("%s", text).',
            "CWE-134",
        )
    else:
        ctx.add(
            node,
            "CC004",
            AnalysisIssueType.COMMAND_INJECTION,
            AnalysisIssueSeverity.HIGH,
            f"{func}() runs a shell command that is not a literal",
            "Run a fixed program with execv/posix_spawn and pass each argument separately.",
            "CWE-78",
        )


class _CcScope:
    """Where a call sits: the wrapper's forwarded parameters and earlier statements."""

    def __init__(self, forwarded: frozenset, before: str) -> None:
        self.forwarded = forwarded
        self.before = before


def _cc_arg(args: List[GenericNode], idx: int) -> Optional[GenericNode]:
    return args[idx] if len(args) > idx else None


def _cc_length_checked(src: GenericNode, scope: _CcScope) -> bool:
    """``strlen(src)``/``strnlen(src`` appears in the few statements before."""
    if _ts(src) != "identifier":
        return False
    pattern = r"\bstrn?len\s*\(\s*" + re.escape(src.text) + r"\b"
    return re.search(pattern, scope.before) is not None


def _cc_nonliteral_format(
    func: str, args: List[GenericNode], fmt_node: GenericNode, scope: _CcScope
) -> Optional[str]:
    """CC003 when a non-constant format has no arguments after it."""
    if len(args) > _CC_FORMAT[func] + 1 or _cc_const(fmt_node):
        return None
    if _ts(fmt_node) == "identifier" and fmt_node.text in scope.forwarded:
        return None
    return "CC003"


def _cc_format_rule(func: str, args: List[GenericNode], scope: _CcScope) -> Optional[str]:
    fmt_node = _cc_arg(args, _CC_FORMAT[func])
    if fmt_node is None:
        return None
    fmt = _cc_literal(fmt_node)
    if fmt is None:
        # Only a format with nothing after it: printf(buf) treats data as a
        # format; printf(fmt, x) passes values to a format chosen in code.
        return _cc_nonliteral_format(func, args, fmt_node, scope)
    if func in ("sprintf", "vsprintf") and _CC_UNBOUNDED_S.search(fmt):
        return "CC002"
    return None


def _cc_copy_rule(args: List[GenericNode], scope: _CcScope) -> Optional[str]:
    src = _cc_arg(args, 1)
    if src is None or _cc_const(src) or _cc_length_checked(src, scope):
        return None
    return "CC002"


def _cc_scanf_rule(func: str, args: List[GenericNode]) -> Optional[str]:
    fmt_node = _cc_arg(args, _CC_SCANF[func])
    fmt = _cc_literal(fmt_node) if fmt_node is not None else None
    return "CC002" if fmt is not None and _CC_SCANF_S.search(fmt) else None


def _cc_shell_rule(args: List[GenericNode]) -> Optional[str]:
    cmd = _cc_arg(args, 0)
    return "CC004" if cmd is not None and _cc_literal(cmd) is None else None


def _cc_format_family(func: str, args: List[GenericNode], scope: _CcScope) -> Optional[str]:
    """Scanf, then the printf family, then shell. That order is the rule order."""
    if func in _CC_SCANF:
        return _cc_scanf_rule(func, args)
    if func in _CC_FORMAT:
        return _cc_format_rule(func, args, scope)
    if func in _CC_SHELL:
        return _cc_shell_rule(args)
    return None


def _cc_rule(func: str, args: List[GenericNode], scope: _CcScope) -> Optional[str]:
    """The rule a call to ``func`` with ``args`` breaks, if any."""
    if func == "gets":
        return "CC001"
    if func in _CC_COPY:
        return _cc_copy_rule(args, scope)
    return _cc_format_family(func, args, scope)


def _cc_call(ctx: _Ctx, node: GenericNode, scope: _CcScope) -> None:
    func = _cc_func_name(node)
    if func is None:
        return
    rule = _cc_rule(func, _cc_args(node), scope)
    if rule is not None:
        _cc_add(ctx, node, rule, func)


def _cc_forwarded(fn: GenericNode) -> frozenset:
    """Parameter names of a variadic or ``va_list`` function (its format is the caller's)."""
    for node in _walk(fn):
        if _ts(node) == "parameter_list":
            text = node.text
            if "..." not in text and "va_list" not in text:
                return frozenset()
            return frozenset(re.findall(r"([A-Za-z_]\w*)\s*(?:\[\s*\])?\s*(?=[,)])", text))
    return frozenset()


_CC_BEFORE = 3


def _check_c_cpp(ctx: _Ctx, root: GenericNode) -> None:
    stack: List[Tuple[GenericNode, _CcScope]] = [(root, _CcScope(frozenset(), ""))]
    while stack:
        node, scope = stack.pop()
        t = _ts(node)
        if t == "function_definition":
            scope = _CcScope(_cc_forwarded(node), "")
        if t == "call_expression":
            _cc_call(ctx, node, scope)
        kids = node.children
        if t == "compound_statement":
            named = _named(node)
            scopes = [
                _CcScope(
                    scope.forwarded, "\n".join(c.text for c in named[max(0, i - _CC_BEFORE) : i])
                )
                for i in range(len(named))
            ]
            stack.extend(reversed(list(zip(named, scopes))))
            continue
        stack.extend((child, scope) for child in reversed(kids))


_CHECKS: Dict[str, Callable[[_Ctx, GenericNode], None]] = {
    "c_sharp": _check_csharp,
    "go": _check_go,
    "rust": _check_rust,
    "c": _check_c_cpp,
    "cpp": _check_c_cpp,
}


def find_language_rule_issues(tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
    """Run the C#, Go, Rust, C or C++ rules for ``tree``; other languages return []."""
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
