import os
from pathlib import Path

from hefesto.telemetry.client import TelemetryClient


def test_telemetry_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("HEFESTO_TELEMETRY", raising=False)
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(tmp_path / "t.jsonl"))
    c = TelemetryClient()
    c.start(command="analyze", version="0.0.0", argv=["hefesto", "analyze", "."])
    c.end(exit_code=0)
    assert not Path(os.environ["HEFESTO_TELEMETRY_PATH"]).exists()


def test_telemetry_opt_in_writes_jsonl(tmp_path, monkeypatch):
    p = tmp_path / "t.jsonl"
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(p))

    c = TelemetryClient()
    c.start(
        command="drift",
        version="1.2.3",
        argv=["hefesto", "drift", "template.yml", "--region", "us-east-1"],
    )
    c.end(exit_code=2)

    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert '"command":"drift"' in lines[0]
    assert '"version":"1.2.3"' in lines[0]
    assert '"exit_code":2' in lines[0]
    assert '"duration_ms":' in lines[0]
    assert '"schema_version":1' in lines[0]


def test_telemetry_cli_success_exit_code_0(tmp_path, monkeypatch):
    import sys

    from hefesto.cli.main import main

    p = tmp_path / "t.jsonl"
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(p))

    # Mock sys.argv
    monkeypatch.setattr(sys, "argv", ["hefesto", "--version"])

    try:
        main()
    except SystemExit as e:
        assert e.code == 0

    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert '"exit_code":0' in lines[-1]


def test_telemetry_rotation(tmp_path, monkeypatch):
    p = tmp_path / "t.jsonl"
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(p))
    # Minimum is 1024 bytes
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_BYTES", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_FILES", "2")

    c = TelemetryClient()

    # We need the JSON line to be > 1024 bytes.
    # argv is hashed, so it doesn't add size.
    # command is stored as-is.
    huge_cmd = "cmd_" + "x" * 1200

    # Write event 1 -> t.jsonl
    c.start(command=huge_cmd, version="1", argv=[])
    c.end(exit_code=0)
    assert p.exists()

    # Write event 2 -> triggers rotation
    c.start(command=huge_cmd, version="1", argv=[])
    c.end(exit_code=0)

    # Check rotation
    assert p.exists()
    p1 = Path(f"{p}.1")
    assert p1.exists()

    content = p.read_text(encoding="utf-8")
    assert huge_cmd in content

    content_1 = p1.read_text(encoding="utf-8")
    assert huge_cmd in content_1

    # Write event 3 -> triggers rotation again
    c.start(command=huge_cmd, version="1", argv=[])
    c.end(exit_code=0)

    p2 = Path(f"{p}.2")
    assert p.exists()
    assert p1.exists()
    assert p2.exists()

    # Write event 4 -> max files 2
    c.start(command=huge_cmd, version="1", argv=[])
    c.end(exit_code=0)

    assert p.exists()
    assert p1.exists()
    assert p2.exists()
    # .3 should NOT exist
    assert not Path(f"{p}.3").exists()


def test_telemetry_status_command(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from hefesto.cli.main import cli

    p = tmp_path / "t.jsonl"
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(p))

    r = CliRunner()
    res = r.invoke(cli, ["telemetry", "status"])
    assert res.exit_code == 0
    assert "Telemetry Status:" in res.output
    assert "Enabled:   True" in res.output
    assert "Max Bytes:" in res.output


def test_telemetry_clear_command(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from hefesto.cli.main import cli

    p = tmp_path / "t.jsonl"
    p.write_text("some data")

    # Create rotated file manually to test cleanup
    p1 = Path(f"{p}.1")
    p1.write_text("backup data")

    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(p))
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_FILES", "2")

    r = CliRunner()
    res = r.invoke(cli, ["telemetry", "clear"], input="y\n")
    assert res.exit_code == 0
    assert not p.exists()
    assert not p1.exists()


def test_invalid_env_vars_are_sanitized(tmp_path, monkeypatch):
    p = tmp_path / "t.jsonl"
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(p))
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_BYTES", "invalid")
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_FILES", "-5")

    c = TelemetryClient()
    # Should fallback to defaults/clamped
    # Default bytes = 1MB (1048576)
    assert c.max_bytes == 1048576
    # Clamped files = 0 (min)
    assert c.max_files == 0


def test_clamps_large_values(tmp_path, monkeypatch):
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_BYTES", "999999999999")
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_FILES", "999")

    c = TelemetryClient()
    assert c.max_bytes == 50_000_000
    assert c.max_files == 20


def test_max_files_zero_disables_rotation(tmp_path, monkeypatch):
    p = tmp_path / "t.jsonl"
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(p))
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_BYTES", "1")  # Force rotation
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_FILES", "0")  # Disable rotation

    c = TelemetryClient()

    # Event 1
    c.start(command="cmd1", version="1", argv=[])
    c.end(exit_code=0)
    assert p.exists()

    # Event 2 (would trigger rotation if allowed)
    c.start(command="cmd2", version="1", argv=[])
    c.end(exit_code=0)

    # Check no rotation happened
    assert p.exists()
    assert not Path(f"{p}.1").exists()

    # Content should just append
    content = p.read_text(encoding="utf-8")
    assert "cmd1" in content
    assert "cmd2" in content


def test_rotation_overwrites_existing_destination(tmp_path, monkeypatch):
    """
    If destination rotated file already exists, rotation must not crash and must overwrite it.
    This specifically validates using os.replace (atomic overwrite) instead of Path.rename.
    """
    from pathlib import Path

    from hefesto.telemetry.client import TelemetryClient

    p = tmp_path / "t.jsonl"
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(p))
    monkeypatch.setenv(
        "HEFESTO_TELEMETRY_MAX_BYTES", "1"
    )  # clamped to 1024 -> forces rotation with huge command
    monkeypatch.setenv("HEFESTO_TELEMETRY_MAX_FILES", "2")

    # Pre-create destination .2 to simulate "already exists" collision.
    p2 = Path(f"{p}.2")
    p2.write_text("PREEXISTING_DESTINATION_SHOULD_BE_OVERWRITTEN\n", encoding="utf-8")
    assert p2.exists()

    c = TelemetryClient()
    huge_cmd = "cmd_" + "x" * 1200

    # Event 1 -> creates p
    c.start(command=huge_cmd, version="1", argv=[])
    c.end(exit_code=0)
    assert p.exists()

    # Event 2 -> rotates p -> p.1 (p.2 already exists but shouldn't matter yet)
    c.start(command=huge_cmd, version="1", argv=[])
    c.end(exit_code=0)
    assert Path(f"{p}.1").exists()
    assert p.exists()

    # Event 3 -> rotates p.1 -> p.2 (THIS is the collision case), then p -> p.1
    c.start(command=huge_cmd, version="1", argv=[])
    c.end(exit_code=0)

    # Must still exist, and must NOT keep the old preexisting marker content.
    assert p2.exists()
    content_2 = p2.read_text(encoding="utf-8")
    assert "PREEXISTING_DESTINATION_SHOULD_BE_OVERWRITTEN" not in content_2
    assert huge_cmd in content_2
