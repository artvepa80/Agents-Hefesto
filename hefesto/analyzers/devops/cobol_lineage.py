"""Program lineage for COBOL: a deterministic dependency graph between programs.

Built from the same pass as :class:`CobolProjectIndex` (each scanned file is
read once) and exposed as the ``lineage`` section of the JSON report. It is
information, not findings: no rule reads it and no severity changes.

What becomes an edge (only literal targets, never guessed):

* ``CALL 'NAME'`` / ``CALL "NAME"`` and ``EXEC CICS LINK|XCTL PROGRAM('NAME')``
  whose target is a COBOL program of the scanned tree (by file name or
  ``PROGRAM-ID``) -> ``program -> program``.
* ``COPY`` / ``EXEC SQL INCLUDE`` of a copybook in the scan -> ``copybook``
  (direct edges only, also copybook -> copybook; the closure is left to the
  reader).
* DB2 tables named after ``FROM``, ``JOIN``, ``UPDATE``, ``DELETE FROM`` and
  ``INSERT INTO`` inside ``EXEC SQL`` (also in a ``DECLARE ... CURSOR FOR``
  select) -> ``table``.

Literal targets that are not programs of the tree are ``references``:
``system`` (target provided by the system, not by the repo; ``kind`` says
how it is referenced: MQ, Language Environment, IMS, DB2 entry points, see
:data:`SYSTEM_SERVICE_PREFIXES`) or ``external`` (everything else, including
non-COBOL modules of the repo such as assembler). Variable targets, dynamic
SQL and names that match two programs are ``unresolved``, with the expression
and a reason. A reference written inside a copybook counts once for every
program that COPYs it (directly or nested), with the copybook file and line.

Every literal CALL/LINK/XCTL target is classified exactly once: an edge, a
reference or an unresolved entry (``ambiguous``).
"""

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

SCHEMA_VERSION = 1

# Literal CALL/LINK/XCTL targets that are runtime services, not user programs.
SYSTEM_SERVICES = {"CBLTDLI", "AIBTDLI"}  # IMS DL/I
SYSTEM_SERVICE_PREFIXES = ("MQ", "CEE", "DSN")  # IBM MQ, Language Environment, DB2

_PROGRAM_SUFFIXES = (".cbl", ".cob", ".cobol", ".pco")
_LITERAL = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
_EXEC_BLOCK = re.compile(r"\bEXEC\s+(CICS|SQL)\b(.*?)(?:\bEND-EXEC\b|\Z)", re.I | re.S)
_CALL = re.compile(r"(?<![\w-])CALL\s+", re.I)
_CALL_TARGET = re.compile(r"'([^'\n]*)'|\"([^\"\n]*)\"|([A-Za-z0-9][\w-]*)")
_PROGRAM_ID = re.compile(r"(?<![\w-])PROGRAM-ID\s*\.?\s*", re.I)
_NAME = re.compile(r"['\"]?([A-Za-z0-9][\w-]*)")
_PROGRAM_OPT = re.compile(r"\bPROGRAM\s*\(\s*", re.I)
_SQL_TOKEN = re.compile(r":?[A-Za-z0-9_#@$][\w#@$-]*(?:\.[A-Za-z0-9_#@$][\w#@$-]*)*|[(),]|\S")
_HEAD_WORD = re.compile(r"\s*([A-Za-z]+)")
_CICS_TARGET = re.compile(r"'([^'\n]*)'|\"([^\"\n]*)\"|([^)]*)")
_NAME_START = re.compile(r"[A-Z0-9_#@$]")
_SEQ_AREA = re.compile(r"^[\d ]{6}")

_SQL_NO_TABLES = {"INCLUDE", "WHENEVER", "OPEN", "CLOSE", "FETCH", "COMMIT", "ROLLBACK"}
_SQL_DYNAMIC = {"PREPARE", "EXECUTE"}
_SQL_KEYWORDS = {
    "AS",
    "ON",
    "WHERE",
    "GROUP",
    "ORDER",
    "HAVING",
    "UNION",
    "EXCEPT",
    "INTERSECT",
    "JOIN",
    "INNER",
    "LEFT",
    "RIGHT",
    "FULL",
    "OUTER",
    "CROSS",
    "SET",
    "VALUES",
    "FOR",
    "FETCH",
    "WITH",
    "INTO",
    "SELECT",
    "FROM",
    "LIMIT",
    "OPTIMIZE",
    "QUERYNO",
    "SKIP",
    "USING",
    "OVERRIDING",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "AND",
    "OR",
    "NOT",
}


