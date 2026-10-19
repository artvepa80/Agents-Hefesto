"""One-line PRO/OMEGA notices and their pricing links.

Prices in this text are PRO $8/mo and OMEGA $19/mo. No trial and no discount.
Each notice is one stderr line, after the command result, at most once every
7 days across all types, and at most 3 times per type. State lives in
``~/.hefesto/upsell.json``. A missing file starts empty. A read or parse
failure shows nothing and leaves the file untouched.

A suppressed notice logs ``upsell suppressed: <reason> (cta=<type>)`` on the
``hefesto.cli.growth`` logger at DEBUG. The CLI configures no log handler, so
nothing is printed unless the caller enables DEBUG logging.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

import click

from hefesto.telemetry.client import (
    capture,
    ci_vendor_detected,
    hefesto_dir,
    in_ci,
    resolve_source,
    sends_this_process,
    telemetry_enabled,
)

_TRUTHY = frozenset({"1", "true", "yes", "on"})

_log = logging.getLogger(__name__)

UTM_SOURCE = "hefesto-cli"
UTM_MEDIUM = "cli"
UTM_CAMPAIGN = "growth_q4_2026"
_LANDING = "https://hefestoai.narapallc.com/"

_WEEK_SECONDS = 7 * 24 * 60 * 60
_MAX_PER_TYPE = 3
_STATE_NAME = "upsell.json"

# swarm/cli.py (PRO package): argparse description
# "HefestoAI Swarm — security analysis pipeline", help text
# "Run swarm analysis on a target repo", and cmd_run returns 1 when
# result["verdict"] == "BLOCK".
SWARM_FACT = (
    "hefesto-swarm is HefestoAI's security analysis pipeline: "
    "it runs on a target repo and can return BLOCK."
)


def pricing_url(utm_content: str) -> str:
    """Landing pricing URL. ``utm_content`` is the notice type."""
    query = (
        f"utm_source={UTM_SOURCE}&utm_medium={UTM_MEDIUM}"
        f"&utm_campaign={UTM_CAMPAIGN}&utm_content={utm_content}"
    )
    return f"{_LANDING}?{query}#pricing"


INIT_PRICING_URL = pricing_url("init")
HOOK_BLOCKED_PRICING_URL = pricing_url("hook_blocked")
INIT_LINE = f"Plans: PRO $8/mo · OMEGA $19/mo. {INIT_PRICING_URL}"
HOOK_BLOCKED_LINE = f"PRO $8/mo: {HOOK_BLOCKED_PRICING_URL}"
# Kept so older imports still name the hook line.
CTA_LINE = HOOK_BLOCKED_LINE


def gated_line(feature: str, tier: str, kind: str) -> str:
    """``<Feature> is part of HefestoAI PRO ($8/mo). See plans: <link>``."""
    price = "PRO ($8/mo)" if tier == "PRO" else "OMEGA ($19/mo)"
    return f"{feature} is part of HefestoAI {price}. See plans: {pricing_url(kind)}"


GATED_SERVE_LINE = gated_line("The API server", "PRO", "gated_serve")
GATED_ENRICH_LINE = gated_line("Enrichment", "PRO", "gated_enrich")
GATED_SCOPE_LINE = gated_line("Scope gating", "PRO", "gated_scope")
# ``hefesto info`` prints only this line. It names the real gates so it does
# not repeat the multi-line PRO message used by serve and status.
GATED_INFO_LINE = (
    "PRO ($8/mo) adds the API server, enrichment, and scope gating. "
    f"OMEGA ($19/mo) adds IRIS. See plans: {pricing_url('gated_info')}"
)
GATED_IRIS_LINE = gated_line("IRIS monitoring", "OMEGA", "gated_iris")


def milestone_line(count: int) -> str:
    """Successful-analysis milestone. The swarm sentence stays within 280 characters."""
    return (
        f"{count} successful analyses. {SWARM_FACT} "
        f"PRO $8/mo. See plans: {pricing_url('analyze_milestone')}"
    )


def stdout_is_tty() -> bool:
    try:
        return bool(sys.stdout.isatty())
    except Exception:  # noqa: BLE001 — a tty check must not surface
        return False


def _no_upsell_env() -> bool:
    return os.getenv("HEFESTO_NO_UPSELL", "").strip().lower() in _TRUTHY


# Checked in order; the first match is the logged reason. Each entry looks
# its function up at call time, so tests can patch ``stdout_is_tty``.
_ENV_SUPPRESSIONS: tuple[tuple[str, Callable[[], bool]], ...] = (
    ("ci", lambda: in_ci() or ci_vendor_detected()),
    ("no_tty", lambda: not stdout_is_tty()),
    ("telemetry_off", lambda: not telemetry_enabled()),
    ("opt_out", _no_upsell_env),
)


def environment_suppression(*, quiet: bool, machine: bool) -> str | None:
    """Why the environment hides notices, or ``None`` when it allows them.

    Reasons: ``quiet``, ``machine_output``, ``ci``, ``no_tty``,
    ``telemetry_off``, ``opt_out`` (``HEFESTO_NO_UPSELL``).
    """
    if quiet:
        return "quiet"
    if machine:
        return "machine_output"
    for reason, applies in _ENV_SUPPRESSIONS:
        if applies():
            return reason
    return None


def notices_allowed(*, quiet: bool, machine: bool) -> bool:
    """False in CI, without a TTY, for machine output, or when opted out."""
    return environment_suppression(quiet=quiet, machine=machine) is None


def _suppressed(reason: str, kind: str) -> bool:
    _log.debug("upsell suppressed: %s (cta=%s)", reason, kind)
    return False


def _state_path() -> Path:
    return hefesto_dir() / _STATE_NAME


def load_upsell_state() -> dict[str, Any] | None:
    """Empty state when the file is missing. ``None`` when it cannot be read."""
    path = _state_path()
    if not path.exists():
        return {"last_shown_at": None, "counts": {}, "successful_analyses": 0}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    last = loaded.get("last_shown_at")
    if last is not None and (isinstance(last, bool) or not isinstance(last, (int, float))):
        return None
    counts = loaded.get("counts", {})
    if not isinstance(counts, dict):
        return None
    clean: dict[str, int] = {}
    for key, value in counts.items():
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, int):
            return None
        if value < 0:
            return None
        clean[key] = value
    total = loaded.get("successful_analyses", 0)
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        return None
    return {"last_shown_at": last, "counts": clean, "successful_analyses": total}


def _save_upsell_state(state: dict[str, Any]) -> bool:
    try:
        directory = hefesto_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = _state_path()
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        return False
    return True


def _week_blocked(state: dict[str, Any], now: float) -> bool:
    last = state.get("last_shown_at")
    if last is None:
        return False
    return (now - float(last)) < _WEEK_SECONDS


def _type_blocked(state: dict[str, Any], kind: str) -> bool:
    return int(state["counts"].get(kind, 0)) >= _MAX_PER_TYPE


def is_analyze_milestone(count: int) -> bool:
    """25 successful analyses, then every 100 after that (125, 225, ...)."""
    if count == 25:
        return True
    return count > 25 and (count - 25) % 100 == 0


def show_notice(kind: str, line: str, *, quiet: bool = False, machine: bool = False) -> bool:
    """Print one notice and emit ``upgrade_cta_shown`` when telemetry can send."""
    if "\n" in line:
        return _suppressed("multiline", kind)
    reason = environment_suppression(quiet=quiet, machine=machine)
    if reason is not None:
        return _suppressed(reason, kind)
    state = load_upsell_state()
    if state is None:
        return _suppressed("state_corrupt", kind)
    if _type_blocked(state, kind):
        return _suppressed("max_per_type", kind)
    if _week_blocked(state, time.time()):
        return _suppressed("weekly_window", kind)
    state["counts"][kind] = int(state["counts"].get(kind, 0)) + 1
    state["last_shown_at"] = time.time()
    if not _save_upsell_state(state):
        return _suppressed("state_write_failed", kind)
    click.echo(line, err=True)
    if sends_this_process() and resolve_source() in {"hook", "cli"}:
        capture("upgrade_cta_shown", cta=kind)
    return True


def note_finished_analysis() -> int | None:
    """Count one finished analyze. ``None`` when the state file cannot be used."""
    state = load_upsell_state()
    if state is None:
        return None
    state["successful_analyses"] = int(state["successful_analyses"]) + 1
    count = int(state["successful_analyses"])
    if not _save_upsell_state(state):
        return None
    return count


def show_milestone(count: int | None, *, quiet: bool, machine: bool) -> bool:
    if count is None or not is_analyze_milestone(count):
        return False
    return show_notice("analyze_milestone", milestone_line(count), quiet=quiet, machine=machine)


def show_upgrade_cta(*, quiet: bool = False, machine: bool = False) -> bool:
    """Hook-block notice. Same weekly cap as the other notices."""
    return show_notice("hook_blocked", HOOK_BLOCKED_LINE, quiet=quiet, machine=machine)
