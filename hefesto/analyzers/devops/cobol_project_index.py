"""Project-wide COPY index for the COBOL analyzer (COBOL007 and COBOL015).

Built once per ``hefesto analyze`` run from every scanned COBOL file:

* which copybook names exist in the scanned tree (file stems, upper case),
* which programs COPY (or ``EXEC SQL INCLUDE``) each name, and
* which files are copybooks even though their extension is not a COBOL one
  (DB2 DCLGEN ``.dcl``, ``.copy``/``.cbk`` and extension-less copylib members).

Copybook directories outside the scan (``copybook_paths`` in ``.hefesto.yaml``
or ``--copybook-path``) only add names that resolve; their files are not
analyzed.

COBOL007 (copybook blast radius) is reported on the copybook file itself when
enough programs depend on it; COBOL015 (copybook not found) is reported in a
program that COPYs a name that is not in the scanned tree. Without an index
(e.g. a single in-memory snippet) neither rule fires, because the analyzer
cannot know either fact.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

COPYBOOK_EXTENSIONS = (".cpy",)
# Copybook files that file discovery does not pick up: DB2 DCLGEN members,
# other copybook extensions and extension-less copylib members. They are
# indexed (and analyzed as copybooks) only when their content looks like COBOL
# data definitions.
EXTRA_COPYBOOK_SUFFIXES = ("", ".dcl", ".copy", ".cbk")
MAX_COPYBOOK_BYTES = 512 * 1024
_DATA_ENTRY_LINE = re.compile(
    r"^(?:[\d ]{6}[ D]|\s*)\s*(?:0?[1-9]|[1-4]\d|66|77|88)\s+[A-Z][A-Z0-9-]*\b",
    re.I | re.M,
)
_SQL_DECLARE = re.compile(r"\bEXEC\s+SQL\s+DECLARE\b", re.I)
_INCLUDE = re.compile(r"\bINCLUDE\s+[\"']?([A-Za-z0-9][A-Za-z0-9_-]*)", re.I)
_EXEC_SQL = re.compile(r"\bEXEC\s+SQL\b", re.I)
_END_EXEC = re.compile(r"\bEND-EXEC\b", re.I)
_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")
_COPY = re.compile(r"(?<![\w-])COPY\s+", re.I)
_COPY_NAME = re.compile(r"[\"']?([A-Za-z0-9][A-Za-z0-9_-]*)")
_SEQ_AREA = re.compile(r"^[\d ]{6}")

# Vendor-supplied copybooks (CICS DFH*, IBM MQ CMQ*, DB2 SQLCA/SQLDA): not user code.
SYSTEM_COPYBOOKS = {"SQLCA", "SQLDA"}
SYSTEM_COPYBOOK_PREFIXES = ("DFH", "CMQ")  # CICS, IBM MQ


def is_system_copybook(name: str) -> bool:
    upper = name.upper()
    return upper in SYSTEM_COPYBOOKS or upper.startswith(SYSTEM_COPYBOOK_PREFIXES)


def is_copybook_path(path: str) -> bool:
    return path.lower().endswith(COPYBOOK_EXTENSIONS)


def _mask(text: str) -> str:
    return _LITERAL.sub(
        lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1], text
    )


def _code_part(line: str) -> str:
    """Drop fixed-format comment lines, sequence area and inline ``*>`` comments."""
    if len(line) > 6 and _SEQ_AREA.match(line) and line[6] in "*/":
        return ""
    stripped = line.lstrip()
    if stripped.startswith("*>") or (stripped.startswith("*") and len(line) - len(stripped) < 7):
        return ""
    cut = line.find("*>")
    return line if cut < 0 else line[:cut]


def looks_like_copybook(text: str) -> bool:
    """True if ``text`` holds COBOL data definitions (level-number entries or a
    DCLGEN ``EXEC SQL DECLARE``). Used for files without a COBOL extension."""
    return bool(_DATA_ENTRY_LINE.search(text) or _SQL_DECLARE.search(text))


def copy_names(text: str, fixed: Optional[bool] = None) -> List[Tuple[int, str]]:
    """(line, NAME) for every COPY and ``EXEC SQL INCLUDE`` outside comments and literals.

    In fixed format only columns 1-72 count: NIST-style sources keep an
    identification area in 73-80 that would otherwise glue onto a COPY name
    written up to column 72. ``fixed=None`` detects the format.
    """
    if fixed is None:
        fixed = is_fixed_format(text)
    out: List[Tuple[int, str]] = []
    in_sql = False
    for num, raw in enumerate(text.splitlines(), start=1):
        line = _code_part(raw[:72] if fixed else raw)
        if not in_sql and not _may_hold_copy(line):
            continue
        masked = _mask(line)
        for match in _COPY.finditer(masked):
            name = _COPY_NAME.match(line, match.end())
            if name:
                out.append((num, name.group(1).upper()))
        out.extend((num, name) for name in _sql_includes(masked, in_sql))
        in_sql = _still_in_sql(masked, in_sql)
    return out


def _may_hold_copy(line: str) -> bool:
    upper = line.upper()
    return "COPY" in upper or "EXEC" in upper


def is_fixed_format(text: str) -> bool:
    """Same format decision as the COBOL analyzer (directive, then inference)."""
    from hefesto.analyzers.devops.cobol_governance_analyzer import _CobolStructuralExtractor

    return _CobolStructuralExtractor()._detect_fixed_format(text.split("\n"))


def _sql_includes(masked: str, in_sql: bool) -> List[str]:
    """INCLUDE member names inside EXEC SQL ... END-EXEC on one (masked) line."""
    names = []
    pos = 0
    while pos <= len(masked):
        if not in_sql:
            start = _EXEC_SQL.search(masked, pos)
            if not start:
                break
            pos, in_sql = start.end(), True
        end = _END_EXEC.search(masked, pos)
        stop = end.start() if end else len(masked)
        for match in _INCLUDE.finditer(masked, pos, stop):
            names.append(match.group(1).upper())
        if not end:
            break
        pos, in_sql = end.end(), False
    return names


def _still_in_sql(masked: str, in_sql: bool) -> bool:
    """Whether an EXEC SQL block is still open at the end of the line."""
    last_exec = [m.end() for m in _EXEC_SQL.finditer(masked)]
    last_end = [m.end() for m in _END_EXEC.finditer(masked)]
    if not last_exec and not last_end:
        return in_sql
    return bool(last_exec) and (not last_end or last_exec[-1] > last_end[-1])


@dataclass
class CobolProjectIndex:
    """Copybook names present in the scan and the programs that COPY each one."""

    available: Set[str] = field(default_factory=set)
    dependents: Dict[str, Set[str]] = field(default_factory=dict)
    # Copybooks without a COBOL extension found in the scanned tree (paths as given).
    copybook_files: Set[str] = field(default_factory=set)

    @classmethod
    def from_sources(
        cls,
        sources: Iterable[Tuple[str, str]],
        extra_copybooks: Iterable[Tuple[str, str]] = (),
        library_names: Iterable[str] = (),
    ) -> "CobolProjectIndex":
        """Build the index.

        ``sources``: scanned COBOL files (path, text). ``extra_copybooks``:
        candidate copybook files without a COBOL extension (path, text); kept
        only if their content looks like COBOL data and some scanned program
        COPYs their name. ``library_names``: copybook names available from
        ``copybook_paths`` outside the scan.
        """
        index = cls()
        for path, text in sources:
            index.available.add(Path(path).stem.upper())
            if is_copybook_path(path):
                continue
            for _, name in copy_names(text):
                index.dependents.setdefault(name, set()).add(str(path))
        for path, text in extra_copybooks:
            name = Path(path).stem.upper()
            if name in index.dependents and looks_like_copybook(text):
                index.available.add(name)
                index.copybook_files.add(str(path))
        index.available.update(name.upper() for name in library_names)
        return index

    @classmethod
    def from_paths(
        cls,
        paths: Iterable[Path],
        extra_copybooks: Iterable[Path] = (),
        library_dirs: Iterable[Path] = (),
    ) -> "CobolProjectIndex":
        return cls.from_sources(
            _read_all(paths),
            _read_all(p for p in extra_copybooks if _small_file(p)),
            library_copybook_names(library_dirs),
        )

    def is_copybook_file(self, path: str) -> bool:
        return is_copybook_path(path) or str(path) in self.copybook_files

    @property
    def resolves_any(self) -> bool:
        """True when at least one user COPY in the scan points at a scanned file.

        COBOL015 only runs then: if no COPY resolves, the copybooks were simply
        not part of the scan and every COPY would be reported.
        """
        return any(name in self.available for name in self.dependents)

    def is_missing(self, name: str) -> bool:
        return self.resolves_any and not is_system_copybook(name) and name not in self.available

    def dependent_programs(self, name: str) -> List[str]:
        return sorted(self.dependents.get(name.upper(), set()))


def _small_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size <= MAX_COPYBOOK_BYTES
    except OSError:
        return False


def _read_all(paths: Iterable[Path]) -> List[Tuple[str, str]]:
    sources = []
    for path in paths:
        try:
            sources.append((str(path), path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return sources


def is_extra_copybook_candidate(path: Path) -> bool:
    """A file name that may be a copybook file discovery does not pick up."""
    return path.suffix.lower() in EXTRA_COPYBOOK_SUFFIXES and not path.name.startswith(".")


def library_copybook_names(dirs: Iterable[Path]) -> Set[str]:
    """Copybook names in ``copybook_paths`` directories (searched recursively).

    COBOL extensions count by name; other candidates (``.dcl``, extension-less
    members, ...) only when their content looks like a copybook.
    """
    names: Set[str] = set()
    for directory in dirs:
        for path in sorted(Path(directory).rglob("*")):
            name = _library_name(path)
            if name:
                names.add(name)
    return names


def _library_name(path: Path) -> Optional[str]:
    """Copybook name of one ``copybook_paths`` file, or None if it is not one."""
    if not path.is_file():
        return None
    if path.suffix.lower() in COBOL_SOURCE_SUFFIXES:
        return path.stem.upper()
    if not (is_extra_copybook_candidate(path) and _small_file(path)):
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    return path.stem.upper() if looks_like_copybook(text) else None


COBOL_SOURCE_SUFFIXES = (".cpy", ".cbl", ".cob", ".cobol", ".pco")


def stem_of(path: str) -> Optional[str]:
    return Path(path).stem.upper() if path else None
