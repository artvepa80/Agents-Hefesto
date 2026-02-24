# Fixture: clean file — no resource safety issues
from functools import lru_cache

# Module-level constant (not mutable — no issue)
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30


@lru_cache(maxsize=128)
def get_config(key):
    """Bounded cache — no issue."""
    return {"key": key}


def fetch_data(url):
    """Uses context-manager — no issue."""
    import requests

    with requests.Session() as session:
        return session.get(url)
