"""PRO/OMEGA-only CLI stubs point at the current offer, not retired links."""

import pytest
from click.testing import CliRunner

from hefesto.cli.main import PRICING_URL, PRO_REQUIRED_MESSAGE, cli


def test_pricing_url_is_landing_pricing_section():
    assert PRICING_URL == "https://hefestoai.narapallc.com/#pricing"


def test_message_names_current_prices_and_url():
    assert "$8/month" in PRO_REQUIRED_MESSAGE
    assert "$19/month" in PRO_REQUIRED_MESSAGE
    assert PRICING_URL in PRO_REQUIRED_MESSAGE
    assert "buy.stripe.com" not in PRO_REQUIRED_MESSAGE


def test_info_prints_pricing_url():
    result = CliRunner().invoke(cli, ["info"])
    assert result.exit_code == 1
    assert PRICING_URL in result.output
    assert "$8/month" in result.output


def test_message_points_licensed_users_at_env_var():
    assert "HEFESTO_LICENSE_KEY" in PRO_REQUIRED_MESSAGE
    assert "private distribution" not in PRO_REQUIRED_MESSAGE


# activate/deactivate/status: licensed users activate with HEFESTO_LICENSE_KEY.
# Before 4.14.2 `activate` printed the purchase message and exited 1 even with
# Pro installed, so the license email told paying customers to run a command
# that always failed.
KEY = "HFST-1234-5678-9ABC-DEF0-1234"


def _set_pro(monkeypatch, installed):
    import hefesto.cli.main as m

    monkeypatch.setattr(m, "_pro_installed", lambda: installed)


@pytest.mark.parametrize("installed", [True, False])
def test_activate_prints_export_line(monkeypatch, installed):
    _set_pro(monkeypatch, installed)
    result = CliRunner().invoke(cli, ["activate", KEY.lower()])
    assert result.exit_code == 0
    assert f"export HEFESTO_LICENSE_KEY={KEY}" in result.output
    assert ("NOT installed" in result.output) is (not installed)
    assert PRICING_URL not in result.output


def test_activate_rejects_bad_format():
    result = CliRunner().invoke(cli, ["activate", "not-a-key"])
    assert result.exit_code == 1
    assert "Invalid license key format" in result.output


def test_deactivate_prints_unset():
    result = CliRunner().invoke(cli, ["deactivate"])
    assert result.exit_code == 0
    assert "unset HEFESTO_LICENSE_KEY" in result.output


def test_status_licensed_shows_prefix_only(monkeypatch):
    _set_pro(monkeypatch, True)
    monkeypatch.setenv("HEFESTO_LICENSE_KEY", KEY)
    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "Pro package:  installed" in result.output
    assert "HFST-1234-..." in result.output
    assert KEY not in result.output
    assert PRICING_URL not in result.output


def test_status_unlicensed_shows_offer(monkeypatch):
    _set_pro(monkeypatch, False)
    monkeypatch.delenv("HEFESTO_LICENSE_KEY", raising=False)
    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "not installed" in result.output and "not set" in result.output
    assert PRICING_URL in result.output


def test_readme_pricing_has_no_retired_links_or_coupons():
    from pathlib import Path

    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    for retired in ("narapallc.com/trial", "narapallc.com/founding", "Founding40", "FOUNDING100"):
        assert retired not in readme, retired
    assert PRICING_URL in readme
