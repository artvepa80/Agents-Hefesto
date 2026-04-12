"""Tests for ``hefesto/pr_review/diff.py`` — unified-diff state machine.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from hefesto.pr_review import parse_unified_diff


def test_single_file_single_hunk_additions() -> None:
    diff = """diff --git a/foo.py b/foo.py
index e69de29..d00491f 100644
--- a/foo.py
+++ b/foo.py
@@ -0,0 +1,3 @@
+def hello():
+    return 1
+
"""
    files = parse_unified_diff(diff)
    assert len(files) == 1
    f = files[0]
    assert f.path == "foo.py"
    assert len(f.hunks) == 1
    assert f.hunks[0].new_start == 1
    assert f.changed_lines == {1, 2, 3}


def test_multiple_hunks_tracks_new_line_cursor_correctly() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -10,3 +10,4 @@ def first():
 existing_a
-removed
+added_at_11
 existing_b
@@ -50,2 +51,3 @@ def second():
 ctx
+added_at_52
 ctx
"""
    files = parse_unified_diff(diff)
    assert len(files) == 1
    hunks = files[0].hunks
    assert len(hunks) == 2
    # Hunk 1: context at 10, added at 11, context at 12
    assert 11 in hunks[0].changed_lines
    assert 10 not in hunks[0].changed_lines  # context line
    # Hunk 2: context at 51, added at 52, context at 53
    assert 52 in hunks[1].changed_lines
    assert files[0].changed_lines == {11, 52}


def test_hunk_header_implicit_count() -> None:
    """``@@ -1 +1 @@`` with no explicit count means count=1."""
    diff = """diff --git a/x.py b/x.py
--- a/x.py
+++ b/x.py
@@ -1 +1 @@
-old
+new
"""
    files = parse_unified_diff(diff)
    assert files[0].hunks[0].new_count == 1
    assert files[0].hunks[0].old_count == 1
    assert files[0].changed_lines == {1}


def test_new_file_has_dev_null_old_side() -> None:
    diff = """diff --git a/new.py b/new.py
new file mode 100644
index 0000000..abc
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+first
+second
"""
    files = parse_unified_diff(diff)
    assert files[0].is_new_file
    assert not files[0].is_deleted_file
    assert files[0].path == "new.py"
    assert files[0].changed_lines == {1, 2}


def test_deleted_file_has_dev_null_new_side() -> None:
    diff = """diff --git a/old.py b/old.py
deleted file mode 100644
index abc..0000000
--- a/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-first
-second
"""
    files = parse_unified_diff(diff)
    assert not files[0].is_new_file
    assert files[0].is_deleted_file
    # path falls back to old_path because new side is /dev/null
    assert files[0].path == "old.py"
    # No new-side additions — deletions don't count as "changed" for review
    assert files[0].changed_lines == set()


def test_binary_file_marker_short_circuits_hunk_collection() -> None:
    diff = """diff --git a/logo.png b/logo.png
index abc..def 100644
Binary files a/logo.png and b/logo.png differ
"""
    files = parse_unified_diff(diff)
    assert len(files) == 1
    assert files[0].is_binary
    assert files[0].hunks == []
    assert files[0].changed_lines == set()


def test_multiple_files_in_single_diff() -> None:
    diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-foo
+bar
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -5 +5,2 @@
 ctx
+new
"""
    files = parse_unified_diff(diff)
    assert [f.path for f in files] == ["a.py", "b.py"]
    assert files[0].changed_lines == {1}
    assert files[1].changed_lines == {6}


def test_no_newline_marker_is_ignored() -> None:
    diff = """diff --git a/x.py b/x.py
--- a/x.py
+++ b/x.py
@@ -1,2 +1,2 @@
-old_line
\\ No newline at end of file
+new_line
"""
    files = parse_unified_diff(diff)
    assert files[0].changed_lines == {1}


def test_empty_diff_returns_empty_list() -> None:
    assert parse_unified_diff("") == []


def test_preamble_text_outside_any_file_is_ignored() -> None:
    diff = """warning: could not find ref
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-x
+y
"""
    files = parse_unified_diff(diff)
    assert len(files) == 1
    assert files[0].changed_lines == {1}
