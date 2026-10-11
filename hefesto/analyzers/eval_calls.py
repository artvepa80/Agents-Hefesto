"""eval/exec calls read from the tree-sitter syntax tree (EVAL_USAGE).

Only calls count, so comments, strings and template text never match.

JavaScript / TypeScript
    ``eval(...)``, ``window.eval(...)``, ``globalThis.eval(...)``,
    ``self.eval(...)``; ``exec`` only when it is the ``child_process``
    function: a name bound by ``require("child_process")`` /
    ``import ... from "child_process"`` (``node:`` prefix included), a member
    call on such a module binding or on ``require("child_process")`` itself,
    and Cypress ``cy.exec`` (runs a shell command). ``RegExp.prototype.exec``
    (``/re/.exec(s)``, ``re.exec(s)``) and any other ``.exec`` method are not
    code execution.
Java
    ``exec`` on a ``Runtime`` (``Runtime.getRuntime().exec``, or a variable,
    field or parameter declared ``Runtime``) and ``eval`` on a
    ``ScriptEngine`` (declared type, or ``getEngineBy*()`` result). A class's
    own ``exec`` method is not code execution.
Go, Rust, C#
    No eval/exec builtin exists, so nothing is reported.
"""

from typing import Dict, Iterator, List, Optional, Set, Tuple

from hefesto.core.ast.generic_ast import GenericAST, GenericNode

_CHILD_PROCESS = {"child_process", "node:child_process"}
_GLOBAL_OBJECTS = {"window", "globalThis", "self"}
_SCRIPT_ENGINE_FACTORIES = {"getEngineByName", "getEngineByExtension", "getEngineByMimeType"}
_PUNCTUATION = {".", "?.", "(", ")", ",", ";"}


def _ts_type(node: GenericNode) -> str:
    return str(node.metadata.get("treesitter_type", ""))


class _Source:
    """Node text from line/column positions (tree-sitter columns are bytes)."""

    def __init__(self, code: str):
        self.lines = [line.encode("utf8") for line in code.split("\n")]

    def text(self, node: GenericNode) -> str:
        if node.line_start != node.line_end or node.line_start > len(self.lines):
            return node.text
        raw = self.lines[node.line_start - 1][node.column_start : node.column_end]
        return raw.decode("utf8", "replace")


def _named(node: GenericNode) -> List[GenericNode]:
    return [c for c in node.children if _ts_type(c) not in _PUNCTUATION]


def _string_value(node: GenericNode, src: _Source) -> Optional[str]:
    if _ts_type(node) not in ("string", "string_literal"):
        return None
    value = src.text(node)
    return value[1:-1] if len(value) >= 2 else value


def find_eval_calls(tree: GenericAST, code: str) -> List[Tuple[int, str]]:
    """(line, function) of every eval/exec call in a tree-sitter tree."""
    src = _Source(code)
    if tree.language in ("javascript", "typescript"):
        return sorted(set(_JsFinder(tree, src).calls()))
    if tree.language == "java":
        return sorted(set(_JavaFinder(tree, src).calls()))
    return []


# --------------------------------------------------------------------- JS / TS


class _JsFinder:
    def __init__(self, tree: GenericAST, src: _Source):
        self.nodes = tree.walk()
        self.src = src
        self.modules: Set[str] = {"child_process"}  # names bound to the module
        self.exec_names: Set[str] = set()  # names bound to child_process.exec
        self._bindings()

    def _is_require_child_process(self, node: GenericNode) -> bool:
        if _ts_type(node) != "call_expression":
            return False
        parts = _named(node)
        if len(parts) != 2 or self.src.text(parts[0]) != "require":
            return False
        args = _named(parts[1])
        return bool(args) and _string_value(args[0], self.src) in _CHILD_PROCESS

    def _bindings(self) -> None:
        for node in self.nodes:
            kind = _ts_type(node)
            if kind == "variable_declarator":
                self._declarator(node)
            elif kind == "import_statement":
                self._import(node)

    def _declarator(self, node: GenericNode) -> None:
        parts = [c for c in node.children if _ts_type(c) != "="]
        if len(parts) != 2:
            return
        target, value = parts
        if self._is_require_child_process(value):
            self._bind_module(target)
        elif _ts_type(value) == "member_expression" and _ts_type(target) == "identifier":
            members = _named(value)
            if self._is_require_child_process(members[0]) and self._text(members[-1]) == "exec":
                self.exec_names.add(self._text(target))

    def _text(self, node: GenericNode) -> str:
        return self.src.text(node)

    def _bind_module(self, target: GenericNode) -> None:
        """``x = require("child_process")`` or ``{ exec, exec: run } = require(...)``."""
        if _ts_type(target) == "identifier":
            self.modules.add(self._text(target))
        elif _ts_type(target) == "object_pattern":
            for entry in _named(target):
                self._bind_pattern_entry(entry)

    def _bind_pattern_entry(self, entry: GenericNode) -> None:
        if _ts_type(entry) == "shorthand_property_identifier_pattern":
            pair = [entry, entry]
        else:
            pair = [c for c in entry.children if _ts_type(c) != ":"]
        if len(pair) == 2 and self._text(pair[0]) == "exec":
            self.exec_names.add(self._text(pair[1]))

    def _import(self, node: GenericNode) -> None:
        source = next((c for c in node.children if _ts_type(c) == "string"), None)
        if source is None or _string_value(source, self.src) not in _CHILD_PROCESS:
            return
        for sub in node.walk():
            ids = [self._text(c) for c in sub.children if _ts_type(c) == "identifier"]
            kind = _ts_type(sub)
            if kind in ("namespace_import", "import_clause"):
                self.modules.update(ids)  # ``* as cp`` / default import
            elif kind == "import_specifier" and ids and ids[0] == "exec":
                self.exec_names.add(ids[-1])

    def calls(self) -> Iterator[Tuple[int, str]]:
        for node in self.nodes:
            if _ts_type(node) == "call_expression" and node.children:
                name = self._call_name(node.children[0])
                if name:
                    yield node.line_start, name

    def _call_name(self, callee: GenericNode) -> Optional[str]:
        """``eval``/``exec`` if the callee is code or shell execution, else None."""
        kind = _ts_type(callee)
        if kind == "identifier":
            name = self._text(callee)
            if name == "eval":
                return "eval"
            return "exec" if name in self.exec_names else None
        parts = _named(callee) if kind == "member_expression" else []
        return self._member_call_name(*parts) if len(parts) == 2 else None

    def _member_call_name(self, obj: GenericNode, prop: GenericNode) -> Optional[str]:
        obj_name = self._text(obj) if _ts_type(obj) == "identifier" else None
        prop_name = self._text(prop)
        if prop_name == "eval":
            return "eval" if obj_name in _GLOBAL_OBJECTS else None
        if prop_name != "exec":
            return None
        shell = obj_name in self.modules or obj_name == "cy"
        return "exec" if shell or self._is_require_child_process(obj) else None


