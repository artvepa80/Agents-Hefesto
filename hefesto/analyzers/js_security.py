"""Experimental JavaScript and TypeScript security rules (``--experimental js-security``).

The flag name and the ``XSS_RISK`` issue type are provisional.

Rules read the tree-sitter syntax tree, so text inside strings and comments
does not match. Sanitizers are recognised by the module they are imported
from (``dompurify``, ``isomorphic-dompurify``, ``sanitize-html``), not by the
local name. A function named ``sanitize`` that is not imported from one of
those modules is still reported.

* JSX001 ``dangerouslySetInnerHTML`` whose HTML is not a constant and not a
  call of an imported sanitizer. A call of a function in the same file is
  reported only when that function returns ``{ __html: ... }`` and the value
  is itself unsafe.
* JSX002 ``href`` or ``src`` whose URL is a ``javascript:`` literal or template
  (trim, then lowercase). A non-literal value is not reported.
* JS002 ``innerHTML`` / ``outerHTML`` assignment, ``insertAdjacentHTML``, and
  ``document.write`` / ``document.writeln`` with HTML that is not a constant
  and not an imported sanitizer.
* JS001 ``exec`` from ``shelljs`` (default import, ``import * as``,
  ``import { exec }``, ``require``, and a renamed export) when the command is
  a template with a substitution or a concatenation that is not all constant.
  A string, a template with no substitution, and a bare identifier are not
  reported. Issue type ``COMMAND_INJECTION`` (CWE-78).

Off unless the experimental flag is on. Test and example paths are skipped.
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Set, Tuple

from hefesto.analyzers.security import is_test_or_example_path
from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST, GenericNode

_SANITIZER_OBJECTS = frozenset({"dompurify", "isomorphic-dompurify"})
_SANITIZER_FUNCTIONS = frozenset({"sanitize-html"})
_SHELLJS = "shelljs"
_HTML_PROPS = frozenset({"innerHTML", "outerHTML"})
_WRITE = frozenset({"write", "writeln"})
_LINK_ATTRS = frozenset({"href", "src"})
_UNWRAP = frozenset(
    {
        "parenthesized_expression",
        "as_expression",
        "satisfies_expression",
        "non_null_expression",
        "type_assertion",
    }
)
_NESTED_FN = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "arrow_function",
        "function",
        "method_definition",
    }
)
_SKIP_FN_CHILD = frozenset(
    {
        "formal_parameters",
        "type_parameters",
        "type_annotation",
        "statement_block",
        "identifier",
    }
)


def _ts(node: GenericNode) -> str:
    return str(node.metadata.get("treesitter_type", ""))


def _named(node: GenericNode) -> List[GenericNode]:
    return [c for c in node.children if c.metadata.get("named", True) and "comment" not in _ts(c)]


def _text(node: GenericNode) -> str:
    return node.text


def _string_content(node: GenericNode) -> str:
    parts = [c.text for c in node.children if _ts(c) == "string_fragment"]
    if parts:
        return "".join(parts)
    text = node.text
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'`":
        return text[1:-1]
    return text


def _unwrap(node: Optional[GenericNode]) -> Optional[GenericNode]:
    seen = 0
    while node is not None and _ts(node) in _UNWRAP and seen < 8:
        kids = _named(node)
        if not kids:
            break
        node = kids[-1] if _ts(node) == "type_assertion" else kids[0]
        seen += 1
    return node


def _prop_name(node: GenericNode) -> str:
    kind = _ts(node)
    if kind in ("property_identifier", "identifier", "shorthand_property_identifier_pattern"):
        return node.text
    if kind == "string":
        return _string_content(node)
    return ""


def _object_html(node: GenericNode) -> Optional[GenericNode]:
    """The ``__html`` value of an object literal, if it has one."""
    for child in _named(node):
        if _ts(child) != "pair":
            continue
        bits = _named(child)
        if not bits or _prop_name(bits[0]) != "__html":
            continue
        return bits[-1]
    return None


def _walk_body(fn: GenericNode) -> Iterator[GenericNode]:
    """Nodes inside ``fn`` except those that belong to a nested function."""
    stack = list(reversed(fn.children))
    while stack:
        current = stack.pop()
        if _ts(current) in _NESTED_FN:
            continue
        yield current
        stack.extend(reversed(current.children))


def _html_returns(fn: GenericNode) -> List[GenericNode]:
    """``__html`` values returned by ``fn`` (block returns and expression body)."""
    found: List[GenericNode] = []

    def consider(expr: Optional[GenericNode]) -> None:
        expr = _unwrap(expr)
        if expr is not None and _ts(expr) == "object":
            html = _object_html(expr)
            if html is not None:
                found.append(html)

    for node in _walk_body(fn):
        if _ts(node) == "return_statement":
            kids = _named(node)
            if kids:
                consider(kids[-1])
    for child in _named(fn):
        if _ts(child) not in _SKIP_FN_CHILD:
            consider(child)
    return found


class _Bindings:
    def __init__(self) -> None:
        self.sanitizer_fns: Set[str] = set()
        self.sanitizer_objects: Set[str] = set()
        self.shell_objects: Set[str] = set()
        self.shell_execs: Set[str] = set()
        self.functions: Dict[str, List[GenericNode]] = {}

    def _bind(self, module: str, local: str, exported: Optional[str]) -> None:
        if not local:
            return
        if module in _SANITIZER_OBJECTS:
            if exported is None:
                self.sanitizer_objects.add(local)
            elif exported == "sanitize":
                self.sanitizer_fns.add(local)
        elif module in _SANITIZER_FUNCTIONS and (
            exported is None or exported in ("sanitize", "default")
        ):
            self.sanitizer_fns.add(local)
        elif module == _SHELLJS:
            if exported is None or exported == "default":
                self.shell_objects.add(local)
            elif exported == "exec":
                self.shell_execs.add(local)

    def import_statement(self, node: GenericNode) -> None:
        if any(_ts(child) == "type" for child in node.children):
            return
        source = next((child for child in node.children if _ts(child) == "string"), None)
        clause = next((child for child in node.children if _ts(child) == "import_clause"), None)
        if source is None or clause is None:
            return
        module = _string_content(source)
        for child in clause.children:
            kind = _ts(child)
            if kind == "identifier":
                self._bind(module, _text(child), None)
            elif kind == "namespace_import":
                names = [c for c in _named(child) if _ts(c) == "identifier"]
                if names:
                    self._bind(module, _text(names[-1]), None)
            elif kind == "named_imports":
                for spec in _named(child):
                    if _ts(spec) != "import_specifier" or any(
                        _ts(c) == "type" for c in spec.children
                    ):
                        continue
                    names = [c for c in spec.children if _ts(c) == "identifier"]
                    if names:
                        self._bind(module, _text(names[-1]), _text(names[0]))

    def declarator(self, node: GenericNode) -> None:
        kids = _named(node)
        if len(kids) < 2:
            return
        target, value = kids[0], kids[1]
        module = _require_module(value)
        if module:
            if _ts(target) == "identifier":
                self._bind(module, _text(target), None)
            elif _ts(target) == "object_pattern":
                for exported, local in _pattern_entries(target):
                    self._bind(module, local, exported)
            return
        fn = value if _ts(value) in _NESTED_FN else _unwrap(value)
        if _ts(target) == "identifier" and fn is not None and _ts(fn) in _NESTED_FN:
            self.functions.setdefault(_text(target), []).extend(_html_returns(fn))

    def function_decl(self, node: GenericNode) -> None:
        ident = next((c for c in _named(node) if _ts(c) == "identifier"), None)
        if ident is not None:
            self.functions.setdefault(_text(ident), []).extend(_html_returns(node))


def _require_module(node: GenericNode) -> Optional[str]:
    if _ts(node) != "call_expression":
        return None
    parts = _named(node)
    if len(parts) < 2 or _text(parts[0]) != "require" or _ts(parts[1]) != "arguments":
        return None
    args = _named(parts[1])
    if not args or _ts(args[0]) != "string":
        return None
    return _string_content(args[0])


def _pattern_entries(pattern: GenericNode) -> Iterator[Tuple[str, str]]:
    for entry in _named(pattern):
        kind = _ts(entry)
        if kind == "shorthand_property_identifier_pattern":
            name = _text(entry)
            yield name, name
        elif kind in ("pair_pattern", "pair"):
            bits = _named(entry)
            if len(bits) >= 2:
                yield _prop_name(bits[0]), _text(bits[-1])


def _is_constant(node: Optional[GenericNode]) -> bool:
    node = _unwrap(node)
    if node is None:
        return False
    kind = _ts(node)
    if kind == "string":
        return True
    if kind == "template_string":
        return not any(_ts(child) == "template_substitution" for child in node.children)
    if kind in ("number", "true", "false", "null", "undefined"):
        return True
    if kind == "binary_expression" and any(child.text == "+" for child in node.children):
        parts = _named(node)
        return bool(parts) and all(_is_constant(part) for part in parts)
    if kind in ("ternary_expression", "conditional_expression"):
        parts = _named(node)
        return len(parts) >= 3 and _is_constant(parts[-2]) and _is_constant(parts[-1])
    return False


def _is_sanitizer_call(node: Optional[GenericNode], bindings: _Bindings) -> bool:
    node = _unwrap(node)
    if node is None or _ts(node) != "call_expression":
        return False
    kids = _named(node)
    if not kids:
        return False
    callee = kids[0]
    if _ts(callee) == "identifier":
        return _text(callee) in bindings.sanitizer_fns
    if _ts(callee) == "member_expression":
        parts = _named(callee)
        if (
            len(parts) == 2
            and _ts(parts[0]) == "identifier"
            and _text(parts[1]) == "sanitize"
            and _text(parts[0]) in bindings.sanitizer_objects
        ):
            return True
    return False


def _unsafe_html(node: Optional[GenericNode], bindings: _Bindings) -> bool:
    """True when ``node`` is HTML that is neither a constant nor an imported sanitizer."""
    if _is_sanitizer_call(node, bindings) or _is_constant(node):
        return False
    return _unwrap(node) is not None


def _unsafe_prop(node: Optional[GenericNode], bindings: _Bindings) -> bool:
    """``dangerouslySetInnerHTML`` value: object ``__html``, or a same-file helper."""
    node = _unwrap(node)
    if node is None:
        return False
    if _ts(node) == "object":
        html = _object_html(node)
        return html is not None and _unsafe_html(html, bindings)
    if _ts(node) != "call_expression":
        return False
    kids = _named(node)
    if not kids or _ts(kids[0]) != "identifier":
        return False
    htmls = bindings.functions.get(_text(kids[0]))
    if not htmls:
        return False
    return any(_unsafe_html(html, bindings) for html in htmls)


def _javascript_url(node: Optional[GenericNode]) -> bool:
    """Literal or template whose static prefix is ``javascript:`` after trim and lowercase."""
    node = _unwrap(node)
    if node is None:
        return False
    kind = _ts(node)
    if kind == "string":
        text = _string_content(node)
    elif kind == "template_string":
        parts: List[str] = []
        for child in node.children:
            if _ts(child) == "template_substitution":
                break
            if _ts(child) == "string_fragment":
                parts.append(child.text)
        text = "".join(parts)
    else:
        return False
    return text.strip().lower().startswith("javascript:")


def _member_prop(node: GenericNode) -> Optional[str]:
    if _ts(node) != "member_expression":
        return None
    parts = _named(node)
    if len(parts) == 2 and _ts(parts[1]) in ("property_identifier", "identifier"):
        return _text(parts[1])
    return None


def _attribute_value(node: GenericNode) -> Tuple[str, Optional[GenericNode]]:
    name = ""
    value: Optional[GenericNode] = None
    for child in _named(node):
        if not name and _ts(child) in ("property_identifier", "identifier"):
            name = _text(child)
            continue
        if _ts(child) == "jsx_expression":
            inner = _named(child)
            value = inner[-1] if inner else None
        else:
            value = child
    return name, value


class _Report:
    def __init__(self, file_path: str, bindings: _Bindings) -> None:
        self.file_path = file_path
        self.bindings = bindings
        self.issues: List[AnalysisIssue] = []
        self.seen: Set[Tuple[str, int, int]] = set()

    def add(
        self,
        node: GenericNode,
        rule_id: str,
        message: str,
        suggestion: str,
        issue_type: AnalysisIssueType = AnalysisIssueType.XSS_RISK,
        cwe: str = "CWE-79",
    ) -> None:
        key = (rule_id, node.line_start, node.column_start)
        if key in self.seen:
            return
        self.seen.add(key)
        self.issues.append(
            AnalysisIssue(
                file_path=self.file_path,
                line=node.line_start,
                column=node.column_start,
                issue_type=issue_type,
                severity=AnalysisIssueSeverity.HIGH,
                message=message,
                suggestion=suggestion,
                code_snippet=node.text.splitlines()[0][:200] if node.text else None,
                metadata={"language": "javascript", "cwe": cwe},
                engine="internal:security",
                rule_id=rule_id,
                source="code",
            )
        )


_HTML_SUGGESTION = (
    "Pass a constant string, or sanitize with a value imported from dompurify, "
    "isomorphic-dompurify, or sanitize-html."
)


def _check_attribute(report: _Report, node: GenericNode) -> None:
    name, value = _attribute_value(node)
    if value is None:
        return
    if name == "dangerouslySetInnerHTML" and _unsafe_prop(value, report.bindings):
        report.add(
            node,
            "JSX001",
            "Unsanitized HTML passed to dangerouslySetInnerHTML",
            _HTML_SUGGESTION,
        )
    elif name in _LINK_ATTRS and _javascript_url(value):
        report.add(
            node,
            "JSX002",
            "Link href or src uses a javascript: URL",
            "Use an http(s) URL, or a button with an event handler.",
        )


def _check_assignment(report: _Report, node: GenericNode) -> None:
    kids = _named(node)
    if len(kids) < 2:
        return
    prop = _member_prop(kids[0])
    if prop in _HTML_PROPS and _unsafe_html(kids[-1], report.bindings):
        report.add(
            node,
            "JS002",
            f"Unsanitized HTML assigned to {prop}",
            _HTML_SUGGESTION,
        )


def _dynamic_command(node: Optional[GenericNode]) -> bool:
    """A command built in this expression: a template substitution, or ``+`` with a variable."""
    node = _unwrap(node)
    if node is None:
        return False
    kind = _ts(node)
    if kind == "template_string":
        return any(_ts(child) == "template_substitution" for child in node.children)
    if kind == "binary_expression" and any(child.text == "+" for child in node.children):
        return not _is_constant(node)
    return False


def _is_shell_exec(callee: GenericNode, bindings: _Bindings) -> bool:
    if _ts(callee) == "identifier":
        return _text(callee) in bindings.shell_execs
    if _ts(callee) != "member_expression":
        return False
    parts = _named(callee)
    return (
        len(parts) == 2
        and _ts(parts[0]) == "identifier"
        and _text(parts[1]) == "exec"
        and _text(parts[0]) in bindings.shell_objects
    )


def _check_call(report: _Report, node: GenericNode) -> None:
    kids = _named(node)
    callee = kids[0] if kids else None
    arguments = next((child for child in kids if _ts(child) == "arguments"), None)
    if callee is None or arguments is None:
        return
    args = _named(arguments)
    if args and _is_shell_exec(callee, report.bindings) and _dynamic_command(args[0]):
        report.add(
            node,
            "JS001",
            "shelljs exec runs a command built from a template or concatenation",
            "Keep the command a constant, or pass arguments separately from the program name.",
            issue_type=AnalysisIssueType.COMMAND_INJECTION,
            cwe="CWE-78",
        )
    if _ts(callee) != "member_expression":
        return
    parts = _named(callee)
    if len(parts) != 2:
        return
    prop = _text(parts[1])
    if prop == "insertAdjacentHTML" and len(args) >= 2 and _unsafe_html(args[1], report.bindings):
        report.add(
            node,
            "JS002",
            "Unsanitized HTML passed to insertAdjacentHTML",
            _HTML_SUGGESTION,
        )
    elif (
        prop in _WRITE
        and _ts(parts[0]) == "identifier"
        and _text(parts[0]) == "document"
        and args
        and _unsafe_html(args[0], report.bindings)
    ):
        report.add(
            node,
            "JS002",
            f"Unsanitized HTML passed to document.{prop}",
            _HTML_SUGGESTION,
        )


def find_js_security_issues(tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
    """XSS findings for one JavaScript or TypeScript tree. The caller gates the flag."""
    bindings = _Bindings()
    nodes = tree.walk()
    for node in nodes:
        kind = _ts(node)
        if kind == "import_statement":
            bindings.import_statement(node)
        elif kind == "variable_declarator":
            bindings.declarator(node)
        elif kind == "function_declaration":
            bindings.function_decl(node)
    report = _Report(file_path, bindings)
    for node in nodes:
        kind = _ts(node)
        if kind == "jsx_attribute":
            _check_attribute(report, node)
        elif kind in ("assignment_expression", "augmented_assignment_expression"):
            _check_assignment(report, node)
        elif kind == "call_expression":
            _check_call(report, node)
    return report.issues


class JsSecurityAnalyzer:
    """JavaScript and TypeScript security rules. Off unless ``js_rules`` is set."""

    # ``--experimental js-security``: set by the engine; off by default.
    js_rules = False

    def analyze(self, tree: GenericAST, file_path: str, code: str) -> List[AnalysisIssue]:
        del code
        if not self.js_rules or getattr(tree, "language", None) not in ("javascript", "typescript"):
            return []
        if is_test_or_example_path(file_path):
            return []
        return find_js_security_issues(tree, file_path)
