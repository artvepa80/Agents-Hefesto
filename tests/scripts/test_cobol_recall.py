"""Recall per COBOL rule on the seeded-issue fixture (scripts/cobol_recall.py)."""

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT_PATH = ROOT / "scripts" / "cobol_recall.py"
FIXTURE = ROOT / "tests" / "fixtures" / "cobol" / "recall"
ALL_RULES = {f"COBOL{n:03d}" for n in range(1, 16)}


def _load_module():
    spec = importlib.util.spec_from_file_location("cobol_recall_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cobol_recall_script"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()
SEEDS = mod.load_seeds(FIXTURE)
RESULTS = mod.match(SEEDS, mod.scan(FIXTURE))


def test_fixture_covers_every_rule_at_least_twice():
    counts = Counter(seed["rule"] for seed in SEEDS["seeds"])
    assert set(counts) == ALL_RULES
    assert min(counts.values()) >= 2
    assert len(SEEDS["seeds"]) >= 30
    for seed in SEEDS["seeds"]:
        assert (FIXTURE / seed["file"]).is_file(), seed


def test_every_regular_seed_is_found():
    missed = [r for r in RESULTS if not r["found"] and not r.get("known_limit")]
    assert missed == []


def test_known_limits_are_still_missed():
    # If one starts being found, drop its known_limit flag and update the docs.
    found = [r for r in RESULTS if r["found"] and r.get("known_limit")]
    assert found == []


def test_recall_table_and_cli(capsys):
    table = mod.recall(RESULTS)
    assert set(table) == ALL_RULES | {"ALL"}
    hit, total = table["ALL"]
    assert total == len(SEEDS["seeds"])
    assert hit == total - sum(1 for s in SEEDS["seeds"] if s.get("known_limit"))
    assert mod.main(["--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["recall"]["ALL"] == [hit, total]
    assert mod.main(["--min-recall", "1.0"]) == 1
    assert "MISSED (known limit)" in capsys.readouterr().out


def test_match_tolerance():
    seeds = {"tolerance": 2, "seeds": [{"rule": "COBOL001", "file": "a.cbl", "line": 10}]}
    assert mod.match(seeds, [("COBOL001", "a.cbl", 12)])[0]["found"]
    assert not mod.match(seeds, [("COBOL001", "a.cbl", 13)])[0]["found"]
    assert not mod.match(seeds, [("COBOL002", "a.cbl", 10)])[0]["found"]
    assert not mod.match(seeds, [("COBOL001", "b.cbl", 10)])[0]["found"]


def test_after_expansion_seeds_need_copy_expansion(monkeypatch):
    # Seeds in RCL08 live in copybook text (or are created by REPLACING): with
    # expansion off they are all missed, with it on they are all found.
    from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer

    expansion = [r for r in RESULTS if r.get("after_expansion")]
    assert len(expansion) >= 7
    assert {r["rule"] for r in expansion} >= {
        "COBOL004",
        "COBOL005",
        "COBOL008",
        "COBOL011",
        "COBOL012",
        "COBOL013",
        "COBOL014",
    }
    assert all(r["found"] for r in expansion)

    monkeypatch.setattr(CobolGovernanceAnalyzer, "_copy_expander", lambda self: None)
    without = mod.match(SEEDS, mod.scan(FIXTURE))
    assert not any(r["found"] for r in without if r.get("after_expansion"))