# --------------------------------------------------------------------- Java


class _JavaFinder:
    def __init__(self, tree: GenericAST, src: _Source):
        self.nodes = tree.walk()
        self.src = src
        self.types: Dict[str, str] = {}
        for node in self.nodes:
            if _ts_type(node) in ("field_declaration", "local_variable_declaration"):
                self._declaration(node)
            elif _ts_type(node) == "formal_parameter":
                parts = _named(node)
                if len(parts) >= 2:
                    self.types[self.src.text(parts[-1])] = self._type_name(parts[-2])

    def _type_name(self, node: GenericNode) -> str:
        return self.src.text(node).rsplit(".", 1)[-1]

    def _declaration(self, node: GenericNode) -> None:
        type_node = next(
            (
                c
                for c in node.children
                if _ts_type(c) in ("type_identifier", "scoped_type_identifier")
            ),
            None,
        )
        if type_node is None:
            return
        type_name = self._type_name(type_node)
        for decl in node.children:
            if _ts_type(decl) == "variable_declarator":
                ident = next((c for c in decl.children if _ts_type(c) == "identifier"), None)
                if ident is not None:
                    self.types[self.src.text(ident)] = type_name

    @staticmethod
    def _split(invocation: GenericNode) -> Tuple[Optional[GenericNode], Optional[GenericNode]]:
        """(receiver, method name) of a method_invocation."""
        parts = [c for c in _named(invocation) if _ts_type(c) not in ("type_arguments",)]
        args = next((i for i, c in enumerate(parts) if _ts_type(c) == "argument_list"), None)
        if args is None or args == 0:
            return None, None
        name = parts[args - 1]
        receiver = parts[args - 2] if args >= 2 else None
        return receiver, name

    def _receiver_type(self, receiver: GenericNode) -> Optional[str]:
        kind = _ts_type(receiver)
        if kind == "identifier":
            return self.types.get(self.src.text(receiver))
        if kind == "field_access":
            last = [c for c in receiver.children if _ts_type(c) == "identifier"]
            return self.types.get(self.src.text(last[-1])) if last else None
        if kind == "method_invocation":
            return self._result_type(receiver)
        return None

    def _result_type(self, invocation: GenericNode) -> Optional[str]:
        """``Runtime.getRuntime()`` -> Runtime, ``m.getEngineByName(..)`` -> ScriptEngine."""
        receiver, name = self._split(invocation)
        method = self.src.text(name) if name is not None else ""
        if method in _SCRIPT_ENGINE_FACTORIES:
            return "ScriptEngine"
        is_runtime = receiver is not None and self._type_name(receiver) == "Runtime"
        return "Runtime" if method == "getRuntime" and is_runtime else None

    _SINKS = {("exec", "Runtime"): "exec", ("eval", "ScriptEngine"): "eval"}

    def calls(self) -> Iterator[Tuple[int, str]]:
        for node in self.nodes:
            if _ts_type(node) != "method_invocation":
                continue
            receiver, name = self._split(node)
            if name is None or receiver is None:
                continue
            sink = self._SINKS.get((self.src.text(name), self._receiver_type(receiver) or ""))
            if sink:
                yield name.line_start, sink
