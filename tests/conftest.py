"""
Pytest configuration and fixtures for Hefesto tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment variables
os.environ["HEFESTO_ENV"] = "test"
os.environ["GCP_PROJECT_ID"] = "hefesto-test-project"

# Patch C: enable docs and use broad workspace root for pre-existing
# tests that assume /docs is accessible and /tmp paths are valid.
os.environ.setdefault("HEFESTO_EXPOSE_DOCS", "true")
os.environ.setdefault("HEFESTO_WORKSPACE_ROOT", "/")

# Reset settings singleton so test env vars take effect
import hefesto.config.settings as _cfg  # noqa: E402

_cfg._settings = None


@pytest.fixture
def sample_code_hardcoded_secret():
    """Sample code with hardcoded secret."""
    return """
API_KEY = "sk-1234567890abcdef"
SECRET_TOKEN = "token_abc123"

def authenticate():
    return requests.post(API_URL, headers={"Authorization": API_KEY})
"""


@pytest.fixture
def sample_code_sql_injection():
    """Sample code with SQL injection vulnerability."""
    return """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)
"""


@pytest.fixture
def sample_code_safe():
    """Sample safe code."""
    return """
import os

def get_api_key():
    return os.environ.get('API_KEY')

def get_user(user_id):
    query = "SELECT * FROM users WHERE id = ?"
    return db.execute(query, (user_id,))
"""
