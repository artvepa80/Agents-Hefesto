"""The retired GO002 gitea list stays free of GO005.

CI does not fetch gitea. The live check runs only when
``HEFESTO_GITEA_CHECKOUT`` points at a checkout of the pinned sha.
``scripts/go005_gitea_regression.py`` is the command that asserts 0 GO005
on those lines; ``tests/fixtures/go005/gitea_retired_go002_result.txt`` is
the recorded result.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.go005_gitea_regression import (
    KEPT,
    RESULT,
    SHA,
    SITES,
    CheckoutPinError,
    check,
    load_sites,
    main,
    require_pin,
)

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
    assert report["sha"] == SHA
    assert report["go005_on_retired_sites"] == []
    assert report["kept_hit_reported"] is True
    assert report["missing_files"] == []
    assert report["retired_sites"] == 57


def _commit_other_sha(root: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Dev",
        "GIT_AUTHOR_EMAIL": "dev@example.com",
        "GIT_COMMITTER_NAME": "Dev",
        "GIT_COMMITTER_EMAIL": "dev@example.com",
    }
    subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
    (root / "note.txt").write_text("other\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "note.txt"], check=True, env=env)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "other"], check=True, env=env)


def test_script_rejects_a_checkout_that_is_not_the_pinned_commit(tmp_path: Path) -> None:
    _commit_other_sha(tmp_path)
    with pytest.raises(CheckoutPinError, match="is not the pinned commit"):
        require_pin(tmp_path)
    before = RESULT.read_text(encoding="utf-8")
    assert main([str(tmp_path), "--write-result"]) == 1
    assert RESULT.read_text(encoding="utf-8") == before
