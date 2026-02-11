from unittest.mock import MagicMock

from hefesto.analyzers.cloud.graph.resolver import ResourceResolver


def test_resolver_merges_with_precedence():
    # fake strategy 1 returns mapping for X
    s1 = MagicMock()
    s1.resolve.return_value = type("RR", (), {"resource_map": {"X": "one"}, "evidence": ["s1"]})()

    # fake strategy 2 tries to override X + adds Y; X should NOT override
    s2 = MagicMock()
    s2.resolve.return_value = type(
        "RR", (), {"resource_map": {"X": "two", "Y": "two"}, "evidence": ["s2"]}
    )()

    resolver = ResourceResolver(strategies=[s1, s2])
    out = resolver.resolve(template={}, region="us-east-1", credentials=MagicMock())

    assert out.resource_map["X"] == "one"
    assert out.resource_map["Y"] == "two"
    assert "ResourceResolver: final resolved 2 logical IDs" in out.evidence[-1]
