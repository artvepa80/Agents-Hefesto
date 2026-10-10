"""Project-wide COPY index for the COBOL analyzer (COBOL007 and COBOL015).

Built once per ``hefesto analyze`` run from every scanned COBOL file:

* which copybook names exist in the scanned tree (file stems, upper case),
* which programs COPY (or ``EXEC SQL INCLUDE``) each name, and
* which files are copybooks even though their extension is not a COBOL one
  (DB2 DCLGEN ``.dcl``, ``.copy``/``.cbk`` and extension-less copylib members).

Copybook directories outside the scan (``copybook_paths`` in ``.hefesto.yaml``
or ``--copybook-path``) add names that resolve; their files are expanded into
the programs that COPY them (``resolve`` / ``copybook_lines``) but are not
analyzed on their own.

COBOL007 (copybook blast radius) is reported on the copybook file itself when
enough programs depend on it; COBOL015 (copybook not found) is reported in a
program that COPYs a name that is not in the scanned tree. Without an index
(e.g. a single in-memory snippet) neither rule fires, because the analyzer
cannot know either fact.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Set, Tuple

COPYBOOK_EXTENSIONS = (".cpy",)
# Copybook files that file discovery does not pick up: DB2 DCLGEN members,
# other copybook extensions and extension-less copylib members. They are
# indexed (and analyzed as copybooks) only when their content looks like COBOL
# data definitions.
EXTRA_COPYBOOK_SUFFIXES = ("", ".dcl", ".copy", ".cbk")
MAX_COPYBOOK_BYTES = 512 * 1024
# Logical lines of copybooks kept in memory for COPY expansion (characters).
MAX_CACHED_COPYBOOK_CHARS = 64 * 1024 * 1024

logger = logging.getLogger(__name__)
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
    if "'" not in text and '"' not in text:
        return text
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
    out: List[Tuple[int, str]] = []
    upper_text = text.upper()
    if "COPY" not in upper_text and "EXEC" not in upper_text:
        return out  # fast path: nothing to find
    in_sql = False
    for num, raw in enumerate(text.splitlines(), start=1):
        if not in_sql and not _may_hold_copy(raw):
            continue  # cheap test on the raw line first
        if fixed is None:
            fixed = is_fixed_format(text)  # only when some line may hold a COPY
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
    """Copybook names present in the scan and the programs that COPY each one.

    ``dependents`` is transitive: a program that COPYs ``TOP``, where ``TOP``
    COPYs ``MID`` and ``MID`` COPYs ``LEAF``, depends on all three.
    """

    available: Set[str] = field(default_factory=set)
    dependents: Dict[str, Set[str]] = field(default_factory=dict)
    # Copybooks without a COBOL extension found in the scanned tree (paths as given).
    copybook_files: Set[str] = field(default_factory=set)
    # COPY/INCLUDE names nested inside each copybook (by copybook name).
    nested: Dict[str, Set[str]] = field(default_factory=dict)
    # (line, NAME) per scanned file, so the analyzer does not parse COPY twice.
    _copy_cache: Dict[str, List[Tuple[int, str]]] = field(default_factory=dict, repr=False)
    _resolves_any: Optional[bool] = field(default=None, repr=False)
    # COPY expansion: files per name (scanned first, then copybook_paths), the
    # scanned paths, and the logical lines of copybooks already read.
    files_by_name: Dict[str, List[str]] = field(default_factory=dict, repr=False)
    library_files: Set[str] = field(default_factory=set, repr=False)
    scanned: Set[str] = field(default_factory=set, repr=False)
    _lines_cache: Dict[str, Any] = field(default_factory=dict, repr=False)
    _lines_cached_chars: int = field(default=0, repr=False)
    expander: Any = field(default=None, repr=False)

    @classmethod
    def from_sources(
        cls,
        sources: Iterable[Tuple[str, str]],
        extra_copybooks: Iterable[Tuple[str, str]] = (),
        library_names: Iterable[str] = (),
        library_files: Optional[Dict[str, str]] = None,
    ) -> "CobolProjectIndex":
        """Build the index.

        ``sources``: scanned COBOL files (path, text). ``extra_copybooks``:
        candidate copybook files without a COBOL extension (path, text); kept
        only if their content looks like COBOL data and some scanned program
        COPYs their name. ``library_names``: copybook names available from
        ``copybook_paths`` outside the scan; ``library_files`` maps those
        names to their files (used to expand COPY).
        """
        index = cls()
        direct: Dict[str, Set[str]] = {}  # program path -> names it COPYs
        for path, text in sources:
            names = copy_names(text)
            index._copy_cache[str(path)] = names
            index.available.add(Path(path).stem.upper())
            index._add_file(str(path))
            index._record(str(path), names, direct, is_copybook_path(path))
        referenced = {name for names in direct.values() for name in names}
        referenced |= {name for names in index.nested.values() for name in names}
        for path, text in extra_copybooks:
            name = Path(path).stem.upper()
            if name in referenced and looks_like_copybook(text):
                index.available.add(name)
                index.copybook_files.add(str(path))
                index._add_file(str(path))
                found = copy_names(text)
                index._copy_cache[str(path)] = found
                index._record(str(path), found, direct, True)
        index._add_library(library_names, library_files or {})
        for program, copied in direct.items():
            for name in index._closure(copied):
                index.dependents.setdefault(name, set()).add(program)
        return index

    def _add_library(self, names: Iterable[str], files: Dict[str, str]) -> None:
        """Names (and files, for expansion) from ``copybook_paths``."""
        self.available.update(name.upper() for name in names)
        for name, path in sorted(files.items()):
            self.files_by_name.setdefault(name.upper(), []).append(str(path))
            self.library_files.add(str(path))

    def _add_file(self, path: str) -> None:
        self.scanned.add(path)
        self.files_by_name.setdefault(Path(path).stem.upper(), []).append(path)

    def resolve(self, name: str, from_path: str) -> Optional[str]:
        """File that ``COPY name`` in ``from_path`` brings in (None if unknown).

        Copybook files win over programs of the same name; then the file
        closest to the including file (longest common directory); then the
        path order.
        """
        candidates = self.files_by_name.get(name.upper())
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        here = Path(from_path).parent.parts

        def rank(path: str) -> Tuple[int, int, str]:
            copybook = self.is_copybook_file(path) or path in self.library_files
            parts = Path(path).parent.parts
            common = 0
            for a, b in zip(here, parts):
                if a != b:
                    break
                common += 1
            return (0 if copybook else 1, -common, path)

        return min(candidates, key=rank)

    def is_scanned(self, path: str) -> bool:
        """True for files of the scan (analyzed on their own), not copybook_paths."""
        return path in self.scanned

    def copybook_lines(self, path: str, build: Callable[[str], Any]) -> Any:
        """``build(text)`` of a copybook file, cached (None if unreadable or too big)."""
        if path in self._lines_cache:
            return self._lines_cache[path]
        result = None
        try:
            if Path(path).stat().st_size <= MAX_COPYBOOK_BYTES:
                result = build(Path(path).read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            result = None
        size = sum(len(line[1]) for line in result) if result else 0
        if self._lines_cached_chars + size <= MAX_CACHED_COPYBOOK_CHARS:
            self._lines_cache[path] = result
            self._lines_cached_chars += size
        return result

    def _record(
        self,
        path: str,
        names: List[Tuple[int, str]],
        direct: Dict[str, Set[str]],
        is_copybook: bool,
    ) -> None:
        if is_copybook:
            self.nested.setdefault(Path(path).stem.upper(), set()).update(n for _, n in names)
        elif names:
            direct[path] = {n for _, n in names}

    def _closure(self, names: Set[str]) -> Set[str]:
        """``names`` plus every copybook they COPY, at any depth (cycle-safe)."""
        seen: Set[str] = set()
        stack = list(names)
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            stack.extend(self.nested.get(name, ()))
        return seen

    def copy_names_for(self, path: str) -> Optional[List[Tuple[int, str]]]:
        """COPY/INCLUDE names already read for ``path`` (None if not indexed)."""
        return self._copy_cache.get(str(path))

    @classmethod
    def from_paths(
        cls,
        paths: Iterable[Path],
        extra_copybooks: Iterable[Path] = (),
        library_dirs: Iterable[Path] = (),
        library_names: Optional[Iterable[str]] = None,
    ) -> "CobolProjectIndex":
        """Index ``paths``.

        ``library_names`` (a set of names, or a name -> file mapping as
        returned by :func:`library_copybook_files`) skips the
        ``library_dirs`` walk; with a mapping, those files can be expanded.
        """
        if library_names is None:
            dirs = list(library_dirs)
            library_names = library_copybook_files(dirs) if dirs else {}
        files = library_names if isinstance(library_names, dict) else None
        return cls.from_sources(
            _read_all(paths),
            _read_all(p for p in extra_copybooks if _small_file(p)),
            library_names,
            files,
        )

    def is_copybook_file(self, path: str) -> bool:
        return is_copybook_path(path) or str(path) in self.copybook_files

    @property
    def resolves_any(self) -> bool:
        """True when at least one user COPY in the scan points at a scanned file.

        COBOL015 only runs then: if no COPY resolves, the copybooks were simply
        not part of the scan and every COPY would be reported.
        """
        if self._resolves_any is None:
            self._resolves_any = any(name in self.available for name in self.dependents)
        return self._resolves_any

    def is_missing(self, name: str) -> bool:
        return self.resolves_any and not is_system_copybook(name) and name not in self.available

    def dependent_programs(self, name: str) -> List[str]:
        return sorted(self.dependents.get(name.upper(), set()))


def _small_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size <= MAX_COPYBOOK_BYTES
    except OSError:
        return False


def _read_all(paths: Iterable[Path]) -> Iterator[Tuple[str, str]]:
    """(path, text) one file at a time, so indexing never holds every source."""
    for path in paths:
        try:
            yield str(path), path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue


def is_extra_copybook_candidate(path: Path) -> bool:
    """A file name that may be a copybook file discovery does not pick up."""
    return path.suffix.lower() in EXTRA_COPYBOOK_SUFFIXES and not path.name.startswith(".")


# Bounds for the ``copybook_paths`` search, so pointing it at a huge tree
# (or ``/``) cannot make a scan crawl: directories deeper than
# LIBRARY_MAX_DEPTH below a copybook path, and files past LIBRARY_MAX_FILES
# per run, are not looked at (a warning says so).
LIBRARY_MAX_DEPTH = 8
LIBRARY_MAX_FILES = 50_000


def library_copybook_names(
    dirs: Iterable[Path],
    max_depth: int = LIBRARY_MAX_DEPTH,
    max_files: int = LIBRARY_MAX_FILES,
) -> Set[str]:
    """Copybook names in ``copybook_paths`` directories (searched recursively)."""
    return set(library_copybook_files(dirs, max_depth, max_files))


def library_copybook_files(
    dirs: Iterable[Path],
    max_depth: int = LIBRARY_MAX_DEPTH,
    max_files: int = LIBRARY_MAX_FILES,
) -> Dict[str, str]:
    """NAME -> file for copybooks in ``copybook_paths`` directories (recursive).

    COBOL extensions count by name; other candidates (``.dcl``, extension-less
    members, ...) only when their content looks like a copybook. Hidden
    directories are skipped and the walk is bounded (see LIBRARY_MAX_*). The
    first file found for a name wins (directories in the given order, then
    sorted paths).
    """
    names: Dict[str, str] = {}
    seen = 0
    for directory in dirs:
        base_depth = str(directory).rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(directory):
            depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            if depth >= max_depth:
                dirnames[:] = []
            for filename in sorted(filenames):
                seen += 1
                if seen > max_files:
                    logger.warning(
                        "copybook_paths: stopped after %d files; copybooks beyond that "
                        "are not used to resolve COPY names",
                        max_files,
                    )
                    return names
                path = Path(dirpath) / filename
                name = _library_name(path)
                if name and name not in names:
                    names[name] = str(path)
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