@dataclass(frozen=True)
class Ref:
    """One reference found in a file: CALL, LINK, XCTL or SQL."""

    kind: str
    line: int
    target: str = ""  # literal name (empty when not literal)
    expression: str = ""  # source text when the target is not a literal
    reason: str = ""  # why it is unresolved (empty when literal)
    op: str = ""  # SQL statement for table references


@dataclass
class FileLineage:
    """References of one file, extracted from its text once."""

    program_id: Optional[str] = None
    refs: List[Ref] = field(default_factory=list)


# ------------------------------------------------------------------ text


# Searched in upper-cased text. A plain alternation scans ~3x faster than one
# with look-arounds, so whole-word matching is checked in _keyword_lines.
_KEYWORD = re.compile(r"CALL|EXEC|PROGRAM-ID")
_END_EXEC = re.compile(r"END-EXEC", re.I)


def _word_char(char: str) -> bool:
    """Same set as ``[\\w-]`` in ``re``: letters, digits, underscore and hyphen."""
    return char.isalnum() or char in "_-"


def _keyword_lines(text: str) -> List[int]:
    """0-based line indexes holding CALL, EXEC or PROGRAM-ID (``text`` upper-cased)."""
    found: List[int] = []
    line, last = 0, 0
    end = len(text)
    for match in _KEYWORD.finditer(text):
        start, stop = match.start(), match.end()
        if (start and _word_char(text[start - 1])) or (stop < end and _word_char(text[stop])):
            continue  # END-EXEC, CALLED, WS-CALL: not the keyword
        line += text.count("\n", last, start)
        last = start
        if not found or found[-1] != line:
            found.append(line)
    return found


def _wanted_lines(upper: str, raw: List[str]) -> List[int]:
    """0-based indexes of the lines that can hold a reference (plus what follows).

    A keyword line and the next one (``PROGRAM-ID.`` / ``CALL`` with the name
    on the next line), and every line of an ``EXEC`` block up to ``END-EXEC``.
    Other lines are never looked at, which keeps big files cheap.
    """
    wanted: List[int] = []
    n = len(raw)
    for i in _keyword_lines(upper):
        if i >= n:
            continue
        stop = i + 1
        if "EXEC" in raw[i].upper():
            while stop < n and not _END_EXEC.search(raw[stop - 1]):
                stop += 1
        stop = min(max(stop, i + 2), n)
        start = max(i, wanted[-1] + 1) if wanted else i
        wanted.extend(range(start, stop))
    return wanted


def _code_line(raw: str, fixed: bool) -> str:
    """Code part of one physical line (same columns, comments and sequence area blanked)."""
    line = raw[:72] if fixed else raw
    if "*" in line or (fixed and line[6:7] == "/"):
        from hefesto.analyzers.devops.cobol_project_index import _code_part

        line = _code_part(line)  # comment lines and inline *> comments
    if fixed and _SEQ_AREA.match(line):
        line = " " * min(len(line), 7) + line[7:]
    return line


def _mask_line(line: str) -> str:
    if "'" not in line and '"' not in line:
        return line
    return _LITERAL.sub(
        lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1], line
    )


class _Text:
    """Selected code lines joined, their literal-masked twin and offset -> line mapping."""

    def __init__(self, raw: List[str], numbers: List[int], fixed: bool):
        lines = [_code_line(raw[i], fixed) for i in numbers]
        self.code = "\n".join(lines)
        self.masked = "\n".join(_mask_line(line) for line in lines)
        self._numbers = [i + 1 for i in numbers]
        self._starts = [0]
        for line in lines[:-1]:
            self._starts.append(self._starts[-1] + len(line) + 1)

    def line_of(self, offset: int) -> int:
        return self._numbers[bisect_right(self._starts, offset) - 1]


def extract(text: str, fixed: Optional[bool] = None) -> FileLineage:
    """PROGRAM-ID and CALL/LINK/XCTL/SQL references of one COBOL source."""
    upper = text.upper()
    if "CALL" not in upper and "EXEC" not in upper and "PROGRAM-ID" not in upper:
        return FileLineage()
    raw = text.splitlines()
    numbers = _wanted_lines(upper, raw)
    if not numbers:
        return FileLineage()
    if fixed is None:
        from hefesto.analyzers.devops.cobol_project_index import is_fixed_format

        fixed = is_fixed_format(text)
    doc = _Text(raw, numbers, fixed)
    result = FileLineage(program_id=_program_id(doc))
    matches = list(_EXEC_BLOCK.finditer(doc.masked))
    blocks = [(m.start(), m.end()) for m in matches]
    result.refs.extend(_calls(doc, blocks))
    for match in matches:
        result.refs.extend(_exec_refs(doc, match))
    result.refs.sort(key=lambda r: (r.line, r.kind, r.target, r.expression))
    return result


