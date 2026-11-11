"""Same-function string facts for Go security rules.

Walks each function in source order and remembers how local strings were built.
A closure does not see the outer function's facts. The last straight-line
assignment wins. The two arms of an ``if`` are joined: if either arm built the
string, the name stays built. An inner ``:=`` shadows the outer name.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional

from hefesto.core.ast.generic_ast import GenericNode

_HOLE = "\ue000"
_UNKNOWN_TEXT = None

_Call = Callable[[GenericNode, GenericNode, List[GenericNode], List["_GoString"]], None]
_Classify = Callable[["_GoString"], bool]


@dataclass(frozen=True)
class _GoString:
    """What a Go expression contributes to a command or a query.

    ``text`` keeps literal pieces. ``_HOLE`` marks a value that was inserted.
    ``quote_ident`` means the value is a ``QuoteIdentifier`` call.
    """

    built: bool = False
    text: Optional[str] = None
    quote_ident: bool = False
    quote_ident_holes: bool = False
    sql_risk: bool = False


_UNKNOWN = _GoString()


class _Env:
    """Nested name bindings. Lookup uses the nearest scope."""

    def __init__(self) -> None:
        self.scopes: List[Dict[str, _GoString]] = [{}]

    def push(self) -> None:
        self.scopes.append({})

    def pop(self) -> None:
        if len(self.scopes) > 1:
            self.scopes.pop()

    def clone(self) -> "_Env":
        copied = _Env()
        copied.scopes = [dict(scope) for scope in self.scopes]
        return copied

    def restore(self, other: "_Env") -> None:
        self.scopes = [dict(scope) for scope in other.scopes]

    def lookup(self, name: str) -> _GoString:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return _UNKNOWN

    def declare(self, name: str, fact: _GoString) -> None:
        if name and name != "_":
            self.scopes[-1][name] = fact

    def assign(self, name: str, fact: _GoString) -> None:
        if not name or name == "_":
            return
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name] = fact
                return
        self.scopes[-1][name] = fact


def _ts(node: GenericNode) -> str:
    return str(node.metadata.get("treesitter_type", ""))


def _named(node: GenericNode) -> List[GenericNode]:
    return [c for c in node.children if c.metadata.get("named", True) and "comment" not in _ts(c)]


def _anon_text(node: GenericNode) -> str:
    for child in node.children:
        if child.metadata.get("named", True):
            continue
        text = child.text.strip()
        if text:
            return text
    return ""


def _no_sql(_fact: _GoString) -> bool:
    return False


def _const_text(fact: _GoString) -> Optional[str]:
    if fact.built or fact.quote_ident or fact.text is None or _HOLE in fact.text:
        return None
    return fact.text


def _is_const(fact: _GoString) -> bool:
    return _const_text(fact) is not None


def _unescape(text: str) -> str:
    return text.replace(r"\\", "\\").replace(r"\"", '"').replace(r"\n", "\n").replace(r"\t", "\t")


def _literal_text(node: GenericNode) -> Optional[str]:
    raw = node.text
    kind = _ts(node)
    if kind == "raw_string_literal" and len(raw) >= 2 and raw[0] == "`" and raw[-1] == "`":
        return raw[1:-1]
    if kind == "interpreted_string_literal" and len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return _unescape(raw[1:-1])
    return None


def _seal(fact: _GoString, classify: _Classify) -> _GoString:
    if not fact.built:
        return fact
    risk = bool(classify(fact))
    if risk == fact.sql_risk:
        return fact
    return replace(fact, sql_risk=risk)


def _keeps_prefix(text: Optional[str]) -> bool:
    if not text:
        return False
    stripped = text.lstrip(" \t\r\n")
    return bool(stripped) and not stripped.startswith(_HOLE)


def _finish(fact: _GoString, classify: _Classify, prior: bool) -> _GoString:
    """Trust a full string. Keep a prior risk when the prefix was lost."""
    sealed = _seal(fact, classify)
    if sealed.sql_risk or not prior or _keeps_prefix(fact.text):
        return sealed
    return replace(sealed, built=True, sql_risk=True)


def _stringish(fact: _GoString) -> bool:
    return fact.text is not None or fact.built or fact.quote_ident


def _piece(fact: _GoString) -> tuple:
    if fact.text is None:
        qi = 1 if fact.quote_ident else 0
        return _HOLE, 1, qi, True
    holes = fact.text.count(_HOLE)
    qi = holes if fact.quote_ident_holes else 0
    return fact.text, holes, qi, holes > 0 or fact.built


def _concat(facts: List[_GoString], classify: _Classify) -> _GoString:
    parts: List[str] = []
    holes = 0
    qi = 0
    dynamic = False
    prior = False
    stringish = False
    for fact in facts:
        piece, count, qi_count, dyn = _piece(fact)
        parts.append(piece)
        holes += count
        qi += qi_count
        dynamic = dynamic or dyn
        prior = prior or fact.sql_risk
        stringish = stringish or _stringish(fact)
    text = "".join(parts) if stringish else _UNKNOWN_TEXT
    built = bool(dynamic and stringish) or any(fact.built for fact in facts)
    made = _GoString(built=built, text=text, quote_ident_holes=holes > 0 and qi == holes)
    return _finish(made, classify, prior)


def _maybe_index(fmt: str, i: int) -> tuple:
    if i >= len(fmt) or fmt[i] != "[":
        return None, i
    end = fmt.find("]", i)
    if end < 0 or not fmt[i + 1 : end].isdigit():
        return None, i
    return int(fmt[i + 1 : end]), end + 1


def _skip_flags(fmt: str, i: int) -> int:
    while i < len(fmt) and fmt[i] in "#0-+ ":
        i += 1
    return i


def _skip_num(fmt: str, i: int) -> tuple:
    stars = 0
    while i < len(fmt) and (fmt[i].isdigit() or fmt[i] == "*"):
        if fmt[i] == "*":
            stars += 1
        i += 1
    return i, stars


def _read_verb(fmt: str, start: int) -> tuple:
    i = start + 1
    if i >= len(fmt):
        return "", i, None, 0
    if fmt[i] == "%":
        return "%", i + 1, None, 0
    index, i = _maybe_index(fmt, i)
    i = _skip_flags(fmt, i)
    i, stars = _skip_num(fmt, i)
    if i < len(fmt) and fmt[i] == ".":
        i, more = _skip_num(fmt, i + 1)
        stars += more
    if i >= len(fmt):
        return "", i, index, stars
    return fmt[i], i + 1, index, stars


def _string_hole(fact: _GoString) -> tuple:
    text = _const_text(fact)
    if text is not None:
        return text, False, False, False
    qi = fact.quote_ident and fact.text is None
    return _HOLE, True, qi, True


def _apply_verb(
    verb: str, index: Optional[int], stars: int, args: List[_GoString], cursor: int
) -> tuple:
    if verb == "%":
        return "%", False, False, False
    if verb == "":
        return "", False, False, False
    pos = index - 1 if index is not None else cursor + stars
    fact = args[pos] if 0 <= pos < len(args) else _UNKNOWN
    if verb in "sq":
        return _string_hole(fact)
    return "", False, False, not _is_const(fact)


def _advance(cursor: int, verb: str, index: Optional[int], stars: int) -> int:
    if verb in ("", "%"):
        return cursor
    if index is not None:
        return index
    return cursor + 1 + stars


def _render_sprintf(fmt: str, args: List[_GoString], classify: _Classify) -> _GoString:
    parts: List[str] = []
    holes = 0
    qi = 0
    dynamic = False
    cursor = 0
    i = 0
    while i < len(fmt):
        if fmt[i] != "%":
            parts.append(fmt[i])
            i += 1
            continue
        verb, i, index, stars = _read_verb(fmt, i)
        piece, is_hole, is_qi, is_dyn = _apply_verb(verb, index, stars, args, cursor)
        parts.append(piece)
        holes += 1 if is_hole else 0
        qi += 1 if is_qi else 0
        dynamic = dynamic or is_dyn
        cursor = _advance(cursor, verb, index, stars)
    used = dynamic or any(not _is_const(arg) for arg in args)
    made = _GoString(built=used, text="".join(parts), quote_ident_holes=holes > 0 and qi == holes)
    return _seal(made, classify)


def _sprintf_fact(facts: List[_GoString], classify: _Classify) -> _GoString:
    if len(facts) < 2:
        text = _const_text(facts[0]) if facts else None
        if text is None:
            return _UNKNOWN
        return _GoString(text=text)
    fmt = _const_text(facts[0])
    if fmt is None:
        return _GoString(built=True)
    return _render_sprintf(fmt, facts[1:], classify)


def _call_name(func: GenericNode) -> str:
    return "".join(func.text.split())


def _is_quote_ident(func: GenericNode) -> bool:
    name = _call_name(func).strip("()")
    return name == "QuoteIdentifier" or name.endswith(".QuoteIdentifier")


def _arg_nodes(call: GenericNode) -> List[GenericNode]:
    for child in _named(call):
        if _ts(child) != "argument_list":
            continue
        args = []
        for arg in _named(child):
            inner = _named(arg)
            args.append(inner[0] if _ts(arg) == "variadic_argument" and inner else arg)
        return args
    return []


def _call_fact(func: GenericNode, facts: List[_GoString], classify: _Classify) -> _GoString:
    name = _call_name(func).strip("()")
    if name == "fmt.Sprintf":
        return _sprintf_fact(facts, classify)
    if _is_quote_ident(func):
        return _GoString(quote_ident=True)
    return _UNKNOWN


def _may(left: _GoString, right: _GoString) -> _GoString:
    if left == right:
        return left
    same = left.text == right.text
    return _GoString(
        built=left.built or right.built,
        text=left.text if same else None,
        quote_ident=left.quote_ident and right.quote_ident,
        quote_ident_holes=left.quote_ident_holes and right.quote_ident_holes and same,
        sql_risk=left.sql_risk or right.sql_risk,
    )


def _fact_at(snap: _Env, depth: int, name: str, fallback: _GoString) -> _GoString:
    if depth < len(snap.scopes) and name in snap.scopes[depth]:
        return snap.scopes[depth][name]
    return fallback


def _merged_fact(base: _GoString, snaps: List[_Env], depth: int, name: str) -> _GoString:
    acc: Optional[_GoString] = None
    for snap in snaps:
        fact = _fact_at(snap, depth, name, base)
        acc = fact if acc is None else _may(acc, fact)
    return base if acc is None else acc


def _merge_scope(scope: Dict[str, _GoString], snaps: List[_Env], depth: int) -> None:
    for name in list(scope):
        scope[name] = _merged_fact(scope[name], snaps, depth, name)


def _merge(env: _Env, snaps: List[_Env]) -> None:
    for depth, scope in enumerate(env.scopes):
        _merge_scope(scope, snaps, depth)


def _ident_texts(node: GenericNode) -> List[str]:
    if _ts(node) == "identifier":
        return [node.text]
    return [child.text for child in _named(node) if _ts(child) == "identifier"]


def _eval_expr(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> _GoString:
    handler = _EXPRS.get(_ts(node))
    if handler is None:
        return _eval_nested(node, env, on_call, classify)
    return handler(node, env, on_call, classify)


def _eval_nested(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> _GoString:
    for child in _named(node):
        _eval_expr(child, env, on_call, classify)
    return _UNKNOWN


def _eval_ident(node: GenericNode, env: _Env, _on_call: _Call, _classify: _Classify) -> _GoString:
    return env.lookup(node.text)


def _eval_lit(node: GenericNode, _env: _Env, _on_call: _Call, _classify: _Classify) -> _GoString:
    text = _literal_text(node)
    if text is None:
        return _UNKNOWN
    return _GoString(text=text)


def _eval_paren(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> _GoString:
    named = _named(node)
    if not named:
        return _UNKNOWN
    return _eval_expr(named[0], env, on_call, classify)


def _eval_binary(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> _GoString:
    named = _named(node)
    if len(named) != 2:
        return _UNKNOWN
    left = _eval_expr(named[0], env, on_call, classify)
    right = _eval_expr(named[1], env, on_call, classify)
    if _anon_text(node) != "+":
        return _UNKNOWN
    return _concat([left, right], classify)


def _eval_selector(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> _GoString:
    for child in _named(node):
        if _ts(child) != "field_identifier":
            _eval_expr(child, env, on_call, classify)
    return _UNKNOWN


def _eval_call(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> _GoString:
    named = _named(node)
    if not named:
        return _UNKNOWN
    func = named[0]
    _eval_expr(func, env, on_call, classify)
    args = _arg_nodes(node)
    facts = [_eval_expr(arg, env, on_call, classify) for arg in args]
    on_call(node, func, args, facts)
    return _call_fact(func, facts, classify)


def _eval_func(node: GenericNode, _env: _Env, on_call: _Call, classify: _Classify) -> _GoString:
    _exec_function_body(node, on_call, classify)
    return _UNKNOWN


def _eval_list(
    node: GenericNode, env: _Env, on_call: _Call, classify: _Classify
) -> List[_GoString]:
    if _ts(node) != "expression_list":
        return [_eval_expr(node, env, on_call, classify)]
    return [_eval_expr(child, env, on_call, classify) for child in _named(node)]


def _exec_stmt(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    handler = _STMTS.get(_ts(node))
    if handler is None:
        _eval_expr(node, env, on_call, classify)
        return
    handler(node, env, on_call, classify)


def _exec_list(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    for child in _named(node):
        _exec_stmt(child, env, on_call, classify)


def _exec_block(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    env.push()
    _exec_list(node, env, on_call, classify)
    env.pop()


def _exec_labeled(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    for child in _named(node):
        if _ts(child) != "label_name":
            _exec_stmt(child, env, on_call, classify)


def _facts_for(names: List[str], values: List[_GoString], type_name: str) -> List[_GoString]:
    if not values and type_name == "string":
        return [_GoString(text="") for _ in names]
    if not values or (len(names) > 1 and len(values) == 1):
        return [_UNKNOWN for _ in names]
    return list(values)


def _declare_names(env: _Env, names: List[str], values: List[_GoString], type_name: str) -> None:
    facts = _facts_for(names, values, type_name)
    for name, fact in zip(names, facts):
        env.declare(name, fact)


def _exec_spec(spec: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    names: List[str] = []
    values: List[_GoString] = []
    type_name = ""
    for child in _named(spec):
        kind = _ts(child)
        if kind == "identifier":
            names.append(child.text)
        elif kind == "expression_list":
            values = _eval_list(child, env, on_call, classify)
        elif kind == "type_identifier":
            type_name = child.text
        else:
            _eval_expr(child, env, on_call, classify)
    _declare_names(env, names, values, type_name)


def _spec_nodes(node: GenericNode) -> List[GenericNode]:
    if _ts(node) in ("var_spec", "const_spec"):
        return [node]
    return [child for child in _named(node) if _ts(child) in ("var_spec", "const_spec")]


def _exec_decl(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    for spec in _spec_nodes(node):
        _exec_spec(spec, env, on_call, classify)


def _bind_append(env: _Env, names: List[str], values: List[_GoString], classify: _Classify) -> None:
    for name, value in zip(names, values):
        env.assign(name, _concat([env.lookup(name), value], classify))


def _bind_assign(
    env: _Env, names: List[str], values: List[_GoString], op: str, classify: _Classify
) -> None:
    if op == "+=":
        _bind_append(env, names, values, classify)
        return
    multi = len(names) > 1 and len(values) == 1
    if op != "=" or multi:
        for name in names:
            env.assign(name, _UNKNOWN)
        return
    for name, fact in zip(names, values):
        env.assign(name, fact)


def _exec_assign(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    parts = _named(node)
    if len(parts) < 2:
        return
    names = _ident_texts(parts[0])
    values = _eval_list(parts[1], env, on_call, classify)
    _bind_assign(env, names, values, _anon_text(node), classify)


def _short_facts(names: List[str], values: List[_GoString]) -> List[_GoString]:
    if len(names) > 1 and len(values) == 1:
        return [_UNKNOWN for _ in names]
    return list(values)


def _exec_short(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    parts = _named(node)
    if len(parts) < 2:
        return
    names = _ident_texts(parts[0])
    values = _eval_list(parts[1], env, on_call, classify)
    for name, fact in zip(names, _short_facts(names, values)):
        env.declare(name, fact)


def _bind_left(env: _Env, left: GenericNode, op: str) -> None:
    for name in _ident_texts(left):
        if op == ":=":
            env.declare(name, _UNKNOWN)
        else:
            env.assign(name, _UNKNOWN)


def _exec_range(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    named = _named(node)
    if not named:
        return
    if len(named) >= 2 and _ts(named[0]) == "expression_list":
        _bind_left(env, named[0], _anon_text(node))
    _eval_expr(named[-1], env, on_call, classify)


def _exec_receive(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    named = _named(node)
    if len(named) >= 2 and _ts(named[0]) == "expression_list":
        _bind_left(env, named[0], _anon_text(node))
    if named:
        _eval_expr(named[-1], env, on_call, classify)


def _exec_for_clause(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    for child in _named(node):
        _exec_stmt(child, env, on_call, classify)


def _bind_for(
    node: GenericNode, env: _Env, on_call: _Call, classify: _Classify
) -> Optional[GenericNode]:
    body = None
    for child in _named(node):
        kind = _ts(child)
        if kind == "block":
            body = child
        elif kind == "for_clause":
            _exec_for_clause(child, env, on_call, classify)
        elif kind == "range_clause":
            _exec_range(child, env, on_call, classify)
        else:
            _eval_expr(child, env, on_call, classify)
    return body


def _exec_for(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    env.push()
    body = _bind_for(node, env, on_call, classify)
    origin = env.clone()
    if body is not None:
        _exec_stmt(body, env, on_call, classify)
    end = env.clone()
    env.restore(origin)
    _merge(env, [origin, end])
    env.pop()


def _split_if(node: GenericNode) -> tuple:
    head: List[GenericNode] = []
    cons = None
    alt = None
    for child in _named(node):
        kind = _ts(child)
        if kind == "block" and cons is None:
            cons = child
        elif cons is not None and kind in ("block", "if_statement"):
            alt = child
        elif cons is None:
            head.append(child)
    init = head[0] if len(head) == 2 else None
    cond = head[-1] if head else None
    return init, cond, cons, alt


def _branch(node: Optional[GenericNode], origin: _Env, on_call: _Call, classify: _Classify) -> _Env:
    env = origin.clone()
    if node is not None:
        _exec_stmt(node, env, on_call, classify)
    return env


def _exec_if(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    init, cond, cons, alt = _split_if(node)
    env.push()
    if init is not None:
        _exec_stmt(init, env, on_call, classify)
    if cond is not None:
        _eval_expr(cond, env, on_call, classify)
    origin = env.clone()
    snaps = [_branch(cons, origin, on_call, classify)]
    snaps.append(_branch(alt, origin, on_call, classify) if alt is not None else origin)
    env.restore(origin)
    _merge(env, snaps)
    env.pop()


_CASES = frozenset({"expression_case", "default_case", "type_case", "communication_case"})


def _bind_header(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    if _ts(node) == "expression_list":
        for name in _ident_texts(node):
            env.declare(name, _UNKNOWN)
        return
    _exec_stmt(node, env, on_call, classify)


def _prepare_switch(
    node: GenericNode, env: _Env, on_call: _Call, classify: _Classify
) -> List[GenericNode]:
    cases = []
    for child in _named(node):
        if _ts(child) in _CASES:
            cases.append(child)
        else:
            _bind_header(child, env, on_call, classify)
    return cases


def _case_branch(case: GenericNode, origin: _Env, on_call: _Call, classify: _Classify) -> _Env:
    env = origin.clone()
    for child in _named(case):
        _exec_stmt(child, env, on_call, classify)
    return env


def _exec_switch(node: GenericNode, env: _Env, on_call: _Call, classify: _Classify) -> None:
    env.push()
    cases = _prepare_switch(node, env, on_call, classify)
    origin = env.clone()
    snaps = [_case_branch(case, origin, on_call, classify) for case in cases]
    if not any(_ts(case) == "default_case" for case in cases):
        snaps.append(origin)
    env.restore(origin)
    if snaps:
        _merge(env, snaps)
    env.pop()


def _param_names(fn: GenericNode) -> List[str]:
    names: List[str] = []
    for child in _named(fn):
        if _ts(child) != "parameter_list":
            continue
        for decl in _named(child):
            names.extend(_ident_texts(decl))
    return names


def _body_block(node: GenericNode) -> Optional[GenericNode]:
    for child in _named(node):
        if _ts(child) == "block":
            return child
    return None


def _exec_function_body(node: GenericNode, on_call: _Call, classify: _Classify) -> None:
    env = _Env()
    for name in _param_names(node):
        env.declare(name, _UNKNOWN)
    body = _body_block(node)
    if body is not None:
        _exec_block(body, env, on_call, classify)


def visit_go_calls(root: GenericNode, on_call: _Call, classify: Optional[_Classify] = None) -> None:
    """Visit Go calls with the string fact of each argument.

    ``classify`` maps a built string to the SQL-risk bit. The default never
    sets that bit.
    """
    chosen = _no_sql if classify is None else classify
    for node in _named(root):
        kind = _ts(node)
        if kind in ("function_declaration", "method_declaration"):
            _exec_function_body(node, on_call, chosen)
        elif kind in ("var_declaration", "const_declaration"):
            _exec_decl(node, _Env(), on_call, chosen)
        else:
            _exec_stmt(node, _Env(), on_call, chosen)


_EXPRS = {
    "identifier": _eval_ident,
    "raw_string_literal": _eval_lit,
    "interpreted_string_literal": _eval_lit,
    "parenthesized_expression": _eval_paren,
    "binary_expression": _eval_binary,
    "selector_expression": _eval_selector,
    "call_expression": _eval_call,
    "func_literal": _eval_func,
    "unary_expression": _eval_nested,
    "index_expression": _eval_nested,
    "slice_expression": _eval_nested,
    "type_assertion_expression": _eval_nested,
    "type_conversion_expression": _eval_nested,
    "composite_literal": _eval_nested,
    "expression_list": _eval_nested,
}

_STMTS = {
    "statement_list": _exec_list,
    "block": _exec_block,
    "labeled_statement": _exec_labeled,
    "var_declaration": _exec_decl,
    "const_declaration": _exec_decl,
    "var_spec": _exec_spec,
    "const_spec": _exec_spec,
    "assignment_statement": _exec_assign,
    "short_var_declaration": _exec_short,
    "if_statement": _exec_if,
    "for_statement": _exec_for,
    "for_clause": _exec_for_clause,
    "range_clause": _exec_range,
    "receive_statement": _exec_receive,
    "expression_switch_statement": _exec_switch,
    "type_switch_statement": _exec_switch,
    "select_statement": _exec_switch,
}
