"""JCL reader for COBOL lineage (``--lineage`` only).

Reads ``.jcl``, ``.prc`` and ``.proc`` files into jobs and steps. PROC calls
are expanded with the PROCs found in the scanned tree (in-stream first, then
cataloged members by PROC label or file name), ``STEP.DD`` overrides replace
the PROC's DD, and ``INCLUDE MEMBER=`` is spliced in when the member is in the
tree. Names are taken literally: symbols (``&X``) are never substituted.

This module only reads JCL. The graph (nodes, edges, classes) is built in
:mod:`hefesto.analyzers.devops.cobol_lineage`. JCL is not a registered
language, so without ``--lineage`` these files are never read.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

JCL_SUFFIXES = (".jcl", ".prc", ".proc")

# Programs supplied by the system (z/OS, DB2, IMS, CICS, compilers, sort).
UTILITIES = frozenset(
    {
        "ADRDSSU",
        "ASMA90",
        "BPXBATCH",
        "CCNDRVR",
        "DFHCSDUP",
        "DFHECP1$",
        "DFHSIP",
        "DFSORT",
        "DFSRRC00",
        "DFSUDMP0",
        "DFSUOCU0",
        "DFSUPNT0",
        "DFSURGL0",
        "DFSURGU0",
        "DFSURUL0",
        "DSNHPC",
        "DSNTEP2",
        "DSNTEP4",
        "DSNTIAD",
        "DSNTIAUL",
        "DSNUTILB",
        "EZACFSM1",
        "FTP",
        "HEWL",
        "ICEGENER",
        "ICEMAN",
        "ICETOOL",
        "IDCAMS",
        "IEBCOPY",
        "IEBGENER",
        "IEBUPDTE",
        "IEFBR14",
        "IEHLIST",
        "IEWBLINK",
        "IEWL",
        "IGYCRCTL",
        "IKJEFT01",
        "IKJEFT1A",
        "IKJEFT1B",
        "IRXJCL",
        "SDSF",
        "SORT",
        "SYNCSORT",
    }
)
TSO_BATCH = frozenset({"IKJEFT01", "IKJEFT1A", "IKJEFT1B"})
IMS_REGION = "DFSRRC00"

_RUN_PROGRAM = re.compile(r"\bRUN\s+PROGRAM\s*\(\s*([^)\s]+)\s*\)", re.I)
_KEYWORD = re.compile(r"^([A-Z0-9@#$.]+)=(.*)$", re.I | re.S)


@dataclass
class Stmt:
    """One JCL statement (continuations joined), with in-stream data after a DD."""

    line: int
    name: str
    op: str
    operands: List[str]
    file: str
    data: List[Tuple[int, str]] = field(default_factory=list)

    def keyword(self, key: str) -> Optional[str]:
        for operand in self.operands:
            match = _KEYWORD.match(operand)
            if match and match.group(1).upper() == key:
                return match.group(2)
        return None

    def positional(self) -> Optional[str]:
        if self.operands and not _KEYWORD.match(self.operands[0]):
            return self.operands[0]
        return None


@dataclass
class DD:
    name: str
    line: int
    file: str
    dsn: Optional[str]
    data: List[Tuple[int, str]]


@dataclass
class Step:
    name: str
    line: int
    file: str
    pgm: Optional[str]
    proc: Optional[str]
    parm: Optional[str]
    dds: List[DD] = field(default_factory=list)
    overrides: List[Tuple[str, DD]] = field(default_factory=list)


@dataclass
class Job:
    name: str
    line: int
    file: str
    steps: List[Step] = field(default_factory=list)


@dataclass
class Unresolved:
    kind: str
    owner: str  # "job" id part or step path ("" for the job itself)
    expression: str
    reason: str
    file: str
    line: int


@dataclass
class ResolvedStep:
    """A step after PROC expansion; ``path`` is ``JOB.STEP[.PROCSTEP...]``."""

    job: Job
    path: str
    step: Step


@dataclass
class JclModel:
    jobs: List[Job]
    steps: List[ResolvedStep]
    unresolved: List[Tuple[Job, str, Unresolved]]  # (job, step path or "", entry)

    def __bool__(self) -> bool:
        return bool(self.jobs)


# ------------------------------------------------------------------ statements


def _split_operands(text: str) -> Tuple[List[str], bool]:
    """Operands up to the first blank outside quotes; True when it ends with a comma."""
    out: List[str] = []
    current: List[str] = []
    depth = 0
    quote = False
    i = 0
    while i < len(text):
        char = text[i]
        if quote:
            current.append(char)
            if char == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    current.append("'")
                    i += 1
                else:
                    quote = False
        elif char == "'":
            quote = True
            current.append(char)
        elif char == " ":
            break
        elif char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            current.append(char)
        elif char == "," and depth == 0:
            out.append("".join(current))
            current = []
        else:
            current.append(char)
        i += 1
    tail = "".join(current)
    continued = tail == "" and bool(out) and text[:i].endswith(",")
    if tail:
        out.append(tail)
    return out, continued


def _fields(rest: str) -> Tuple[str, str, str]:
    """(name, operation, operand text) of the part after ``//``."""
    name = ""
    if rest and rest[0] != " ":
        name, _, rest = rest.partition(" ")
    rest = rest.lstrip()
    op, _, operands = rest.partition(" ")
    return name.upper(), op.upper(), operands.lstrip()


