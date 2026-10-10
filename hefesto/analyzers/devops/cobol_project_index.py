"""Project-wide COPY index for the COBOL analyzer (COBOL007 and COBOL015).

Built once per ``hefesto analyze`` run from every scanned COBOL file:

* which copybook names exist in the scanned tree (file stems, upper case), and
* which programs COPY each name.

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


def copy_names(text: str) -> List[Tuple[int, str]]:
    """(line, NAME) for every COPY statement outside comments and literals."""
    out: List[Tuple[int, str]] = []
    for num, raw in enumerate(text.splitlines(), start=1):
        line = _code_part(raw)
        if "COPY" not in line.upper():
            continue
        masked = _mask(line)
        for match in _COPY.finditer(masked):
            name = _COPY_NAME.match(line, match.end())
            if name:
                out.append((num, name.group(1).upper()))
    return out


@dataclass
class CobolProjectIndex:
    """Copybook names present in the scan and the programs that COPY each one."""

    available: Set[str] = field(default_factory=set)
    dependents: Dict[str, Set[str]] = field(default_factory=dict)

    @classmethod
    def from_sources(cls, sources: Iterable[Tuple[str, str]]) -> "CobolProjectIndex":
        index = cls()
        for path, text in sources:
            index.available.add(Path(path).stem.upper())
            if is_copybook_path(path):
                continue
            for _, name in copy_names(text):
                index.dependents.setdefault(name, set()).add(str(path))
        return index

    @classmethod
    def from_paths(cls, paths: Iterable[Path]) -> "CobolProjectIndex":
        sources = []
        for path in paths:
            try:
                sources.append((str(path), path.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
        return cls.from_sources(sources)

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


def stem_of(path: str) -> Optional[str]:
    return Path(path).stem.upper() if path else None
