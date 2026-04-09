#!/usr/bin/env python3
"""
traffic_report.py — Fetch and format GitHub repository traffic data.

Usage:
    python scripts/traffic_report.py --owner OWNER --repo REPO --token TOKEN

Outputs a Markdown report to stdout and exits 0.
Requires a GitHub token with at least `repo` scope (classic PAT) or a
Fine-Grained PAT with "Administration" (read) permission on the target repo.
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any


def _api_get(path: str, token: str) -> Any:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hefesto-traffic-report/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"[ERROR] GitHub API {path} → HTTP {exc.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"[ERROR] GitHub API {path} → network error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


def _fmt_number(n: int) -> str:
    return f"{n:,}"


def build_report(owner: str, repo: str, token: str) -> str:
    repo_path = f"/repos/{owner}/{repo}"
    views = _api_get(f"{repo_path}/traffic/views", token)
    clones = _api_get(f"{repo_path}/traffic/clones", token)
    referrers = _api_get(f"{repo_path}/traffic/popular/referrers", token)
    paths = _api_get(f"{repo_path}/traffic/popular/paths", token)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    full_repo = f"{owner}/{repo}"

    lines = [
        f"## 📊 Traffic Report — `{full_repo}`",
        "",
        f"> Generated: {now}  ",
        "> Data covers the last 14 days (GitHub API limit).",
        "",
        "---",
        "",
        "### 👁️ Page Views",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total views (14 days) | {_fmt_number(views.get('count', 0))} |",
        f"| Unique visitors (14 days) | {_fmt_number(views.get('uniques', 0))} |",
        "",
    ]

    # Daily views breakdown
    daily_views: list = views.get("views", [])
    if daily_views:
        lines += [
            "#### Daily Views",
            "| Date | Views | Unique Visitors |",
            "|------|-------|-----------------|",
        ]
        for day in daily_views:
            raw_ts = day.get("timestamp", "")
            ts = raw_ts[:10] if len(raw_ts) >= 10 else (raw_ts or "—")
            lines.append(
                f"| {ts} | {_fmt_number(day.get('count', 0))} "
                f"| {_fmt_number(day.get('uniques', 0))} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "### 📥 Git Clones",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total clones (14 days) | {_fmt_number(clones.get('count', 0))} |",
        f"| Unique cloners (14 days) | {_fmt_number(clones.get('uniques', 0))} |",
        "",
    ]

    # Daily clones breakdown
    daily_clones: list = clones.get("clones", [])
    if daily_clones:
        lines += [
            "#### Daily Clones",
            "| Date | Clones | Unique Cloners |",
            "|------|--------|----------------|",
        ]
        for day in daily_clones:
            raw_ts = day.get("timestamp", "")
            ts = raw_ts[:10] if len(raw_ts) >= 10 else (raw_ts or "—")
            lines.append(
                f"| {ts} | {_fmt_number(day.get('count', 0))} "
                f"| {_fmt_number(day.get('uniques', 0))} |"
            )
        lines.append("")

    # Top referrers
    lines += [
        "---",
        "",
        "### 🔗 Top Referrers",
    ]
    if referrers:
        lines += [
            "| Referrer | Views | Unique Visitors |",
            "|----------|-------|-----------------|",
        ]
        for ref in referrers:
            lines.append(
                f"| {ref.get('referrer', '—')} "
                f"| {_fmt_number(ref.get('count', 0))} "
                f"| {_fmt_number(ref.get('uniques', 0))} |"
            )
    else:
        lines.append("_No referrer data available._")
    lines.append("")

    # Popular paths
    lines += [
        "---",
        "",
        "### 📄 Most Visited Pages",
    ]
    if paths:
        lines += [
            "| Path | Views | Unique Visitors |",
            "|------|-------|-----------------|",
        ]
        for p in paths:
            lines.append(
                f"| `{p.get('path', '—')}` "
                f"| {_fmt_number(p.get('count', 0))} "
                f"| {_fmt_number(p.get('uniques', 0))} |"
            )
    else:
        lines.append("_No page data available._")
    lines.append("")
    lines.append("---")
    lines.append(
        "_This report was generated automatically by "
        "[Hefesto Traffic Report](../../blob/main/scripts/traffic_report.py)._"
    )

    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub repo traffic and print a Markdown report."
    )
    parser.add_argument("--owner", required=True, help="GitHub owner/org")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--token", required=True, help="GitHub token (repo scope)")
    parser.add_argument(
        "--output",
        default="-",
        help="Output file path (default: stdout)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = build_report(args.owner, args.repo, args.token)

    if args.output == "-":
        print(report)
    else:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print(f"Report written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