def statements(text: str, file: str) -> List[Stmt]:
    """JCL statements of ``text``; comments, delimiters and in-stream data are skipped."""
    lines = text.splitlines()
    out: List[Stmt] = []
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i][:72]
        number = i + 1
        i += 1
        if not raw.startswith("//") or raw.startswith("//*"):
            continue
        name, op, operand_text = _fields(raw[2:])
        if not op:
            continue  # null statement
        operands, continued = _split_operands(operand_text)
        while continued and i < n:
            nxt = lines[i][:72]
            if not nxt.startswith("//") or nxt.startswith("//*"):
                if nxt.startswith("//*"):
                    i += 1
                    continue
                break
            more, continued = _split_operands(nxt[2:].lstrip())
            operands.extend(more)
            i += 1
        stmt = Stmt(number, name, op, operands, file)
        out.append(stmt)
        if op == "DD":
            first = (stmt.positional() or "").upper()
            if first in ("*", "DATA"):
                dlm = (stmt.keyword("DLM") or "").strip("'")
                i = _read_data(lines, i, stmt, first, dlm)
    return out


def _read_data(lines: List[str], i: int, stmt: Stmt, kind: str, dlm: str) -> int:
    """Collect in-stream data after ``stmt``; returns the index after it."""
    n = len(lines)
    while i < n:
        raw = lines[i]
        if dlm:
            if raw.startswith(dlm):
                return i + 1
        elif raw.startswith("/*"):
            return i + 1
        elif kind == "*" and raw.startswith("//"):
            return i
        stmt.data.append((i + 1, raw[:72]))
        i += 1
    return i


# ------------------------------------------------------------------ library


@dataclass
class _Source:
    path: str
    stmts: List[Stmt]
    has_job: bool


class JclLibrary:
    """Every JCL file of the scan, with members and PROCs indexed by name."""

    def __init__(self, sources: Sequence[Tuple[str, str]]):
        self.sources: List[_Source] = []
        self.members: Dict[str, Set[str]] = {}
        self.procs: Dict[str, Set[str]] = {}
        for path, text in sorted(sources):
            stmts = statements(text, path)
            has_job = any(s.op == "JOB" for s in stmts)
            source = _Source(path, stmts, has_job)
            self.sources.append(source)
            if has_job:
                continue
            # A cataloged PROC or INCLUDE member is called by its member (file)
            # name; the label on its PROC statement is not used.
            stem = Path(path).stem.upper()
            self.members.setdefault(stem, set()).add(path)
            self.procs.setdefault(stem, set()).add(path)
        self._by_path = {s.path: s for s in self.sources}

    def stmts(self, path: str) -> List[Stmt]:
        return self._by_path[path].stmts