def _program_id(doc: _Text) -> Optional[str]:
    match = _PROGRAM_ID.search(doc.masked)
    if not match:
        return None
    name = _NAME.match(doc.code, match.end())
    return name.group(1).upper() if name else None


def _inside(offset: int, blocks: List[Tuple[int, int]]) -> bool:
    """Whether ``offset`` falls in one of the (sorted, disjoint) EXEC blocks."""
    i = bisect_right(blocks, (offset, float("inf"))) - 1
    return i >= 0 and blocks[i][0] <= offset < blocks[i][1]


def _calls(doc: _Text, blocks: List[Tuple[int, int]]) -> Iterable[Ref]:
    for match in _CALL.finditer(doc.masked):
        if _inside(match.start(), blocks):
            continue  # EXEC SQL CALL (stored procedure) and CICS text
        line = doc.line_of(match.start())
        target = _CALL_TARGET.match(doc.code, match.end())
        if target is None:
            yield Ref("CALL", line, expression="CALL", reason="no_target")
        elif target.group(3) is None:
            literal = target.group(1) if target.group(1) is not None else target.group(2)
            yield Ref("CALL", line, target=literal.strip().upper())
        else:
            yield Ref("CALL", line, expression=target.group(3), reason="variable_target")


def _exec_refs(doc: _Text, match: "re.Match[str]") -> Iterable[Ref]:
    body_start = match.start(2)
    if match.group(1).upper() == "SQL":
        return _sql_refs(doc, match.group(2), body_start)
    return _cics_refs(doc, match.group(2), body_start)


def _cics_refs(doc: _Text, body: str, base: int) -> List[Ref]:
    words = _HEAD_WORD.match(body)
    if not words or words.group(1).upper() not in ("LINK", "XCTL"):
        return []
    kind = words.group(1).upper()
    line = doc.line_of(base + words.start(1))
    option = _PROGRAM_OPT.search(body)
    if option is None:
        return [Ref(kind, line, expression=kind, reason="no_program_option")]
    start = base + option.end()
    target = _CICS_TARGET.match(doc.code[start:])
    if target and target.group(3) is None:
        literal = target.group(1) if target.group(1) is not None else target.group(2)
        return [Ref(kind, line, target=literal.strip().upper())]
    expression = " ".join((target.group(3) if target else "").split())
    return [Ref(kind, line, expression=f"PROGRAM({expression})", reason="variable_target")]


# ------------------------------------------------------------------- SQL


def _sql_refs(doc: _Text, body: str, base: int) -> List[Ref]:
    head = _HEAD_WORD.match(body)
    if head and head.group(1).upper() in _SQL_NO_TABLES:
        return []  # cheap exit for INCLUDE, FETCH, OPEN, ... before tokenizing
    # Tokens without offsets; only the line of a token is ever needed, and only
    # for table names, so keep the body line of each token instead.
    tokens: List[str] = []
    token_lines: List[int] = []
    for n, text in enumerate(body.upper().split("\n")):
        found = _SQL_TOKEN.findall(text)
        tokens.extend(found)
        token_lines.extend([n] * len(found))
    if not tokens:
        return []
    starts = [0]
    if token_lines[-1]:
        for text in body.split("\n")[: token_lines[-1]]:
            starts.append(starts[-1] + len(text) + 1)

    def line(i: int) -> int:
        return doc.line_of(base + starts[token_lines[i]])

    first = tokens[0]
    if first in _SQL_DYNAMIC or (first == "DECLARE" and _declares_statement(tokens)):
        return [Ref("SQL", line(0), expression=" ".join(tokens[:3]), reason="dynamic_sql")]
    if first in _SQL_NO_TABLES or (first == "DECLARE" and not _declares_cursor(tokens)):
        return []
    op = _sql_op(tokens)
    return [Ref("SQL", line(i), target=tokens[i], op=op) for i in _table_tokens(tokens)]


def _declares_cursor(tokens: List[str]) -> bool:
    names = tokens[:8]
    return "CURSOR" in names and "TABLE" not in names[:4]


def _declares_statement(tokens: List[str]) -> bool:
    return len(tokens) > 2 and tokens[2] == "STATEMENT"


def _sql_op(tokens: List[str]) -> str:
    first = tokens[0]
    if first == "DECLARE":
        return "SELECT"
    return first if first in ("SELECT", "INSERT", "UPDATE", "DELETE", "MERGE") else first


_TABLE_STARTERS = frozenset({"FROM", "JOIN", "UPDATE", "INTO"})


