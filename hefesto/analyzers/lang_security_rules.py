"""Security rules for C#, Go, Rust, C and C++.

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
* C and C++: CC001 ``gets``, CC002 unbounded copy or write (``strcpy``,
  ``strcat``, ``sprintf`` with ``%s``, ``scanf`` ``%s`` without a width),
  CC003 format string that is not a literal, CC004 ``system``/``popen`` with
  a command that is not a literal.

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

LANGUAGES = frozenset({"c_sharp", "go", "rust", "c", "cpp"})

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


def _go_shell(ctx: _Ctx, node: GenericNode, func: str, args: List[GenericNode]) -> None:
    rest = args[1:] if func == "exec.CommandContext" else args
    if len(rest) < 3 or _string_value(rest[0]) not in _SHELLS:
        return
    if _string_value(rest[1]) == "-c" and any(_built_string(a) for a in rest[2:]):
        ctx.add(
            node,
            "GO001",
            AnalysisIssueType.COMMAND_INJECTION,
            AnalysisIssueSeverity.HIGH,
            "Shell command built from strings and run with -c",
            "Call the program directly with exec.Command(name, args...).",
            "CWE-78",
        )


def _go_sql(ctx: _Ctx, node: GenericNode, sql: GenericNode) -> None:
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


def _go_weak(ctx: _Ctx, node: GenericNode, path: str) -> None:
    ctx.add(
        node,
        "GO003",
        AnalysisIssueType.INSECURE_CRYPTOGRAPHY,
        AnalysisIssueSeverity.MEDIUM,
        f"Broken or weak algorithm: {path}",
        "Use crypto/sha256 or stronger, and crypto/aes with GCM.",
        "CWE-327",
    )


def _go_method_call(
    ctx: _Ctx, node: GenericNode, func: str, args: List[GenericNode], imports: Dict[str, str]
) -> None:
    owner, method = func.rsplit(".", 1)
    index = _GO_SQL_METHODS.get(method)
    if index is not None and len(args) > index:
        _go_sql(ctx, node, args[index])
        return
    path = imports.get(owner)
    if path and method in _GO_WEAK[path][1]:
        _go_weak(ctx, node, path)


def _go_call(ctx: _Ctx, node: GenericNode, imports: Dict[str, str]) -> None:
    parts = _named(node)
    if not parts:
        return
    func = parts[0].text.replace(" ", "")
    args = _args(node)
    if func in ("exec.Command", "exec.CommandContext"):
        _go_shell(ctx, node, func, args)
    elif _ts(parts[0]) == "selector_expression" and "." in func:
        _go_method_call(ctx, node, func, args, imports)


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


def _check_go(ctx: _Ctx, root: GenericNode) -> None:
    imports = _go_imports(root)
    for node in _walk(root):
        t = _ts(node)
        if t == "call_expression":
            _go_call(ctx, node, imports)
        elif t == "keyed_element":
            _go_keyed(ctx, node)


# --- Rust ----------------------------------------------------------------------

_RS_TRANSMUTE = frozenset(
    {"transmute", "mem::transmute", "std::mem::transmute", "core::mem::transmute"}
)
_RS_SHELL_CHAIN = re.compile(r'Command::new\(\s*"(?:/bin/)?(?:sh|bash|zsh|dash)"\s*\)')
_RS_DASH_C = re.compile(r'(?:\.arg\(\s*"-c"\s*\)|\.args\(\s*[\[&]*\s*"-c")')


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


def _rs_shell(ctx: _Ctx, node: GenericNode) -> None:
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


def _rs_call(ctx: _Ctx, node: GenericNode, parent_type: str) -> None:
    _rs_transmute(ctx, node)
    # Only the outermost call of a method chain, so one chain gives one finding.
    if parent_type not in ("field_expression", "call_expression"):
        _rs_shell(ctx, node)


def _check_rust(ctx: _Ctx, root: GenericNode) -> None:
    for node, parent_type in _walk_with_parent(root):
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
            _rs_call(ctx, node, parent_type)


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
        text = func.text.replace(" ", "")
        if text.startswith("::"):
            text = text[2:]
        if text.startswith("std::"):
            text = text[5:]
        return text if re.fullmatch(r"[A-Za-z_]\w*", text) else None
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


def _cc_arg_literal(args: List[GenericNode], idx: int) -> Tuple[bool, Optional[str]]:
    """(present, literal text) for argument ``idx``."""
    if len(args) <= idx:
        return False, None
    return True, _cc_literal(args[idx])


def _cc_format_rule(func: str, args: List[GenericNode]) -> Optional[str]:
    present, fmt = _cc_arg_literal(args, _CC_FORMAT[func])
    if not present:
        return None
    if fmt is None:
        fmt_node = args[_CC_FORMAT[func]]
        # An all-caps name is a macro holding a literal (``LOG_FMT``).
        if _ts(fmt_node) == "identifier" and fmt_node.text.isupper():
            return None
        return "CC003"
    if func in ("sprintf", "vsprintf") and _CC_UNBOUNDED_S.search(fmt):
        return "CC002"
    return None


def _cc_rule(func: str, args: List[GenericNode]) -> Optional[str]:
    """The rule a call to ``func`` with ``args`` breaks, if any."""
    if func == "gets":
        return "CC001"
    if func in _CC_COPY:
        present, src = _cc_arg_literal(args, 1)
        return "CC002" if present and src is None else None
    if func in _CC_SCANF:
        _, fmt = _cc_arg_literal(args, _CC_SCANF[func])
        return "CC002" if fmt is not None and _CC_SCANF_S.search(fmt) else None
    if func in _CC_FORMAT:
        return _cc_format_rule(func, args)
    if func in _CC_SHELL:
        present, cmd = _cc_arg_literal(args, 0)
        return "CC004" if present and cmd is None else None
    return None


def _cc_call(ctx: _Ctx, node: GenericNode) -> None:
    func = _cc_func_name(node)
    if func is None:
        return
    rule = _cc_rule(func, _cc_args(node))
    if rule is not None:
        _cc_add(ctx, node, rule, func)


def _check_c_cpp(ctx: _Ctx, root: GenericNode) -> None:
    for node in _walk(root):
        if _ts(node) == "call_expression":
            _cc_call(ctx, node)


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