def _spliced(
    lib: JclLibrary, stmts: List[Stmt], misses: List[Stmt], seen: Tuple[str, ...] = ()
) -> List[Stmt]:
    """``stmts`` with ``INCLUDE MEMBER=`` replaced by the member's statements."""
    out: List[Stmt] = []
    for stmt in stmts:
        if stmt.op != "INCLUDE":
            out.append(stmt)
            continue
        member = (stmt.keyword("MEMBER") or "").upper()
        paths = lib.members.get(member, set())
        if len(paths) != 1 or member in seen:
            misses.append(stmt)
            continue
        out.extend(_spliced(lib, lib.stmts(next(iter(paths))), misses, seen + (member,)))
    return out


def _steps(stmts: Iterable[Stmt]) -> List[Step]:
    """Steps of a statement list (no JOB/PROC handling); DDs attach to the last step."""
    steps: List[Step] = []
    last_dd = ""
    for stmt in stmts:
        if stmt.op == "EXEC":
            pgm = stmt.keyword("PGM")
            proc = stmt.keyword("PROC") or (None if pgm else stmt.positional())
            steps.append(
                Step(
                    name=stmt.name,
                    line=stmt.line,
                    file=stmt.file,
                    pgm=pgm.upper() if pgm else None,
                    proc=proc.upper() if proc else None,
                    parm=stmt.keyword("PARM"),
                )
            )
            last_dd = ""
        elif stmt.op == "DD" and steps:
            name = stmt.name or last_dd  # unnamed DD: concatenation
            last_dd = name
            dsn = stmt.keyword("DSN") or stmt.keyword("DSNAME")
            dd = DD(name, stmt.line, stmt.file, dsn.upper() if dsn else None, stmt.data)
            step = steps[-1]
            if "." in name and step.proc:
                proc_step, _, dd_name = name.partition(".")
                step.overrides.append((proc_step, replace(dd, name=dd_name)))
            else:
                step.dds.append(dd)
    return steps


def _proc_bodies(stmts: List[Stmt]) -> Tuple[Dict[str, List[Stmt]], List[Stmt]]:
    """In-stream PROCs (name -> body) and the statements outside them."""
    procs: Dict[str, List[Stmt]] = {}
    rest: List[Stmt] = []
    current: Optional[str] = None
    for stmt in stmts:
        if stmt.op == "PROC" and stmt.name:
            current = stmt.name
            procs[current] = []
        elif stmt.op == "PEND":
            current = None
        elif current is not None:
            procs[current].append(stmt)
        else:
            rest.append(stmt)
    return procs, rest


def _cataloged_body(stmts: List[Stmt]) -> List[Stmt]:
    return [s for s in stmts if s.op not in ("PROC", "PEND")]


_MAX_DEPTH = 15  # JCL allows 15 levels of nested PROCs


class _Expander:
    def __init__(self, lib: JclLibrary):
        self.lib = lib
        self.steps: List[ResolvedStep] = []
        self.unresolved: List[Tuple[Job, str, Unresolved]] = []

    def expand(
        self,
        job: Job,
        steps: List[Step],
        prefix: str,
        local: Dict[str, List[Stmt]],
        stack: Tuple[str, ...],
    ) -> None:
        for step in steps:
            path = f"{prefix}.{step.name or f'#{step.line}'}"
            if not step.proc:
                self.steps.append(ResolvedStep(job, path, step))
                continue
            body = self._proc(job, step, path, local, stack)
            if body is None:
                # Not expanded: the step stays a node so its unresolved entry has an owner.
                self.steps.append(ResolvedStep(job, path, step))
                continue
            inner = _steps(body)
            for proc_step in inner:
                for target, dd in step.overrides:
                    if target != proc_step.name:
                        continue
                    kept = [d for d in proc_step.dds if d.name != dd.name]
                    if len(kept) == len(proc_step.dds):
                        proc_step.dds.append(dd)
                    else:
                        index = next(i for i, d in enumerate(proc_step.dds) if d.name == dd.name)
                        kept.insert(index, dd)
                        proc_step.dds = kept
            self.expand(job, inner, path, local, stack + (step.proc,))

    def _proc(
        self,
        job: Job,
        step: Step,
        path: str,
        local: Dict[str, List[Stmt]],
        stack: Tuple[str, ...],
    ) -> Optional[List[Stmt]]:
        name = step.proc or ""

        def miss(reason: str) -> None:
            entry = Unresolved("EXEC_PROC", path, name, reason, step.file, step.line)
            self.unresolved.append((job, path, entry))

        if name in stack or len(stack) >= _MAX_DEPTH:
            miss("proc_recursion")
            return None
        if name in local:
            return _spliced(self.lib, local[name], [])
        paths = self.lib.procs.get(name, set())
        if not paths:
            miss("proc_not_found")
            return None
        if len(paths) > 1:
            miss("ambiguous")
            return None
        misses: List[Stmt] = []
        body = _spliced(self.lib, _cataloged_body(self.lib.stmts(next(iter(paths)))), misses)
        for stmt in misses:
            member = (stmt.keyword("MEMBER") or "").upper()
            entry = Unresolved("INCLUDE", path, member, "include_not_found", stmt.file, stmt.line)
            self.unresolved.append((job, path, entry))
        return body