def _table_tokens(tokens: List[str]) -> List[int]:
    """Indexes of the table names of one SQL statement."""
    found: List[int] = []
    stack: List[bool] = []  # True = subquery parenthesis
    for i, tok in enumerate(tokens):
        if tok == "(":
            stack.append(i + 1 < len(tokens) and tokens[i + 1] == "SELECT")
            continue
        if tok == ")":
            if stack:
                stack.pop()
            continue
        if tok not in _TABLE_STARTERS or (stack and not stack[-1]):
            continue  # inside a function call: EXTRACT(YEAR FROM ...), TRIM(... FROM ...)
        found.extend(_tables_after(tokens, i))
    return found


def _tables_after(tokens: List[str], i: int) -> List[int]:
    tok = tokens[i]
    prev = tokens[i - 1] if i else ""
    if tok == "FROM":
        return _table_list(tokens, i + 1)
    if tok == "JOIN" or (tok == "UPDATE" and prev != "FOR"):
        return _table_list(tokens, i + 1, single=True)
    if tok == "INTO" and prev in ("INSERT", "MERGE"):
        return _table_list(tokens, i + 1, single=True)
    return []


def _is_name(tok: str) -> bool:
    return bool(_NAME_START.match(tok)) and tok not in _SQL_KEYWORDS


def _table_list(tokens: List[str], j: int, single: bool = False) -> List[int]:
    found = []
    while j < len(tokens) and _is_name(tokens[j]):
        found.append(j)
        j += 1
        if j < len(tokens) and tokens[j] == "AS":
            j += 1
        if j < len(tokens) and _is_name(tokens[j]):
            j += 1  # correlation name
        if single or j >= len(tokens) or tokens[j] != ",":
            break
        j += 1
    return found


# ----------------------------------------------------------------- graph


def is_system_target(name: str) -> bool:
    upper = name.upper()
    return upper in SYSTEM_SERVICES or upper.startswith(SYSTEM_SERVICE_PREFIXES)


def is_system_table(name: str) -> bool:
    """DB2 catalog and dummy tables (``SYSIBM.*``) are system references, not table nodes."""
    return name.upper().startswith("SYSIBM.")


def is_program_path(path: str) -> bool:
    return path.lower().endswith(_PROGRAM_SUFFIXES)


class _Graph:
    """Collects nodes, edges, references and unresolved entries, then sorts them."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.references: List[Dict[str, Any]] = []
        self.unresolved: List[Dict[str, Any]] = []

    def node(self, node_id: str, kind: str, name: str, file: Optional[str] = None) -> str:
        entry: Dict[str, Any] = {"id": node_id, "kind": kind, "name": name}
        if file:
            entry["file"] = file
        current = self.nodes.setdefault(node_id, entry)
        if file and "file" not in current:
            current["file"] = file
        return node_id

    def to_dict(self) -> Dict[str, Any]:
        def key(item: Dict[str, Any]) -> Tuple[str, ...]:
            return (
                item.get("kind", ""),
                item.get("from", ""),
                item.get("to", item.get("target", item.get("expression", ""))),
                item.get("source_file", item.get("file", "")),
                f"{item.get('line', 0):09d}",
            )

        return {
            "schema_version": SCHEMA_VERSION,
            "nodes": [self.nodes[k] for k in sorted(self.nodes)],
            "edges": sorted(_merge_edges(self.edges), key=key),
            "references": sorted(self.references, key=key),
            "unresolved": sorted(self.unresolved, key=key),
        }


def _merge_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One edge per (kind, from, to, op, source_file); its lines sorted in ``lines``."""
    merged: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    for edge in edges:
        ident = (edge["kind"], edge["from"], edge["to"], edge.get("op", ""), edge["source_file"])
        entry = merged.get(ident)
        if entry is None:
            entry = {k: v for k, v in edge.items() if k != "line"}
            entry["lines"] = []
            merged[ident] = entry
        entry["lines"].append(edge["line"])
    for entry in merged.values():
        entry["lines"] = sorted(set(entry["lines"]))
        entry["line"] = entry["lines"][0]
    return list(merged.values())


def build_lineage(index: Any) -> Optional[Dict[str, Any]]:
    """The ``lineage`` report section for a :class:`CobolProjectIndex` (None without COBOL)."""
    files = sorted(index.lineage_by_file)
    if not files:
        return None
    graph = _Graph()
    programs = _program_names(index, files)
    owners = _program_ids(index, files, programs, graph)
    for path in files:
        sources = _sources_for(index, path, owners)
        for ref in index.lineage_by_file[path].refs:
            _add_ref(graph, ref, path, sources, programs, owners)
        _add_copies(index, graph, path, owners)
    return graph.to_dict()


