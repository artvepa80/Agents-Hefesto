"""Security rules for C#, Go, Rust, C and C++.

The rules read the tree-sitter syntax tree that the multi-language parser
builds, so string literals and comments never match. Each rule reports one
finding per construct with a stable ``rule_id``:

* C#: CS001 SQL built from strings, CS002 dangerous formatters, CS003
  ``Process.Start`` with a built string, CS004 MD5/SHA-1 (LOW inventory) or broken
  cipher (MEDIUM).
* Go: GO001 shell ``-c`` with a built string (including a variable assigned
  in the same block), GO003 ``crypto/md5``, ``crypto/sha1`` (LOW inventory),
  ``crypto/des`` or ``crypto/rc4`` (MEDIUM), GO004 ``InsecureSkipVerify: true``,
  GO005 a SQL value built from a non-constant argument. GO002 (any SQL built
  from strings) was dropped from v1: every measured hit was non-actionable.
  GO005 does not reuse that id.
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
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple

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


class _GoFact:
    """What a local name was last assigned in this block.

    ``built`` is a shell string from ``fmt.Sprintf`` or ``+`` with a
    non-constant part. ``sql`` is a DML value slot filled by one.
    ``constant`` is a literal (or a name copied from one).
    """

    __slots__ = ("built", "sql", "constant")

    def __init__(self, built: bool = False, sql: bool = False, constant: bool = False) -> None:
        self.built = built
        self.sql = sql
        self.constant = constant


_GoEnv = Dict[str, _GoFact]
_GoVisit = Callable[["_Ctx", GenericNode, _GoEnv, Dict[str, str], Set[str]], None]

# database/sql methods. The Context forms take the query as the second argument.
_GO_SQL_ARG = {
    "Query": 0,
    "QueryRow": 0,
    "Exec": 0,
    "Prepare": 0,
    "QueryContext": 1,
    "QueryRowContext": 1,
    "ExecContext": 1,
    "PrepareContext": 1,
}
_GO_DML = re.compile(r"(?is)^\s*(select|insert|update|delete|replace|with)\b")
_GO_SETVAL = re.compile(r"(?is)\bsetval\s*\(")
# Catalog lookups interpolate schema names. That was the non-actionable class.
_GO_CATALOG = re.compile(
    r"(?i)\b(sqlite_master|sqlite_schema|sqlite_temp_master|information_schema|pg_catalog)\b"
)
# ``%%`` is a literal percent. ``%[n]`` is an explicit argument index.
# ``*`` width or precision consumes an extra argument, so those formats are skipped.
_GO_VERB = re.compile(
    r"%(?P<esc>%)"
    r"|%(?P<index>\[\d+\])?(?P<flags>[#+\- 0]*)(?P<width>\d+|\*)?"
    r"(?P<prec>\.(?:\d+|\*))?(?P<verb>[A-Za-z])"
)
_GO_STRING_VERBS = frozenset({"s", "q", "v"})
_GO_VALUE_OPS = ("=", "<", ">", "!")
_GO_SCOPE = frozenset(
    {
        "block",
        "if_statement",
        "expression_switch_statement",
        "type_switch_statement",
        "select_statement",
        "expression_case",
        "default_case",
        "type_case",
        "communication_case",
    }
)


def _go_fmt_aliases(root: GenericNode) -> Set[str]:
    """Local names of the ``fmt`` package. ``fmt`` itself always counts.

    Fixtures call ``fmt.Sprintf`` without an import spec. An alias
    (``import f "fmt"``) is added when the file has one.
    """
    names = {"fmt"}
    for node in _walk(root):
        if _ts(node) != "import_spec":
            continue
        parts = _named(node)
        if not parts or parts[-1].text.strip('"`') != "fmt":
            continue
        # The alias is a package_identifier, not an identifier.
        if len(parts) == 2:
            names.add(parts[0].text.strip())
    return names


def _go_string_literal(node: GenericNode) -> Optional[str]:
    """Contents of a Go string literal, quotes removed, escapes left in place."""
    text = node.text
    kind = _ts(node)
    if kind == "interpreted_string_literal" and len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1]
    if kind == "raw_string_literal" and len(text) >= 2 and text[0] == text[-1] == "`":
        return text[1:-1]
    return None


def _go_sql_escaped_quote(text: str, index: int, single: bool) -> bool:
    return single and text[index] == "'" and index + 1 < len(text) and text[index + 1] == "'"


def _go_quote_step(text: str, index: int, single: bool, tick: bool) -> Tuple[bool, bool, int]:
    char = text[index]
    if tick:
        return single, char != "`", index + 1
    if char == "`":
        return single, True, index + 1
    if char == "\\" or _go_sql_escaped_quote(text, index, single):
        return single, tick, index + 2
    if char == "'":
        return not single, tick, index + 1
    return single, tick, index + 1


def _go_inside_single(text: str) -> bool:
    """True when text inserted after ``text`` sits in a SQL single-quoted string."""
    single = False
    tick = False
    index = 0
    while index < len(text):
        single, tick, index = _go_quote_step(text, index, single, tick)
    return single and not tick


def _go_dml_text(text: str) -> bool:
    """DML that is not a sequence reset or a catalog lookup."""
    if _GO_SETVAL.search(text) or _GO_CATALOG.search(text):
        return False
    return _GO_DML.match(text) is not None


def _go_hole_is_value(before: str) -> bool:
    """True when inserted text is inside quotes or directly after =, <, > or !."""
    return _go_inside_single(before) or before.rstrip().endswith(_GO_VALUE_OPS)


def _go_percents_covered(fmt: str) -> bool:
    cursor = 0
    for match in _GO_VERB.finditer(fmt):
        if fmt.find("%", cursor, match.start()) != -1:
            return False
        cursor = match.end()
    return fmt.find("%", cursor) == -1


def _go_one_slot(match: "re.Match[str]", next_arg: int) -> Optional[Tuple[str, int, int, int]]:
    """``(verb, value-arg index, start, next sequential arg)``, or None if ``*`` is used."""
    if match.group("esc"):
        return ("%", 0, match.start(), next_arg)
    precision = match.group("prec") or ""
    if match.group("width") == "*" or "*" in precision:
        return None
    index = match.group("index")
    if index:
        return (match.group("verb"), int(index[1:-1]) - 1, match.start(), next_arg)
    return (match.group("verb"), next_arg, match.start(), next_arg + 1)


def _go_format_slots(fmt: str) -> Optional[List[Tuple[str, int, int]]]:
    """``(verb, value-arg index, start)`` for each verb. None if the format is not simple."""
    if not _go_percents_covered(fmt):
        return None
    slots: List[Tuple[str, int, int]] = []
    next_arg = 0
    for match in _GO_VERB.finditer(fmt):
        slot = _go_one_slot(match, next_arg)
        if slot is None:
            return None
        verb, arg_index, start, next_arg = slot
        if verb != "%":
            slots.append((verb, arg_index, start))
    return slots


def _go_nonconst(node: GenericNode, env: _GoEnv) -> bool:
    """True when ``node`` is not a literal and not a name assigned from one."""
    if _is_literal(node):
        return False
    kind = _ts(node)
    if kind == "parenthesized_expression":
        named = _named(node)
        return len(named) == 1 and _go_nonconst(named[0], env)
    if kind != "identifier":
        return True
    fact = env.get(node.text.strip())
    return fact is None or not fact.constant


def _go_is_sprintf(node: GenericNode, fmt_names: Set[str]) -> bool:
    parts = _named(node)
    if not parts or "." not in parts[0].text:
        return False
    owner, method = parts[0].text.replace(" ", "").rsplit(".", 1)
    return method == "Sprintf" and owner in fmt_names


def _go_plus_parts(node: GenericNode) -> List[GenericNode]:
    if _ts(node) != "binary_expression":
        return [node]
    ops = [child.text for child in node.children if not child.metadata.get("named", True)]
    named = _named(node)
    if "+" not in ops or len(named) != 2:
        return [node]
    return _go_plus_parts(named[0]) + [named[1]]


def _go_command_built_expr(node: GenericNode, env: _GoEnv, fmt_names: Set[str]) -> bool:
    """``fmt.Sprintf`` or ``+`` whose result depends on a non-constant part."""
    kind = _ts(node)
    if kind == "parenthesized_expression":
        named = _named(node)
        return len(named) == 1 and _go_command_built_expr(named[0], env, fmt_names)
    if kind == "binary_expression" and _concat_builds_string(node):
        return any(
            _go_nonconst(part, env) for part in _go_plus_parts(node) if not _is_literal(part)
        )
    if kind == "call_expression" and _go_is_sprintf(node, fmt_names):
        return any(_go_nonconst(arg, env) for arg in _args(node)[1:])
    return False


def _go_concat_prefix(parts: List[GenericNode]) -> Optional[str]:
    """DML text of a ``+`` chain, or None when the chain is not a SQL value build."""
    if not parts:
        return None
    first = _go_string_literal(parts[0])
    if first is None or not _go_dml_text(first):
        return None
    joined = "".join(_go_string_literal(part) or "" for part in parts)
    if not _go_dml_text(joined):
        return None
    return first


def _go_concat_has_value(parts: List[GenericNode], before: str, env: _GoEnv) -> bool:
    for part in parts:
        literal = _go_string_literal(part)
        if literal is not None:
            before += literal
            continue
        if _go_hole_is_value(before) and _go_nonconst(part, env):
            return True
    return False


def _go_concat_sql(node: GenericNode, env: _GoEnv) -> bool:
    parts = _go_plus_parts(node)
    first = _go_concat_prefix(parts)
    if first is None:
        return False
    return _go_concat_has_value(parts[1:], first, env)


def _go_sprintf_format(
    node: GenericNode, fmt_names: Set[str]
) -> Optional[Tuple[str, List[GenericNode]]]:
    if not _go_is_sprintf(node, fmt_names):
        return None
    args = _args(node)
    if len(args) < 2:
        return None
    fmt = _go_string_literal(args[0])
    if fmt is None or not _go_dml_text(fmt):
        return None
    return fmt, args


def _go_sprintf_slot_risky(
    fmt: str, args: List[GenericNode], verb: str, arg_index: int, start: int, env: _GoEnv
) -> bool:
    if verb not in _GO_STRING_VERBS or not _go_hole_is_value(fmt[:start]):
        return False
    if arg_index < 0 or arg_index >= len(args) - 1:
        return False
    return _go_nonconst(args[arg_index + 1], env)


def _go_sprintf_sql(node: GenericNode, env: _GoEnv, fmt_names: Set[str]) -> bool:
    parsed = _go_sprintf_format(node, fmt_names)
    if parsed is None:
        return False
    fmt, args = parsed
    slots = _go_format_slots(fmt)
    if slots is None:
        return False
    return any(
        _go_sprintf_slot_risky(fmt, args, verb, arg_index, start, env)
        for verb, arg_index, start in slots
    )


def _go_sql_expr(node: GenericNode, env: _GoEnv, fmt_names: Set[str]) -> bool:
    kind = _ts(node)
    if kind == "parenthesized_expression":
        named = _named(node)
        return len(named) == 1 and _go_sql_risky(named[0], env, fmt_names)
    if kind == "binary_expression":
        return _go_concat_sql(node, env)
    if kind == "call_expression":
        return _go_sprintf_sql(node, env, fmt_names)
    return False


def _go_sql_risky(node: GenericNode, env: _GoEnv, fmt_names: Set[str]) -> bool:
    if _ts(node) == "parenthesized_expression":
        named = _named(node)
        return len(named) == 1 and _go_sql_risky(named[0], env, fmt_names)
    if _ts(node) == "identifier":
        fact = env.get(node.text.strip())
        return bool(fact and fact.sql)
    return _go_sql_expr(node, env, fmt_names)


def _go_fact(expr: GenericNode, env: _GoEnv, fmt_names: Set[str]) -> _GoFact:
    kind = _ts(expr)
    if kind == "identifier":
        return env.get(expr.text.strip(), _GoFact())
    if kind == "parenthesized_expression":
        named = _named(expr)
        if len(named) == 1:
            return _go_fact(named[0], env, fmt_names)
        return _GoFact()
    if _is_literal(expr):
        return _GoFact(constant=True)
    return _GoFact(
        built=_go_command_built_expr(expr, env, fmt_names),
        sql=_go_sql_expr(expr, env, fmt_names),
    )


def _go_bind_pair(env: _GoEnv, left: GenericNode, right: GenericNode, fmt_names: Set[str]) -> None:
    if _ts(left) != "identifier":
        return
    name = left.text.strip()
    if name and name != "_":
        env[name] = _go_fact(right, env, fmt_names)


def _go_bind_lists(env: _GoEnv, node: GenericNode, fmt_names: Set[str]) -> None:
    lists = [child for child in _named(node) if _ts(child) == "expression_list"]
    if len(lists) != 2:
        return
    left, right = _named(lists[0]), _named(lists[1])
    if len(left) != len(right):
        return
    for lhs, rhs in zip(left, right):
        _go_bind_pair(env, lhs, rhs, fmt_names)


def _go_bind_spec(env: _GoEnv, node: GenericNode, fmt_names: Set[str]) -> None:
    names = [child for child in _named(node) if _ts(child) == "identifier"]
    values: List[GenericNode] = []
    for child in _named(node):
        if _ts(child) == "expression_list":
            values = _named(child)
    if len(names) == len(values):
        for lhs, rhs in zip(names, values):
            _go_bind_pair(env, lhs, rhs, fmt_names)


def _go_shell_risky(arg: GenericNode, env: _GoEnv, fmt_names: Set[str]) -> bool:
    if _ts(arg) == "parenthesized_expression":
        named = _named(arg)
        return len(named) == 1 and _go_shell_risky(named[0], env, fmt_names)
    if _ts(arg) == "identifier":
        fact = env.get(arg.text.strip())
        return bool(fact and fact.built)
    return _go_command_built_expr(arg, env, fmt_names)


def _go_shell(
    ctx: _Ctx,
    node: GenericNode,
    func: str,
    args: List[GenericNode],
    env: _GoEnv,
    fmt_names: Set[str],
) -> None:
    rest = args[1:] if func == "exec.CommandContext" else args
    if len(rest) < 3 or _string_value(rest[0]) not in _SHELLS:
        return
    risky = _string_value(rest[1]) == "-c" and any(
        _go_shell_risky(arg, env, fmt_names) for arg in rest[2:]
    )
    if not risky:
        return
    ctx.add(
        node,
        "GO001",
        AnalysisIssueType.COMMAND_INJECTION,
        AnalysisIssueSeverity.HIGH,
        "Shell command built from strings and run with -c",
        "Call the program directly with exec.Command(name, args...).",
        "CWE-78",
    )


def _go_sql_sink(
    ctx: _Ctx,
    node: GenericNode,
    func: str,
    args: List[GenericNode],
    env: _GoEnv,
    fmt_names: Set[str],
) -> None:
    index = _GO_SQL_ARG.get(func.rsplit(".", 1)[-1])
    if index is None or index >= len(args) or not _go_sql_risky(args[index], env, fmt_names):
        return
    ctx.add(
        node,
        "GO005",
        AnalysisIssueType.SQL_INJECTION_RISK,
        AnalysisIssueSeverity.HIGH,
        "SQL value built from a non-constant argument",
        "Pass the value as a placeholder (? or $1) and keep the SQL text fixed.",
        "CWE-89",
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


def _go_call(
    ctx: _Ctx, node: GenericNode, imports: Dict[str, str], env: _GoEnv, fmt_names: Set[str]
) -> None:
    parts = _named(node)
    if not parts:
        return
    func = parts[0].text.replace(" ", "")
    args = _args(node)
    if func in ("exec.Command", "exec.CommandContext"):
        _go_shell(ctx, node, func, args, env, fmt_names)
        return
    if func.rsplit(".", 1)[-1] in _GO_SQL_ARG:
        _go_sql_sink(ctx, node, func, args, env, fmt_names)
        return
    if _ts(parts[0]) == "selector_expression" and "." in func:
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


def _go_children(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    for child in node.children:
        _go_visit(ctx, child, env, imports, fmt_names)


def _go_visit_scoped(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    _go_children(ctx, node, dict(env), imports, fmt_names)


def _go_visit_assign(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    _go_children(ctx, node, env, imports, fmt_names)
    _go_bind_lists(env, node, fmt_names)


def _go_visit_spec(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    _go_children(ctx, node, env, imports, fmt_names)
    _go_bind_spec(env, node, fmt_names)


def _go_visit_call(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    _go_call(ctx, node, imports, env, fmt_names)
    _go_children(ctx, node, env, imports, fmt_names)


def _go_visit_keyed(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    _go_keyed(ctx, node)
    _go_children(ctx, node, env, imports, fmt_names)


def _go_visit_function(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    """Each function starts empty: only assignments inside it are followed."""
    for child in node.children:
        if _ts(child) == "block":
            _go_visit(ctx, child, {}, imports, fmt_names)
        else:
            _go_visit(ctx, child, env, imports, fmt_names)


def _go_for_clause(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    """Bind the init, not the post statement (that runs after the body)."""
    named = _named(node)
    post = len(named) == 3 and _ts(named[2]) in ("assignment_statement", "inc_statement")
    if not post:
        _go_children(ctx, node, env, imports, fmt_names)
        return
    _go_visit(ctx, named[0], env, imports, fmt_names)
    _go_visit(ctx, named[1], env, imports, fmt_names)
    saved = dict(env)
    _go_visit(ctx, named[2], env, imports, fmt_names)
    env.clear()
    env.update(saved)


def _go_visit_for(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    inner = dict(env)
    for child in node.children:
        if _ts(child) == "for_clause":
            _go_for_clause(ctx, child, inner, imports, fmt_names)
        else:
            _go_visit(ctx, child, inner, imports, fmt_names)


_GO_VISIT: Dict[str, _GoVisit] = {}


def _go_visit(
    ctx: _Ctx, node: GenericNode, env: _GoEnv, imports: Dict[str, str], fmt_names: Set[str]
) -> None:
    handler = _GO_VISIT.get(_ts(node))
    if handler is not None:
        handler(ctx, node, env, imports, fmt_names)
        return
    _go_children(ctx, node, env, imports, fmt_names)


def _check_go(ctx: _Ctx, root: GenericNode) -> None:
    _go_visit(ctx, root, {}, _go_imports(root), _go_fmt_aliases(root))


for _go_kind in _GO_SCOPE:
    _GO_VISIT[_go_kind] = _go_visit_scoped
_GO_VISIT["for_statement"] = _go_visit_for
_GO_VISIT["function_declaration"] = _go_visit_function
_GO_VISIT["method_declaration"] = _go_visit_function
_GO_VISIT["short_var_declaration"] = _go_visit_assign
_GO_VISIT["assignment_statement"] = _go_visit_assign
_GO_VISIT["var_spec"] = _go_visit_spec
_GO_VISIT["const_spec"] = _go_visit_spec
_GO_VISIT["call_expression"] = _go_visit_call
_GO_VISIT["keyed_element"] = _go_visit_keyed


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
