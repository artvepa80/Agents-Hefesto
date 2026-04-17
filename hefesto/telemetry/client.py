from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path.home() / ".hefesto" / "telemetry.jsonl"
DEFAULT_MAX_BYTES = 1048576  # 1MB
DEFAULT_MAX_FILES = 3
SCHEMA_VERSION = 1
TELEMETRY_ENDPOINT = "https://hefestoai.narapallc.com/api/telemetry"


def _env_truthy(v: Optional[str]) -> bool:
    if not v:
        return False
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_mkdir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sanitize_args_for_hash(argv: List[str]) -> str:
    """
    Remove/normalize obvious sensitive bits (paths, tokens, emails).
    We only use this for a hash, never store raw.
    """
    redacted: List[str] = []
    for a in argv:
        x = a.strip()

        # crude redactions
        if "/" in x or "\\" in x:
            redacted.append("<path>")
            continue
        if "@" in x and "." in x:
            redacted.append("<email>")
            continue
        if "key" in x.lower() or "token" in x.lower() or "secret" in x.lower():
            redacted.append("<secret>")
            continue

        redacted.append(x)
    return " ".join(redacted)


@dataclass
class TelemetryEvent:
    ts: str
    command: str
    version: str
    exit_code: int
    duration_ms: int
    schema_version: int = SCHEMA_VERSION
    args_hash: Optional[str] = None


class TelemetryClient:
    def __init__(self) -> None:
        self._start_ts: Optional[float] = None
        self._command: Optional[str] = None
        self._version: Optional[str] = None
        self._args_hash: Optional[str] = None
        self._finalized = False

        self._refresh_config()

        if self.enabled:
            pass

    def _safe_int(self, v: Any, default: int) -> int:
        try:
            return int(v)
        except Exception:
            return default

    def _clamp(self, v: int, min_v: int, max_v: int) -> int:
        return max(min_v, min(v, max_v))

    def _refresh_config(self) -> None:
        self.enabled = _env_truthy(os.getenv("HEFESTO_TELEMETRY"))
        self.path = Path(os.getenv("HEFESTO_TELEMETRY_PATH", str(DEFAULT_PATH)))

        # Clamp settings to safe ranges
        raw_bytes = self._safe_int(os.getenv("HEFESTO_TELEMETRY_MAX_BYTES"), DEFAULT_MAX_BYTES)
        self.max_bytes = self._clamp(raw_bytes, 1024, 50_000_000)  # 1KB - 50MB

        raw_files = self._safe_int(os.getenv("HEFESTO_TELEMETRY_MAX_FILES"), DEFAULT_MAX_FILES)
        self.max_files = self._clamp(raw_files, 0, 20)  # 0 - 20 files

    def _rotated_path(self, i: int) -> Path:
        # Stable: "/x/telemetry.jsonl" -> "/x/telemetry.jsonl.1"
        return Path(str(self.path) + f".{i}")

    def start(self, *, command: str, version: str, argv: Optional[List[str]] = None) -> None:
        # Refresh config in case env changed (e.g. testing)
        self._refresh_config()

        # Reset state for reuse (prevents cross-command carryover)
        self._start_ts = None
        self._command = None
        self._version = None
        self._args_hash = None
        self._finalized = False

        if not self.enabled:
            return
        self._start_ts = time.time()
        self._command = command
        self._version = version
        if argv is not None:
            self._args_hash = _sha256(_sanitize_args_for_hash(argv))

    def end(self, *, exit_code: int) -> None:
        if not self.enabled or self._finalized:
            return
        self._finalized = True
        if self._start_ts is None or self._command is None or self._version is None:
            return

        dur_ms = int((time.time() - self._start_ts) * 1000)
        ev = TelemetryEvent(
            ts=_utc_iso(),
            command=self._command,
            version=self._version,
            exit_code=int(exit_code),
            duration_ms=dur_ms,
            schema_version=SCHEMA_VERSION,
            args_hash=self._args_hash,
        )
        self._write(ev)

    def _atomic_replace(self, src: Path, dst: Path) -> None:
        try:
            os.replace(str(src), str(dst))
        except Exception:
            # swallow
            pass

    def _rotate_if_needed(self) -> None:
        try:
            if not self.path.exists():
                return

            size = self.path.stat().st_size
            if size < self.max_bytes:
                return

            max_files = self._safe_int(self.max_files, DEFAULT_MAX_FILES)
            if max_files <= 0:
                return

            # Spec: delete <path>.<max_files> if exists (avoid rename collisions)
            # We actively delete the oldest one to make space
            last = self._rotated_path(max_files)
            if last.exists():
                try:
                    last.unlink()
                except Exception:
                    pass

            # Rotate: file.{n} -> file.{n+1}
            # Start from max_files-1 down to 1
            for i in range(max_files - 1, 0, -1):
                s_curr = self._rotated_path(i)
                s_next = self._rotated_path(i + 1)
                if s_curr.exists():
                    self._atomic_replace(s_curr, s_next)

            # Rotate: file -> file.1
            s_first = self._rotated_path(1)
            self._atomic_replace(self.path, s_first)

        except Exception:
            # Swallow rotation errors to not break CLI
            pass

    def _write(self, ev: TelemetryEvent) -> None:
        try:
            _safe_mkdir(self.path)
            self._rotate_if_needed()

            line = json.dumps(ev.__dict__, separators=(",", ":"), ensure_ascii=False)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            # MUST NOT break CLI
            return

    def get_status(self) -> Dict[str, Any]:
        """Return telemetry status for diagnostics."""
        self._refresh_config()
        size = 0
        if self.path.exists():
            try:
                size = self.path.stat().st_size
            except Exception:
                pass

        return {
            "enabled": self.enabled,
            "path": str(self.path),
            "size_bytes": size,
            "max_bytes": self.max_bytes,
            "max_files": self.max_files,
            "schema_version": SCHEMA_VERSION,
        }

    def clear_data(self) -> None:
        """Purge telemetry data (current + rotated)."""
        self._refresh_config()
        try:
            if self.path.exists():
                self.path.unlink()

            # Use clamped max_files to avoid trying to delete thousands of files if env is bad
            max_files = self.max_files
            for i in range(1, max_files + 1):
                f = self._rotated_path(i)
                if f.exists():
                    try:
                        f.unlink()
                    except Exception:
                        pass
        except Exception:
            pass


