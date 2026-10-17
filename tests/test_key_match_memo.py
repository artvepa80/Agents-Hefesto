"""Performance guard for JSON/TOML key matching (deterministic, no wall clock).

4.20.0 re-tokenized every pattern and every key on every call, so analysis
time grew with the number of keys in the document (about 3 s per MB of JSON).
Key tokenization must be bounded by the unique keys plus the patterns.
"""

import json

import pytest

from hefesto.analyzers.devops import key_match
from hefesto.analyzers.devops.json_analyzer import JsonAnalyzer
from hefesto.analyzers.devops.toml_analyzer import TomlAnalyzer


@pytest.fixture
def counted_tokens(monkeypatch):
    calls = []
    original = key_match._tokens

    def counting(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(key_match, "_tokens", counting)
    key_match.clear_caches()
    yield calls
    key_match.clear_caches()


def _items(n):
    return [{"id": i, "name": "item-%d" % i, "tags": ["x", "y", "z"]} for i in range(n)]


def _all_patterns():
    pats = set()
    for cls in (JsonAnalyzer, TomlAnalyzer):
        for attr in ("SECRET_KEY_PATTERNS", "INSECURE_URL_KEYS"):
            pats.update(getattr(cls, attr, ()))
    return pats


def test_json_tokenization_is_bounded_by_unique_keys(counted_tokens):
    content = json.dumps({"password": "Sup3rS3cretValue!2026", "items": _items(5000)})
    issues = JsonAnalyzer().analyze("data.json", content)
    assert [i.rule_id for i in issues].count("J001") == 1
    unique_keys = {"password", "items", "id", "name", "tags"}
    assert len(counted_tokens) <= len(unique_keys) + len(_all_patterns())


def test_result_is_unchanged_by_the_cache():
    key_match.clear_caches()
    keys = ["api_key", "apiKey", "author", "auth_token", "secrets", "x-api-key", "url", "a b"]
    first = [key_match.key_has_pattern(k, ["api_key", "auth", "secret"]) for k in keys]
    second = [key_match.key_has_pattern(k, ["api_key", "auth", "secret"]) for k in keys]
    assert first == second == [True, True, False, True, True, True, False, False]


def test_list_and_tuple_patterns_match_the_same():
    assert key_match.key_has_pattern("apiKey", ["api_key"]) == key_match.key_has_pattern(
        "apiKey", ("api_key",)
    )
