# 2026-10-15: hefesto init and price copy (handoff)

Public repo only. Stacked on the PostHog telemetry branch. No tag, no release, no merge (Arturo merges, and not the same day).

## What landed

- `hefesto init` runs the same installer as `hefesto install-hooks` and then prints `PRO $8/mo. OMEGA $19/mo.` plus `https://hefestoai.narapallc.com/?utm_source=hefesto-cli&utm_medium=cli&utm_campaign=growth_q4_2026&utm_content=init#pricing`.
- Running it again is safe: hooks that already match stay, exit 0, and the link is printed again.
- The first eligible `init` also prints the telemetry notice and does not send in that process (same rule as the other commands).
- After a hook blocks (`analyze` exit 1, `--fail-on` set, at least one file, `source=hook`), stderr shows `PRO $8/mo: <url with utm_content=hook_blocked>` once. Not when `CI=true` or `GITHUB_ACTIONS` is `1`/`true`/`yes`/`on`.
- `upgrade_cta_shown` is emitted once, and only when `source` is `hook`, `ci`, or `action`. The notice process prints the line and leaves the event for a later block.
- Current user-facing prices are PRO $8/mo and OMEGA $19/mo. No trial, no discount, no "no credit card required". Historical changelog entries and worklogs are unchanged. Competitor prices in the README comparison table stay.

## Not done

- No merge. No tag. No release.