def build_model(sources: Sequence[Tuple[str, str]]) -> JclModel:
    """Jobs, expanded steps and unresolved entries of the JCL ``sources``."""
    lib = JclLibrary(sources)
    expander = _Expander(lib)
    jobs: List[Job] = []
    for source in lib.sources:
        if not source.has_job:
            continue
        misses: List[Stmt] = []
        stmts = _spliced(lib, source.stmts, misses)
        local, rest = _proc_bodies(stmts)
        current: Optional[Job] = None
        chunks: List[Tuple[Job, List[Stmt]]] = []
        for stmt in rest:
            if stmt.op == "JOB":
                current = Job(stmt.name or Path(source.path).stem.upper(), stmt.line, source.path)
                jobs.append(current)
                chunks.append((current, []))
            elif current is not None:
                chunks[-1][1].append(stmt)
        for stmt in misses:
            owner = next((j for j in reversed(jobs) if j.file == source.path), None)
            if owner is None:
                continue
            member = (stmt.keyword("MEMBER") or "").upper()
            entry = Unresolved("INCLUDE", "", member, "include_not_found", stmt.file, stmt.line)
            expander.unresolved.append((owner, "", entry))
        for job, body in chunks:
            job.steps = _steps(body)
            expander.expand(job, job.steps, job.name, local, ())
    return JclModel(jobs, expander.steps, expander.unresolved)


def jcl_files(roots: Sequence[Path], exclude_patterns: Sequence[str]) -> List[Path]:
    """``.jcl``, ``.prc`` and ``.proc`` files under ``roots`` (default + user excludes)."""
    from hefesto.core.analyzer_engine import (
        DEFAULT_EXCLUDES,
        _relative_parts,
        path_is_excluded,
    )

    excludes = list(DEFAULT_EXCLUDES) + list(exclude_patterns)
    found: List[Path] = []
    for root in roots:
        if root.is_file():
            if root.suffix.lower() in JCL_SUFFIXES:
                found.append(root)
            continue
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = _relative_parts(Path(dirpath), root)
            dirnames[:] = sorted(
                d
                for d in dirnames
                if not d.startswith(".")
                and not path_is_excluded(rel_dir + (d,), excludes, is_dir=True)
            )
            for name in sorted(filenames):
                if Path(name).suffix.lower() in JCL_SUFFIXES and not path_is_excluded(
                    rel_dir + (name,), excludes
                ):
                    found.append(Path(dirpath) / name)
    return sorted(set(found))


def read_model(roots: Sequence[Path], exclude_patterns: Sequence[str]) -> JclModel:
    sources = []
    for path in jcl_files(roots, exclude_patterns):
        try:
            sources.append((str(path), path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return build_model(sources)


def parm_operands(parm: str) -> List[str]:
    """Operands of a PARM value: ``'A,B'`` or ``(A,B)``."""
    value = parm.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    value = value.strip("'")
    return [part.strip().strip("'") for part in value.split(",")]


def run_programs(dd: DD) -> List[Tuple[int, str]]:
    """``RUN PROGRAM(X)`` names in the in-stream data of a SYSTSIN DD."""
    out = []
    for number, text in dd.data:
        for match in _RUN_PROGRAM.finditer(text):
            out.append((number, match.group(1).strip("'").upper()))
    return out
