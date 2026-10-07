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


@pytest.mark.parametrize("args", [["info"], ["status"], ["deactivate"]])
def test_pro_only_commands_print_pricing_url(args):
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 1
    assert PRICING_URL in result.output
    assert "$8/month" in result.output
