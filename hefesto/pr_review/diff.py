"""Unified-diff parser for Phase 2 PR review.

Stdlib-only state machine that extracts the set of new-side line numbers
for each touched file in a ``git diff`` output. Deliberately minimal —
we only need enough information to answer "does finding at file F line
L fall within a hunk?" for the reporter's filtering pass.

What we parse:
- File headers: ``diff --git a/<old> b/<new>``
- File delimiters: ``--- a/<path>`` / ``--- /dev/null`` (for new files)
- File delimiters: ``+++ b/<path>`` / ``+++ /dev/null`` (for deletions)
- Hunk headers: ``@@ -old_start[,old_count] +new_start[,new_count] @@ ...``
- Hunk body: ``+`` additions, ``-`` deletions, `` `` context, ``\\`` no-newline

What we skip:
- Binary file markers (``Binary files ... differ``) — set ``is_binary`` True,
  no hunks collected.
- Git extended headers (``index``, ``old mode``, ``new mode``, ``similarity
  index``, ``rename from``, ``rename to``, ``copy from``, ``copy to``,
  ``deleted file``, ``new file``) — ignored between ``diff --git`` and the
  first ``---`` line.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

_DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<old>.+?) b/(?P<new>.+?)$")
_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)
_FROM_FILE_RE = re.compile(r"^--- (?:a/)?(?P<path>.+?)(?:\t.*)?$")
_TO_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>.+?)(?:\t.*)?$")
_DEV_NULL = "/dev/null"


@dataclass
class Hunk:
    """A single hunk within a file's diff.

    ``changed_lines`` contains the new-side line numbers for additions
    only — context lines are not included because they are unchanged and
    deletions have no new-side line number.
    """

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    changed_lines: Set[int] = field(default_factory=set)


@dataclass
class FileDiff:
    """All hunks for a single file in a unified diff."""

    old_path: Optional[str]
    new_path: Optional[str]
    hunks: List[Hunk] = field(default_factory=list)
    is_binary: bool = False

    @property
    def path(self) -> Optional[str]:
        """The new-side path if the file still exists, else the old path."""
        if self.new_path and self.new_path != _DEV_NULL:
            return self.new_path
        return self.old_path

    @property
    def is_new_file(self) -> bool:
        return self.old_path == _DEV_NULL

    @property
    def is_deleted_file(self) -> bool:
        return self.new_path == _DEV_NULL

    @property
    def changed_lines(self) -> Set[int]:
        """Union of new-side changed line numbers across all hunks."""
        out: Set[int] = set()
        for hunk in self.hunks:
            out.update(hunk.changed_lines)
        return out


def parse_unified_diff(text: str) -> List[FileDiff]:
    """Parse a ``git diff`` output into a list of ``FileDiff`` entries.

    Robust to the common real-world cases: added/deleted/renamed files,
    binary markers, no-newline markers, and hunks with implicit counts
    (``@@ -1 +1 @@`` with no count means count=1).
    """
    files: List[FileDiff] = []
    current: Optional[FileDiff] = None
    current_hunk: Optional[Hunk] = None
    new_line_cursor: int = 0

    def _finalize_hunk() -> None:
        nonlocal current_hunk
        current_hunk = None

    def _finalize_file() -> None:
        nonlocal current
        if current is not None:
            files.append(current)
        current = None

    for raw in text.splitlines():
        # File header — start of a new file entry.
        header = _DIFF_HEADER_RE.match(raw)
        if header:
            _finalize_hunk()
            _finalize_file()
            current = FileDiff(old_path=header.group("old"), new_path=header.group("new"))
            continue

        if current is None:
            # Data outside any known file header — ignore (git can emit
            # preamble text like "warning:" lines).
            continue

        if raw.startswith("Binary files "):
            current.is_binary = True
            _finalize_hunk()
            continue

        from_match = _FROM_FILE_RE.match(raw)
        if from_match:
            path = from_match.group("path").strip()
            current.old_path = _DEV_NULL if path == "/dev/null" else path
            continue

        to_match = _TO_FILE_RE.match(raw)
        if to_match:
            path = to_match.group("path").strip()
            current.new_path = _DEV_NULL if path == "/dev/null" else path
            continue

        hunk_match = _HUNK_HEADER_RE.match(raw)
        if hunk_match:
            _finalize_hunk()
            old_start = int(hunk_match.group("old_start"))
            old_count = int(hunk_match.group("old_count") or "1")
            new_start = int(hunk_match.group("new_start"))
            new_count = int(hunk_match.group("new_count") or "1")
            current_hunk = Hunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
            )
            current.hunks.append(current_hunk)
            new_line_cursor = new_start
            continue

        if current_hunk is None:
            # Still in the extended-header zone before the first hunk —
            # ignore index/mode/rename metadata.
            continue

        # Hunk body lines.
        if raw.startswith("+") and not raw.startswith("+++"):
            current_hunk.changed_lines.add(new_line_cursor)
            new_line_cursor += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            # Deletion: the old side advances, the new side does not.
            pass
        elif raw.startswith(" "):
            # Context line on both sides.
            new_line_cursor += 1
        elif raw.startswith("\\"):
            # "\\ No newline at end of file" marker — ignore.
            pass
        else:
            # Unknown non-hunk line inside a hunk body signals the end of
            # this file's diff in practice (blank lines are rare here).
            continue

    _finalize_hunk()
    _finalize_file()
    return files


__all__ = ["Hunk", "FileDiff", "parse_unified_diff"]
