"""Plans link for ``hefesto init`` and the one-time hook-block line.

Prices in this text are PRO $8/mo and OMEGA $19/mo. No trial and no discount.
"""

from __future__ import annotations

import click

from hefesto.telemetry.client import (
    CTA_SOURCES,
    capture,
    in_ci,
    persist_flag,
    persisted_flag,
    resolve_source,
    sends_this_process,
)

UTM_SOURCE = "hefesto-cli"
UTM_MEDIUM = "cli"
UTM_CAMPAIGN = "growth_q4_2026"
_LANDING = "https://hefestoai.narapallc.com/"

_LINE_FLAG = "upgrade_cta_line_shown"
_EVENT_FLAG = "upgrade_cta_event_sent"


def pricing_url(utm_content: str) -> str:
    """Landing pricing URL with the growth UTM set. ``utm_content`` names the surface."""
    query = (
        f"utm_source={UTM_SOURCE}&utm_medium={UTM_MEDIUM}"
        f"&utm_campaign={UTM_CAMPAIGN}&utm_content={utm_content}"
    )
    return f"{_LANDING}?{query}#pricing"


INIT_PRICING_URL = pricing_url("init")
HOOK_BLOCKED_PRICING_URL = pricing_url("hook_blocked")
CTA_LINE = f"PRO $8/mo: {HOOK_BLOCKED_PRICING_URL}"


def show_upgrade_cta() -> None:
    """Print ``PRO $8/mo`` once after a hook block, and emit ``upgrade_cta_shown``.

    Not printed when ``CI=true`` or ``GITHUB_ACTIONS`` is truthy, and not
    printed for a direct local invocation (``source=cli``). The event is
    sent only when ``source`` is ``hook``, ``ci``, or ``action`` and this
    process is allowed to send. The notice process prints the line and
    leaves the event for a later block.
    """
    if in_ci() or resolve_source() not in CTA_SOURCES:
        return
    if not persisted_flag(_LINE_FLAG):
        click.echo(CTA_LINE, err=True)
        persist_flag(_LINE_FLAG)
    if persisted_flag(_EVENT_FLAG) or not sends_this_process():
        return
    capture("upgrade_cta_shown")
    persist_flag(_EVENT_FLAG)