def _program_names(index: Any, files: List[str]) -> Dict[str, Set[str]]:
    """NAME -> program files, by file stem and by PROGRAM-ID."""
    names: Dict[str, Set[str]] = {}
    for path in files:
        if index.is_copybook_file(path) or not is_program_path(path):
            continue
        names.setdefault(Path(path).stem.upper(), set()).add(path)
        program_id = index.lineage_by_file[path].program_id
        if program_id:
            names.setdefault(program_id, set()).add(path)
    return names


def _program_ids(
    index: Any, files: List[str], programs: Dict[str, Set[str]], graph: _Graph
) -> Dict[str, str]:
    """Program file -> node id (``program:NAME``); a shared name gets the file appended."""
    owners: Dict[str, str] = {}
    for path in files:
        if index.is_copybook_file(path) or not is_program_path(path):
            continue
        name = index.lineage_by_file[path].program_id or Path(path).stem.upper()
        node_id = f"program:{name}"
        if len(programs.get(name, ())) > 1:
            node_id = f"program:{name}@{path}"
        owners[path] = graph.node(node_id, "program", name, path)
    return owners


def _sources_for(index: Any, path: str, owners: Dict[str, str]) -> List[str]:
    """Program nodes a reference in ``path`` belongs to (every copier of a copybook)."""
    if path in owners:
        return [owners[path]]
    copiers = index.dependents.get(Path(path).stem.upper(), set())
    return sorted(owners[p] for p in copiers if p in owners)


def _add_ref(
    graph: _Graph,
    ref: Ref,
    path: str,
    sources: List[str],
    programs: Dict[str, Set[str]],
    owners: Dict[str, str],
) -> None:
    if not sources:
        sources = [""]  # copybook nobody in the scan COPYs
    for source in sources:
        place = {"source_file": path, "line": ref.line}
        if ref.reason or not source:
            reason = ref.reason or "copybook_not_copied"
            graph.unresolved.append(
                {
                    "kind": ref.kind,
                    "from": source,
                    "expression": ref.expression or ref.target,
                    "reason": reason,
                    "file": path,
                    "line": ref.line,
                }
            )
        elif ref.kind == "SQL" and is_system_table(ref.target):
            graph.references.append(
                {
                    "kind": "SQL",
                    "class": "system",
                    "target": ref.target,
                    "op": ref.op,
                    "from": source,
                    **place,
                }
            )
        elif ref.kind == "SQL":
            to = graph.node(f"table:{ref.target}", "table", ref.target)
            graph.edges.append({"kind": "SQL", "from": source, "to": to, "op": ref.op, **place})
        else:
            _add_program_ref(graph, ref, source, place, programs, owners)


def _add_program_ref(
    graph: _Graph,
    ref: Ref,
    source: str,
    place: Dict[str, Any],
    programs: Dict[str, Set[str]],
    owners: Dict[str, str],
) -> None:
    """Classify one literal CALL/LINK/XCTL target: program, service, external or ambiguous."""
    targets = programs.get(ref.target, set())
    if len(targets) == 1:
        to = owners[next(iter(targets))]
        graph.edges.append({"kind": ref.kind, "from": source, "to": to, **place})
    elif targets:
        graph.unresolved.append(
            {
                "kind": ref.kind,
                "from": source,
                "expression": ref.target,
                "reason": "ambiguous",
                "file": place["source_file"],
                "line": place["line"],
            }
        )
    else:
        cls = "system" if is_system_target(ref.target) else "external"
        graph.references.append(
            {"kind": ref.kind, "class": cls, "target": ref.target, "from": source, **place}
        )


def _add_copies(index: Any, graph: _Graph, path: str, owners: Dict[str, str]) -> None:
    """Direct COPY/INCLUDE edges from ``path`` to copybooks of the scan."""
    from hefesto.analyzers.devops.cobol_project_index import is_system_copybook

    names = index.copy_names_for(path) or []
    if path in owners:
        source = owners[path]
    else:
        stem = Path(path).stem.upper()
        source = graph.node(f"copybook:{stem}", "copybook", stem, path)
    for line, name in names:
        if is_system_copybook(name) or name not in index.available:
            continue
        target = index.resolve(name, path)
        to = graph.node(
            f"copybook:{name}",
            "copybook",
            name,
            target if target and index.is_copybook_file(target) else None,
        )
        graph.edges.append(
            {"kind": "COPY", "from": source, "to": to, "source_file": path, "line": line}
        )
