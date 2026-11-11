"""Experimental JavaScript and TypeScript security rules (``--experimental js-security``).

Rules read the tree-sitter syntax tree, so text inside strings and comments
does not match. Sanitizers are recognised by the module they are imported
from (``dompurify``, ``isomorphic-dompurify``, ``sanitize-html``), not by the
local name. A function named ``sanitize`` that is not imported from one of
those modules is still reported. ``createDOMPurify(...)`` from one of the
DOMPurify modules is a sanitizer object. ``const clean = DOMPurify.sanitize(html)``
counts at a later ``__html: clean``. A second assignment does not.

* JSX001 ``dangerouslySetInnerHTML`` whose HTML is not a constant and not a
  call of an imported sanitizer. A call of a function in the same file is
  reported only when that function returns ``{ __html: ... }`` and the value
  is itself unsafe.
* JSX002 ``href``, ``src``, ``action``, or ``xlinkHref`` (including
  ``xlink:href``) whose URL is a ``javascript:`` literal or template (trim,
  then lowercase). ``javascript:void(0)``, ``javascript:void(0);``, and
  ``javascript:;`` are not reported. A template that substitutes the rest of
  the URL is reported. A non-literal value is not reported.
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
_LINK_ATTRS = frozenset({"href", "src", "action", "xlinkHref"})
_NO_OP_JS_URLS = frozenset(
    {
        "javascript:void(0)",
        "javascript:void(0);",
        "javascript:;",
    }
)
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


def _consider_html(expr: Optional[GenericNode], found: List[GenericNode]) -> None:
    expr = _unwrap(expr)
    if expr is None or _ts(expr) != "object":
        return
    html = _object_html(expr)
    if html is not None:
        found.append(html)


def _returned_html(fn: GenericNode, found: List[GenericNode]) -> None:
    for node in _walk_body(fn):
        if _ts(node) != "return_statement":
            continue
        kids = _named(node)
        if kids:
            _consider_html(kids[-1], found)


def _expression_html(fn: GenericNode, found: List[GenericNode]) -> None:
    for child in _named(fn):
        if _ts(child) not in _SKIP_FN_CHILD:
            _consider_html(child, found)


def _html_returns(fn: GenericNode) -> List[GenericNode]:
    """``__html`` values returned by ``fn`` (block returns and expression body)."""
    found: List[GenericNode] = []
    _returned_html(fn, found)
    _expression_html(fn, found)
    return found


class _Bindings:
    def __init__(self) -> None:
        self.sanitizer_fns: Set[str] = set()
        self.sanitizer_objects: Set[str] = set()
        self.sanitizer_factories: Set[str] = set()
        self.sanitized_values: Set[str] = set()
        self.shell_objects: Set[str] = set()
        self.shell_execs: Set[str] = set()
        self.functions: Dict[str, List[GenericNode]] = {}

    def _bind(self, module: str, local: str, exported: Optional[str]) -> None:
        if not local:
            return
        if module in _SANITIZER_OBJECTS:
            self._bind_sanitizer_object(local, exported)
        elif module in _SANITIZER_FUNCTIONS:
            self._bind_sanitize_html(local, exported)
        elif module == _SHELLJS:
            self._bind_shelljs(local, exported)

    def _bind_sanitizer_object(self, local: str, exported: Optional[str]) -> None:
        if exported is None:
            self.sanitizer_objects.add(local)
        elif exported == "sanitize":
            self.sanitizer_fns.add(local)
        elif exported == "createDOMPurify":
            self.sanitizer_factories.add(local)

    def _bind_sanitize_html(self, local: str, exported: Optional[str]) -> None:
        if exported is None or exported in ("sanitize", "default"):
            self.sanitizer_fns.add(local)

    def _bind_shelljs(self, local: str, exported: Optional[str]) -> None:
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
            self._bind_import_child(module, child)

    def _bind_import_child(self, module: str, child: GenericNode) -> None:
        kind = _ts(child)
        if kind == "identifier":
            self._bind(module, _text(child), None)
        elif kind == "namespace_import":
            self._bind_namespace(module, child)
        elif kind == "named_imports":
            self._bind_named(module, child)

    def _bind_namespace(self, module: str, child: GenericNode) -> None:
        names = [c for c in _named(child) if _ts(c) == "identifier"]
        if names:
            self._bind(module, _text(names[-1]), None)

    def _bind_named(self, module: str, child: GenericNode) -> None:
        for spec in _named(child):
            self._bind_specifier(module, spec)

    def _bind_specifier(self, module: str, spec: GenericNode) -> None:
        if _ts(spec) != "import_specifier":
            return
        if any(_ts(child) == "type" for child in spec.children):
            return
        names = [child for child in spec.children if _ts(child) == "identifier"]
        if names:
            self._bind(module, _text(names[-1]), _text(names[0]))

    def declarator(self, node: GenericNode) -> None:
        kids = _named(node)
        if len(kids) < 2:
            return
        target, value = kids[0], kids[1]
        module = _require_module(value)
        if module:
            self._bind_require(target, module)
            return
        if self._bind_sanitized_value(target, value):
            return
        self._bind_local_function(target, value)

    def _bind_sanitized_value(self, target: GenericNode, value: GenericNode) -> bool:
        """One assignment: a sanitizer call, or a ``createDOMPurify(...)`` instance."""
        if _ts(target) != "identifier":
            return False
        name = _text(target)
        if _is_sanitizer_call(value, self):
            self.sanitized_values.add(name)
            return True
        if _is_factory_call(value, self):
            self.sanitizer_objects.add(name)
            return True
        return False

    def _bind_require(self, target: GenericNode, module: str) -> None:
        if _ts(target) == "identifier":
            self._bind(module, _text(target), None)
            return
        if _ts(target) != "object_pattern":
            return
        for exported, local in _pattern_entries(target):
            self._bind(module, local, exported)

    def _bind_local_function(self, target: GenericNode, value: GenericNode) -> None:
        fn = value if _ts(value) in _NESTED_FN else _unwrap(value)
        if _ts(target) != "identifier" or fn is None or _ts(fn) not in _NESTED_FN:
            return
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
    if kind in ("string", "number", "true", "false", "null", "undefined"):
        return True
    if kind == "template_string":
        return _template_is_constant(node)
    return _operator_is_constant(node, kind)


def _template_is_constant(node: GenericNode) -> bool:
    return not any(_ts(child) == "template_substitution" for child in node.children)


def _operator_is_constant(node: GenericNode, kind: str) -> bool:
    if kind == "binary_expression" and any(child.text == "+" for child in node.children):
        parts = _named(node)
        return bool(parts) and all(_is_constant(part) for part in parts)
    if kind not in ("ternary_expression", "conditional_expression"):
        return False
    parts = _named(node)
    return len(parts) >= 3 and _is_constant(parts[-2]) and _is_constant(parts[-1])


def _is_sanitizer_call(node: Optional[GenericNode], bindings: _Bindings) -> bool:
    node = _unwrap(node)
    if node is None or _ts(node) != "call_expression":
        return False
    kids = _named(node)
    if not kids:
        return False
    return _callee_is_sanitizer(kids[0], bindings)


def _callee_is_sanitizer(callee: GenericNode, bindings: _Bindings) -> bool:
    if _ts(callee) == "identifier":
        return _text(callee) in bindings.sanitizer_fns
    if _ts(callee) != "member_expression":
        return False
    return _member_is_sanitizer(callee, bindings)


def _member_is_sanitizer(callee: GenericNode, bindings: _Bindings) -> bool:
    parts = _named(callee)
    if len(parts) != 2 or _ts(parts[0]) != "identifier" or _text(parts[1]) != "sanitize":
        return False
    return _text(parts[0]) in bindings.sanitizer_objects


def _call_callee(node: Optional[GenericNode]) -> Optional[GenericNode]:
    node = _unwrap(node)
    if node is None or _ts(node) != "call_expression":
        return None
    kids = _named(node)
    if not kids:
        return None
    return kids[0]


def _is_factory_call(node: Optional[GenericNode], bindings: _Bindings) -> bool:
    """``createDOMPurify(...)`` or a call of the default DOMPurify export."""
    callee = _call_callee(node)
    if callee is None or _ts(callee) != "identifier":
        return False
    name = _text(callee)
    return name in bindings.sanitizer_factories or name in bindings.sanitizer_objects


def _is_sanitized_name(node: Optional[GenericNode], bindings: _Bindings) -> bool:
    """An identifier assigned in one step from a sanitizer call."""
    node = _unwrap(node)
    if node is None or _ts(node) != "identifier":
        return False
    return _text(node) in bindings.sanitized_values


def _unsafe_html(node: Optional[GenericNode], bindings: _Bindings) -> bool:
    """True when ``node`` is HTML that is neither a constant nor an imported sanitizer."""
    if _is_sanitizer_call(node, bindings) or _is_constant(node):
        return False
    if _is_sanitized_name(node, bindings):
        return False
    return _unwrap(node) is not None


def _unsafe_prop(node: Optional[GenericNode], bindings: _Bindings) -> bool:
    """``dangerouslySetInnerHTML`` value: object ``__html``, or a same-file helper."""
    node = _unwrap(node)
    if node is None:
        return False
    if _ts(node) == "object":
        return _object_html_unsafe(node, bindings)
    return _helper_call_unsafe(node, bindings)


def _object_html_unsafe(node: GenericNode, bindings: _Bindings) -> bool:
    html = _object_html(node)
    return html is not None and _unsafe_html(html, bindings)


def _helper_call_unsafe(node: GenericNode, bindings: _Bindings) -> bool:
    if _ts(node) != "call_expression":
        return False
    kids = _named(node)
    if not kids or _ts(kids[0]) != "identifier":
        return False
    htmls = bindings.functions.get(_text(kids[0]))
    if not htmls:
        return False
    return any(_unsafe_html(html, bindings) for html in htmls)


def _static_js_text(node: Optional[GenericNode]) -> Optional[str]:
    """String or template text up to the first substitution."""
    if node is None:
        return None
    kind = _ts(node)
    if kind == "string":
        return _string_content(node)
    if kind == "template_string":
        return _template_prefix(node)
    return None


def _template_builds_url(node: GenericNode) -> bool:
    return any(_ts(child) == "template_substitution" for child in node.children)


def _normalized_js_url(node: Optional[GenericNode]) -> Optional[str]:
    text = _static_js_text(_unwrap(node))
    if text is None:
        return None
    normalized = text.strip().lower()
    if normalized.startswith("javascript:"):
        return normalized
    return None


def _built_javascript_url(node: Optional[GenericNode]) -> bool:
    node = _unwrap(node)
    if node is None or _ts(node) != "template_string":
        return False
    return _template_builds_url(node)


def _javascript_url(node: Optional[GenericNode]) -> bool:
    """``javascript:`` literal or template, except the three no-op spellings."""
    normalized = _normalized_js_url(node)
    if normalized is None:
        return False
    if _built_javascript_url(node):
        return True
    return normalized not in _NO_OP_JS_URLS


def _template_prefix(node: GenericNode) -> str:
    parts: List[str] = []
    for child in node.children:
        if _ts(child) == "template_substitution":
            break
        if _ts(child) == "string_fragment":
            parts.append(child.text)
    return "".join(parts)


def _namespace_attr(node: GenericNode) -> str:
    parts = [_text(child) for child in _named(node) if _ts(child) == "identifier"]
    if parts == ["xlink", "href"]:
        return "xlinkHref"
    return ""


def _attr_name(node: GenericNode) -> str:
    kind = _ts(node)
    if kind in ("property_identifier", "identifier"):
        return _text(node)
    if kind == "jsx_namespace_name":
        return _namespace_attr(node)
    return ""


def _expr_value(node: GenericNode) -> Optional[GenericNode]:
    inner = _named(node)
    if inner:
        return inner[-1]
    return None


def _take_attr(
    name: str, value: Optional[GenericNode], child: GenericNode
) -> Tuple[str, Optional[GenericNode]]:
    found = _attr_name(child)
    if not name and found:
        return found, value
    if _ts(child) == "jsx_expression":
        return name, _expr_value(child)
    return name, child


def _attribute_value(node: GenericNode) -> Tuple[str, Optional[GenericNode]]:
    name = ""
    value: Optional[GenericNode] = None
    for child in _named(node):
        name, value = _take_attr(name, value, child)
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


def _check_html_attr(report: _Report, node: GenericNode, name: str, value: GenericNode) -> None:
    if name == "dangerouslySetInnerHTML" and _unsafe_prop(value, report.bindings):
        report.add(
            node,
            "JSX001",
            "Unsanitized HTML passed to dangerouslySetInnerHTML",
            _HTML_SUGGESTION,
        )


def _check_link_attr(report: _Report, node: GenericNode, name: str, value: GenericNode) -> None:
    if name in _LINK_ATTRS and _javascript_url(value):
        report.add(
            node,
            "JSX002",
            "javascript: URL in href, src, action, or xlinkHref",
            "Use an http(s) URL, or a button with an event handler.",
        )


def _check_attribute(report: _Report, node: GenericNode) -> None:
    name, value = _attribute_value(node)
    if value is None:
        return
    _check_html_attr(report, node, name, value)
    _check_link_attr(report, node, name, value)


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


def _first_named(node: GenericNode) -> Optional[GenericNode]:
    kids = _named(node)
    if kids:
        return kids[0]
    return None


def _argument_list(node: GenericNode) -> Optional[GenericNode]:
    for child in _named(node):
        if _ts(child) == "arguments":
            return child
    return None


def _check_call(report: _Report, node: GenericNode) -> None:
    callee = _first_named(node)
    arguments = _argument_list(node)
    if callee is None or arguments is None:
        return
    _check_shell_call(report, node, callee, _named(arguments))


def _check_shell_call(
    report: _Report, node: GenericNode, callee: GenericNode, args: List[GenericNode]
) -> None:
    if not args or not _is_shell_exec(callee, report.bindings):
        return
    if not _dynamic_command(args[0]):
        return
    report.add(
        node,
        "JS001",
        "shelljs exec runs a command built from a template or concatenation",
        "Keep the command a constant, or pass arguments separately from the program name.",
        issue_type=AnalysisIssueType.COMMAND_INJECTION,
        cwe="CWE-78",
    )


def _record_binding(bindings: _Bindings, node: GenericNode) -> None:
    kind = _ts(node)
    if kind == "import_statement":
        bindings.import_statement(node)
    elif kind == "variable_declarator":
        bindings.declarator(node)
    elif kind == "function_declaration":
        bindings.function_decl(node)


def _report_node(report: _Report, node: GenericNode) -> None:
    kind = _ts(node)
    if kind == "jsx_attribute":
        _check_attribute(report, node)
    elif kind == "call_expression":
        _check_call(report, node)


def find_js_security_issues(tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
    """XSS findings for one JavaScript or TypeScript tree. The caller gates the flag."""
    nodes = tree.walk()
    bindings = _Bindings()
    for node in nodes:
        _record_binding(bindings, node)
    report = _Report(file_path, bindings)
    for node in nodes:
        _report_node(report, node)
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
