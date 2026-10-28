"""Known public client keys are reported at LOW severity, not as CRITICAL secrets.

PostHog project tokens (``phc_``) and Stripe publishable keys (``pk_live_`` /
``pk_test_``) are designed to ship in client code. Secret keys from the same
vendors stay CRITICAL.
"""

import pytest

from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.analysis_models import AnalysisIssueSeverity, AnalysisIssueType

BODY = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def _secrets(code: str):
    issues = SecurityAnalyzer()._check_hardcoded_secrets(None, "src/app/config.py", code)
    return [i for i in issues if i.issue_type == AnalysisIssueType.HARDCODED_SECRET]


def _severities(code: str):
    return {i.severity for i in _secrets(code)}


@pytest.mark.parametrize(
    "line",
    [
        f'POSTHOG_API_KEY = "phc_{BODY}"',
        f'api_key = "pk_live_{BODY}"',
        f'api_key = "pk_test_{BODY}"',
        f'token = "phc_{BODY}"',
    ],
)
def test_public_client_key_is_low(line):
    issues = _secrets(line)
    assert issues, "public key should still be reported, not dropped"
    assert {i.severity for i in issues} == {AnalysisIssueSeverity.LOW}
    assert all(i.metadata.get("public_client_key") for i in issues)
    assert all("public" in i.message.lower() for i in issues)


@pytest.mark.parametrize(
    "line",
    [
        f'api_key = "phx_{BODY}"',  # PostHog personal API key
        f'api_key = "phs_{BODY}"',  # PostHog project secret key
        f'api_key = "sk_live_{BODY}"',  # Stripe secret key
        f'api_key = "rk_live_{BODY}"',  # Stripe restricted key
        f'api_key = "xphc_{BODY}"',  # prefix not at the start of the value
        f'api_key = "my_phc_{BODY}"',
        f'secret_key = "phc_{BODY}"',  # named as a secret: stay conservative
        f'password = "phc_{BODY}"',
        f'secret_key = "pk_live_{BODY}"',
    ],
)
def test_non_public_or_ambiguous_stays_critical(line):
    assert AnalysisIssueSeverity.CRITICAL in _severities(line)


def test_other_secret_on_same_line_still_critical():
    code = f'api_key = "phc_{BODY}"; other = "AKIA{"A" * 16}"'
    sev = _severities(code)
    assert AnalysisIssueSeverity.CRITICAL in sev
    assert AnalysisIssueSeverity.LOW in sev
