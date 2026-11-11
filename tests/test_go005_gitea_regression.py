"""The retired GO002 gitea list stays free of GO005.

CI does not fetch gitea. The live check runs only when
``HEFESTO_GITEA_CHECKOUT`` points at a checkout of the pinned sha.
``scripts/go005_gitea_regression.py`` is the command that asserts 0 GO005
on those lines; ``tests/fixtures/go005/gitea_retired_go002_result.txt`` is
the recorded result.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.go005_gitea_regression import KEPT, RESULT, SHA, SITES, check, load_sites

pytest.importorskip("tree_sitter_language_pack")


def test_retired_go002_site_list_has_57_lines_and_omits_the_kept_hit() -> None:
    text = SITES.read_text(encoding="utf-8")
    assert f"sha: {SHA}" in text
    rows = load_sites()
    assert len(rows) == 57
    assert len(set(rows)) == 57
    assert KEPT not in {f"{rel}:{line}" for rel, line in rows}


def test_recorded_gitea_result_has_zero_go005_on_retired_sites() -> None:
    text = RESULT.read_text(encoding="utf-8")
    assert f"sha: {SHA}" in text
    assert "retired_sites: 57" in text
    assert "go005_on_retired_sites: 0" in text
    assert f"kept_hit: {KEPT}" in text
    assert "kept_hit_reported: true" in text
    assert "CI does not fetch gitea" in text


@pytest.mark.skipif(
    not os.environ.get("HEFESTO_GITEA_CHECKOUT"),
    reason="CI does not fetch gitea; see scripts/go005_gitea_regression.py",
)
def test_gitea_checkout_has_zero_go005_on_retired_sites() -> None:
    root = Path(os.environ["HEFESTO_GITEA_CHECKOUT"])
    report = check(root)
    assert report["go005_on_retired_sites"] == []
    assert report["kept_hit_reported"] is True
    assert report["missing_files"] == []
    assert report["retired_sites"] == 57
