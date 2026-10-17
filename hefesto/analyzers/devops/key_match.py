"""Token matching for secret and URL keys in JSON and TOML.

A substring test treats ``author`` as ``auth`` and a dependency name such as
``@aws-sdk/credential-providers`` as a credential. Keys match when a pattern's
tokens sit together in the key (``api_key``, ``api-key``, ``apiKey``).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import List, Sequence, Tuple

# Immediate children of these objects are package names mapped to versions.
DEPENDENCY_MAP_KEYS = frozenset(
    {
        "dependencies",
        "devdependencies",
        "peerdependencies",
        "optionaldependencies",
        "bundleddependencies",
        "requires",
    }
)


def _tokens(text: str) -> List[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    return [token for token in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if token]


def _with_plurals_stripped(tokens: Sequence[str]) -> List[str]:
    stripped: List[str] = []
    for token in tokens:
        if len(token) > 3 and token.endswith("s"):
            stripped.append(token[:-1])
        else:
            stripped.append(token)
    return stripped


def _sequence_contains(sequence: Sequence[str], pattern_tokens: Sequence[str]) -> bool:
    """True when ``pattern_tokens`` is a consecutive slice of ``sequence``.

    A one-token pattern also matches tokens joined in order (``api`` + ``key``
    is ``apikey``).
    """
    width = len(pattern_tokens)
    if width == 0:
        return False
    limit = len(sequence) - width + 1
    for start in range(limit):
        if list(sequence[start : start + width]) == list(pattern_tokens):
            return True
    if width != 1:
        return False
    target = pattern_tokens[0]
    for start in range(len(sequence)):
        joined = ""
        for part in sequence[start:]:
            joined += part
            if joined == target:
                return True
            if len(joined) > len(target):
                break
    return False


def key_has_pattern(key: str, patterns: Sequence[str]) -> bool:
    """True when ``key`` contains a pattern as whole tokens, not a substring.

    Memoized: a document repeats the same keys many times, and tokenizing is
    pure, so each key and each pattern list is tokenized once.
    """
    return _key_has_pattern(str(key), tuple(patterns))


@lru_cache(maxsize=8192)
def _key_has_pattern(key: str, patterns: Tuple[str, ...]) -> bool:
    sequences = _key_sequences(key)
    for pattern_tokens in _pattern_tokens(patterns):
        for sequence in sequences:
            if _sequence_contains(sequence, pattern_tokens):
                return True
    return False


@lru_cache(maxsize=8192)
def _key_sequences(key: str) -> Tuple[Tuple[str, ...], ...]:
    """The key's tokens, plus a copy with plurals stripped when it differs."""
    if any(char.isspace() for char in key):
        return ()
    primary = tuple(_tokens(key))
    if not primary:
        return ()
    deplural = tuple(_with_plurals_stripped(primary))
    if deplural != primary:
        return (primary, deplural)
    return (primary,)


@lru_cache(maxsize=64)
def _pattern_tokens(patterns: Tuple[str, ...]) -> Tuple[Tuple[str, ...], ...]:
    return tuple(tuple(_tokens(pattern)) for pattern in patterns)


def clear_caches() -> None:
    """Drop the memoized results (tests that count tokenizer calls use it)."""
    _key_has_pattern.cache_clear()
    _key_sequences.cache_clear()
    _pattern_tokens.cache_clear()