_LATEST_VERSION_CACHE = Path.home() / ".hefesto" / ".latest_version"
_SESSION_ID_FILE = Path.home() / ".hefesto" / ".session_id"
_CACHE_TTL_SECONDS = 86400  # 24h


def _get_session_id() -> str:
    """Return a stable anonymous session ID (UUID4), generated once per machine."""
    try:
        if _SESSION_ID_FILE.exists():
            sid = _SESSION_ID_FILE.read_text(encoding="utf-8").strip()
            if sid:
                return sid
        sid = uuid.uuid4().hex[:12]
        _SESSION_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SESSION_ID_FILE.write_text(sid, encoding="utf-8")
        return sid
    except Exception:
        return ""


def _get_environment_flags() -> list:
    """Detect execution environment. All matching flags appended (not first-match-wins).

    A GitHub Actions run produces ['ci', 'github_actions'].
    A Docker container in CI produces ['ci', 'docker'].
    Default: ['user'] if none match.
    """
    try:
        flags = []
        if os.getenv("CI", "").lower() == "true":
            flags.append("ci")
        if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
            flags.append("github_actions")
        if os.getenv("GITLAB_CI", "").lower() == "true":
            flags.append("gitlab_ci")
        if os.getenv("JENKINS_URL"):
            flags.append("jenkins")
        if os.getenv("CIRCLECI", "").lower() == "true":
            flags.append("circleci")
        if os.path.exists("/.dockerenv"):
            flags.append("docker")
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            flags.append("kubernetes")
        return flags or ["user"]
    except Exception:
        return ["user"]


def _get_install_source() -> str:
    """Detect if installed from PyPI or as editable (dev) install."""
    try:
        import hefesto

        path = os.path.dirname(hefesto.__file__)
        if "site-packages" not in path:
            return "editable"
        return "pypi"
    except Exception:
        return "unknown"


def _ping_remote(payload: dict) -> None:
    """Anonymous ping. Caches ``latest_version`` from server response for upgrade notices."""
    if os.getenv("HEFESTO_TELEMETRY", "").lower() in ("0", "false", "no", "off"):
        return

    # First-run notice (once per machine)
    notice_file = Path.home() / ".hefesto" / ".telemetry_noticed"
    if not notice_file.exists():
        try:
            notice_file.parent.mkdir(parents=True, exist_ok=True)
            notice_file.touch()
            import sys

            print(
                "\u2139\ufe0f  Anonymous telemetry enabled. No code or paths sent."
                " Disable: HEFESTO_TELEMETRY=0",
                file=sys.stderr,
            )
        except Exception:
            pass

    sid = _get_session_id()
    if sid:
        payload["sid"] = sid
    payload["env"] = _get_environment_flags()
    payload["src"] = _get_install_source()

    try:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            TELEMETRY_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=2)
        body = resp.read().decode("utf-8", errors="ignore")
        if body:
            resp_data = json.loads(body)
            latest = resp_data.get("latest_version")
            if latest:
                _cache_latest_version(latest)
    except Exception:
        pass


def _cache_latest_version(version: str) -> None:
    try:
        _LATEST_VERSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _LATEST_VERSION_CACHE.write_text(
            json.dumps({"version": version, "ts": time.time()}),
            encoding="utf-8",
        )
    except Exception:
        pass


def get_upgrade_notice(current_version: str) -> Optional[str]:
    """Return an upgrade notice string if a newer version is available, else None.

    Reads from the local cache populated by ``_ping_remote``. Returns None
    if cache is missing, stale (>24h), or current version is up to date.
    Never raises.
    """
    try:
        if not _LATEST_VERSION_CACHE.exists():
            return None
        raw = json.loads(_LATEST_VERSION_CACHE.read_text(encoding="utf-8"))
        cached_ts = raw.get("ts", 0)
        if time.time() - cached_ts > _CACHE_TTL_SECONDS:
            return None
        latest = raw.get("version", "")
        if not latest or not _is_newer(latest, current_version):
            return None
        return (
            f"\n\u26a0\ufe0f  Hefesto {latest} available (you have {current_version})."
            f" Upgrade: pip install --upgrade hefesto-ai"
        )
    except Exception:
        return None


def _is_newer(latest: str, current: str) -> bool:
    """Compare semver-style version strings. Returns True if latest > current."""
    try:
        l_parts = [int(x) for x in latest.split(".")]
        c_parts = [int(x) for x in current.split(".")]
        return l_parts > c_parts
    except (ValueError, AttributeError):
        return False
