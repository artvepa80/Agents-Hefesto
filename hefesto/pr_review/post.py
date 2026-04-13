"""``hefesto pr-review --post`` convenience mode.

Shells out to ``gh api`` once per finding. **Not idempotent** — two
runs create two comments. Intentional: the idempotent posting pipeline
lives in the deduped workflow template (``hefesto-pr-review-deduped.yml``)
and uses ``gh api`` list → ``jq`` filter → post. Keeping both flows
lets small projects onboard in two lines while production users get
the full dedup-aware pipeline without changing the CLI contract.

Requires: ``gh`` on PATH, authenticated (``gh auth status``), and a
GitHub repository context available from the current directory.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def post_findings(
    *,
    repo: str,
    pr_number: int,
    commit_id: str,
    findings: List[Dict[str, Any]],
    dry_run: bool = False,
) -> Dict[str, int]:
    """Post each finding as an inline review comment via ``gh api``.

    Returns a small counters dict for the CLI to report. Silent
    non-idempotence: repeated calls create duplicate comments. Use the
    deduped workflow template for production runs.
    """
    posted = 0
    failed = 0
    skipped_no_hunk = 0

    for finding in findings:
        if not finding.get("in_hunk", False):
            # Inline comments require a changed line — file-level
            # (strict mode) findings are not postable as inline.
            skipped_no_hunk += 1
            continue

        body = _format_comment_body(finding)
        args = [
            "gh",
            "api",
            "--method",
            "POST",
            f"repos/{repo}/pulls/{pr_number}/comments",
            "-f",
            f"body={body}",
            "-f",
            f"commit_id={commit_id}",
            "-f",
            f"path={finding['file']}",
            "-F",
            f"line={finding['line']}",
            "-f",
            "side=RIGHT",
        ]

        if dry_run:
            logger.info("dry-run: would post %s", args)
            posted += 1
            continue

        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            posted += 1
        else:
            failed += 1
            logger.warning(
                "gh api POST failed for %s:%s (rc=%s): %s",
                finding["file"],
                finding["line"],
                result.returncode,
                result.stderr.strip(),
            )

    return {"posted": posted, "failed": failed, "skipped_no_hunk": skipped_no_hunk}


def _format_comment_body(finding: Dict[str, Any]) -> str:
    """Inline the dedup marker so a future deduped pipeline can find it."""
    dedup = finding.get("dedup_key", "")
    severity = finding.get("severity", "?")
    kind = finding.get("type", "?")
    message = finding.get("message", "")
    suggestion = finding.get("suggestion")

    lines = [
        f"<!-- hefesto-pr-review: dedup_key={dedup} -->",
        f"**[{severity}] {kind}**",
        "",
        message,
    ]
    if suggestion:
        lines.append("")
        lines.append(f"> {suggestion}")

    # Phase 3.1: render enrichment summary when present (Pro path).
    # Pure OSS findings have no "enrichment" key — output is identical
    # to the deterministic-only format.
    enrichment = finding.get("enrichment")
    if isinstance(enrichment, dict) and enrichment.get("status") == "ok":
        summary = enrichment.get("summary")
        if summary:
            lines.append("")
            lines.append(f"**AI insight:** {summary}")

    return "\n".join(lines)


def detect_repo_and_pr(cwd: Optional[str] = None) -> "tuple[Optional[str], Optional[int]]":
    """Try to infer ``owner/repo`` and PR number from ``gh pr view``.

    Returns ``(repo, pr_number)`` or ``(None, None)`` on any failure
    (not in a GitHub repo, no open PR for current branch, ``gh`` not
    on PATH). The CLI uses this only when the user does not pass
    ``--pr`` and ``--repo`` explicitly.
    """
    try:
        result = subprocess.run(
            ["gh", "pr", "view", "--json", "number,baseRepository"],
            capture_output=True,
            text=True,
            check=False,
            cwd=cwd,
        )
        if result.returncode != 0:
            return None, None
        import json as _json

        data = _json.loads(result.stdout)
        pr_number = data.get("number")
        base_repo = data.get("baseRepository") or {}
        owner = base_repo.get("owner", {}).get("login")
        name = base_repo.get("name")
        if owner and name and pr_number is not None:
            return f"{owner}/{name}", int(pr_number)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("detect_repo_and_pr failed: %s", exc)
    return None, None


__all__ = ["post_findings", "detect_repo_and_pr"]
