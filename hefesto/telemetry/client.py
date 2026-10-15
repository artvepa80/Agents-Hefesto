"""Anonymous usage events for PostHog Cloud.

On by default. Nothing is sent until the one-time notice has been shown, and
nothing is sent when the project key or host is empty. The body carries a
random install id and no paths, code, findings, repository names, or IP.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import sys
import threading
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Public write-only project key (PostHog Cloud, US). Empty string disables sends.
POSTHOG_API_KEY = "phc_ofYThaD8rd7ptYXG8PaqNL6hnLBafbXNddwNfqshzyJ7"
POSTHOG_HOST = "https://us.i.posthog.com"

EVENTS = (
    "first_run",
    "analyze",
    "hooks_installed",
    "hook_blocked",
    "upgrade_cta_shown",
)
# Growth: upgrade_cta_shown.source is only one of these. A direct local CLI
# run is "cli" so it is not mislabeled as a hook, CI, or the GitHub Action.
CTA_SOURCES = frozenset({"hook", "ci", "action"})
_EXPLICIT_SOURCES = frozenset({"hook", "ci", "action"})
_OPT_OUT = frozenset({"0", "false", "no", "off"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_UUID_RE_TEXT = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"

NOTICE = (
    "Hefesto collects anonymous usage data by default (a random id; no code, "
    "file paths, findings, repository names, or IP addresses). "
    "Disable: hefesto telemetry disable, HEFESTO_TELEMETRY=0, or DO_NOT_TRACK=1."
)

# Set for the rest of this process after the notice is printed, so the first
# run never sends. A later process starts with this false.
_held = False


def hefesto_dir() -> Path:
    override = os.environ.get("HEFESTO_STATE_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".hefesto"


def telemetry_enabled() -> bool:
    """True unless the user opted out. Ignores the project key."""
    if os.getenv("DO_NOT_TRACK", "").strip().lower() in _TRUTHY:
        return False
    if os.getenv("HEFESTO_TELEMETRY", "").strip().lower() in _OPT_OUT:
        return False
    return not (hefesto_dir() / "telemetry_disabled").is_file()


def disable() -> None:
    """Persist the machine opt-out used by ``hefesto telemetry disable``."""
    directory = hefesto_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "telemetry_disabled").write_text("1\n", encoding="utf-8")


def resolve_source() -> str:
    """Channel for this process: hook, action, ci, or cli (direct invocation)."""
    explicit = os.getenv("HEFESTO_SOURCE", "").strip().lower()
    if explicit in _EXPLICIT_SOURCES:
        return explicit
    if os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true":
        return "action"
    if os.getenv("CI", "").strip().lower() == "true":
        return "ci"
    return "cli"


def in_ci() -> bool:
    """True for ``CI=true`` or ``GITHUB_ACTIONS`` set to a truthy value."""
    if os.getenv("CI", "").strip().lower() == "true":
        return True
    return os.getenv("GITHUB_ACTIONS", "").strip().lower() in _TRUTHY


def resolved_posthog_key() -> str:
    """Env, then ``~/.hefesto/telemetry.json``, then the built-in key.

    A set-but-empty env var or config value wins, and then nothing is sent.
    """
    if "HEFESTO_POSTHOG_KEY" in os.environ:
        return os.environ["HEFESTO_POSTHOG_KEY"].strip()
    configured = _config_string("posthog_api_key")
    if configured is not None:
        return configured
    return POSTHOG_API_KEY


def resolved_posthog_host() -> str:
    """Origin only (scheme + host). Empty when the value is missing or invalid."""
    if "HEFESTO_POSTHOG_HOST" in os.environ:
        raw = os.environ["HEFESTO_POSTHOG_HOST"]
    else:
        configured = _config_string("posthog_host")
        raw = POSTHOG_HOST if configured is None else configured
    return _valid_host(raw)


def build_event(event: str) -> dict[str, Any]:
    """JSON body for one event. Caller-supplied fields are not accepted."""
    if event not in EVENTS:
        raise ValueError(event)
    return {
        "api_key": resolved_posthog_key(),
        "event": event,
        "distinct_id": install_id(),
        "properties": {
            "source": resolve_source(),
            "$geoip_disable": True,
            "$process_person_profile": False,
        },
    }


def prepare_cli(subcommand: str | None) -> None:
    """Hook used by the Click group, which is what the console script runs.

    Prints the notice on the first eligible invocation and sends ``first_run``
    only on a later one. ``hefesto telemetry`` is skipped so ``disable`` does
    not emit an event before the opt-out is stored.
    """
    if not subcommand or subcommand == "telemetry":
        return
    if not _may_emit():
        return
    if not _can_deliver() and not _debug_enabled():
        return
    if _defer_until_noticed():
        return
    if _flag("first_run_sent"):
        return
    _set_flag("first_run_sent", True)
    capture("first_run")


def capture(event: str, **extra: Any) -> None:
    """Send one of the five events. ``extra`` is discarded (no paths or findings)."""
    del extra
    if event not in EVENTS or not _may_emit():
        return
    if event == "upgrade_cta_shown" and resolve_source() not in CTA_SOURCES:
        return
    if not _can_deliver() and not _debug_enabled():
        return
    if _defer_until_noticed():
        return
    body = build_event(event)
    if _debug_enabled():
        _print_debug(body)
        return
    _schedule_send(body)


def sends_this_process() -> bool:
    """True when an event would leave this process (send or debug print).

    False during the notice process, when telemetry is off, or when the key
    or host is empty.
    """
    if not _may_emit():
        return False
    if _held or not _flag("notice_shown"):
        return False
    return _can_deliver() or _debug_enabled()


def persisted_flag(name: str) -> bool:
    return _flag(name)


def persist_flag(name: str) -> None:
    _set_flag(name, True)


def print_notice() -> None:
    print(NOTICE, file=sys.stderr)


def _print_debug(body: Mapping[str, Any]) -> None:
    public = {
        "event": body["event"],
        "distinct_id": body["distinct_id"],
        "properties": body["properties"],
    }
    print(json.dumps(public, separators=(",", ":"), sort_keys=True), file=sys.stderr)


def _defer_until_noticed() -> bool:
    """True when this process must not send. The first call prints the notice."""
    global _held
    if _held:
        return True
    if _flag("notice_shown"):
        return False
    print_notice()
    _set_flag("notice_shown", True)
    _held = True
    return True


def _may_emit() -> bool:
    if _suppressed_by_test_runner():
        return False
    return telemetry_enabled()


def _suppressed_by_test_runner() -> bool:
    if os.environ.get("HEFESTO_TELEMETRY_UNDER_TEST") == "1":
        return False
    return "PYTEST_CURRENT_TEST" in os.environ


def _can_deliver() -> bool:
    return bool(resolved_posthog_key() and resolved_posthog_host())


def _debug_enabled() -> bool:
    return os.getenv("HEFESTO_TELEMETRY_DEBUG", "").strip().lower() in _TRUTHY


def _config_string(key: str) -> str | None:
    path = hefesto_dir() / "telemetry.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(loaded, dict) or key not in loaded:
        return None
    value = loaded[key]
    if value is None:
        return ""
    return str(value).strip()


def _valid_host(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return ""
    if parsed.username or parsed.password:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _read_state() -> dict[str, Any]:
    path = hefesto_dir() / "telemetry_state.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _write_state(state: Mapping[str, Any]) -> None:
    directory = hefesto_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "telemetry_state.json"
    temporary = directory / "telemetry_state.json.tmp"
    temporary.write_text(json.dumps(dict(state), separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, target)


def _flag(name: str) -> bool:
    return _read_state().get(name) is True


def _set_flag(name: str, value: bool) -> None:
    state = _read_state()
    state[name] = value
    try:
        _write_state(state)
    except OSError:
        return


def install_id() -> str:
    """Random UUID stored on disk. Delete ``telemetry_state.json`` to reset it."""
    state = _read_state()
    current = state.get("install_id")
    if isinstance(current, str) and re.fullmatch(_UUID_RE_TEXT, current):
        return current
    new_id = str(uuid.uuid4())
    state["install_id"] = new_id
    try:
        _write_state(state)
    except OSError:
        return new_id
    return new_id


_pending: list[threading.Thread] = []


def _schedule_send(payload: Mapping[str, Any]) -> None:
    body = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
    url = resolved_posthog_host() + "/capture/"

    def _run() -> None:
        try:
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(request, timeout=1.5)
        except Exception:  # noqa: BLE001 — a telemetry failure must not surface
            return

    thread = threading.Thread(target=_run, name="hefesto-telemetry", daemon=True)
    thread.start()
    if os.environ.get("HEFESTO_TELEMETRY_UNDER_TEST") != "1":
        _pending.append(thread)


def _flush_pending() -> None:
    for thread in _pending:
        thread.join(timeout=1.0)


atexit.register(_flush_pending)
