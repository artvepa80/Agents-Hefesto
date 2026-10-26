"""Git side of the critical-test guard: merge-base, changed files, renames.

``changed_files`` runs ``git diff -z --name-status -M`` between two commits
and returns one ``FileChange`` per path. A rename (``R###``) keeps both paths,
so ``pair_test_files`` can hand the comparator the old path's base source and
the new path's head source instead of reporting the test as deleted.

Copyright 2026 Narapa LLC, Miami, Florida
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

ADDED = "ADDED"
MODIFIED = "MODIFIED"
DELETED_FILE = "DELETED_FILE"
RENAMED = "RENAMED"

_SIMPLE_STATUSES = {"A": ADDED, "M": MODIFIED, "T": MODIFIED, "D": DELETED_FILE}

# Variables that would point git at another repository than ``repo``.
_REPO_LOCATING_GIT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)

PathLike = Union[str, Path]


class GitError(RuntimeError):
    """A git command failed or printed output that could not be parsed."""


@dataclass(frozen=True)
class FileChange:
    status: str  # ADDED, MODIFIED, DELETED_FILE or RENAMED
    old_path: Optional[str]  # None when ADDED
    new_path: Optional[str]  # None when DELETED_FILE
    similarity: Optional[int] = None  # RENAMED only: git's score, 0-100


def _git_env() -> Dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _REPO_LOCATING_GIT_VARS}


def _run_git(repo: PathLike, args: List[str]) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
        env=_git_env(),
    )


def _git_output(repo: PathLike, args: List[str]) -> str:
    result = _run_git(repo, args)
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def merge_base(repo: PathLike, base_ref: str, head_ref: str = "HEAD") -> str:
    """Return the merge-base commit of ``base_ref`` and ``head_ref``."""
    sha = _git_output(repo, ["merge-base", base_ref, head_ref]).strip()
    if not sha:
        raise GitError(f"no merge-base between {base_ref} and {head_ref}")
    return sha


def _take(fields: List[str], index: int, status: str) -> str:
    if index >= len(fields):
        raise GitError(f"truncated git name-status output after status {status!r}")
    return fields[index]


def _parse_one(fields: List[str], index: int) -> Tuple[FileChange, int]:
    status = fields[index]
    code = status[:1]
    if code == "R":
        old = _take(fields, index + 1, status)
        new = _take(fields, index + 2, status)
        score = int(status[1:]) if status[1:].isdigit() else None
        return FileChange(RENAMED, old, new, similarity=score), index + 3
    kind = _SIMPLE_STATUSES.get(code)
    if kind is None:
        raise GitError(f"unsupported git name-status {status!r}")
    path = _take(fields, index + 1, status)
    old_path = None if kind == ADDED else path
    new_path = None if kind == DELETED_FILE else path
    return FileChange(kind, old_path, new_path), index + 2


def parse_name_status(raw: str) -> List[FileChange]:
    """Parse ``git diff -z --name-status`` output."""
    fields = raw.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    changes: List[FileChange] = []
    index = 0
    while index < len(fields):
        change, index = _parse_one(fields, index)
        changes.append(change)
    return changes


def changed_files(repo: PathLike, base: str, head: str) -> List[FileChange]:
    """Files changed from ``base`` to ``head``, with renames detected.

    ``--no-renames`` user config and external diff drivers do not apply:
    ``-M`` is passed explicitly and ``--no-ext-diff`` is set.
    """
    args = ["diff", "-z", "--name-status", "-M", "--no-ext-diff", "--no-color", base, head]
    return parse_name_status(_git_output(repo, args))


def read_file_at(repo: PathLike, ref: str, path: str) -> Optional[str]:
    """Contents of ``path`` at ``ref``, or None when it does not exist there."""
    spec = f"{ref}:{path}"
    if _run_git(repo, ["cat-file", "-e", spec]).returncode != 0:
        return None
    return _git_output(repo, ["show", "--no-textconv", spec])


def pair_test_files(
    changes: Iterable[FileChange], mapped_paths: Iterable[str]
) -> List[Tuple[str, Optional[str]]]:
    """``(base_path, head_path)`` for each mapped test file the diff touched.

    ``head_path`` is the new path for a rename and None for a deletion.
    Mapped files the diff did not touch, and added files, are left out.
    """
    by_old = {c.old_path: c for c in changes if c.old_path is not None}
    pairs: List[Tuple[str, Optional[str]]] = []
    for path in mapped_paths:
        change = by_old.get(path)
        if change is not None:
            pairs.append((path, change.new_path))
    return pairs


__all__ = [
    "ADDED",
    "DELETED_FILE",
    "MODIFIED",
    "RENAMED",
    "FileChange",
    "GitError",
    "changed_files",
    "merge_base",
    "pair_test_files",
    "parse_name_status",
    "read_file_at",
]
