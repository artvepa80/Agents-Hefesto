"""Tests for scripts/cobol_label_precision.py and the Phase 3 labels fixture."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT_PATH = ROOT / "scripts" / "cobol_label_precision.py"
LABELS_PATH = ROOT / "tests" / "fixtures" / "cobol" / "labels" / "phase3_labels.json"
BASELINE_PATH = ROOT / "benchmark" / "cobol" / "baseline.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("cobol_label_precision_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cobol_label_precision_script"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()
DOC = json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def _label(rule, verdict, sets, line=1, file="a.cbl", corpus="c"):
    return {
        "corpus": corpus,
        "rule": rule,
        "file": file,
        "line": line,
        "verdict": verdict,
        "reason": "r",
        "sets": sets,
    }


class TestFixture:
    def test_fixture_is_valid(self):
        assert mod.validate(DOC) == []

    def test_fixture_has_at_least_300_labels(self):
        assert len(DOC["labels"]) >= 300

    def test_every_labelled_rule_has_a_criterion(self):
        rules = {label["rule"] for label in DOC["labels"]}
        assert rules <= set(DOC["criteria"])

    def test_latest_labels_match_the_committed_baseline(self):
        """On pinned corpora the latest run's labels are exactly the COBOL findings
        in baseline.json (every finding labelled, no stale label)."""
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        for corpus, data in baseline["corpora"].items():
            findings = {tuple(f) for f in data["findings"] if f[0].startswith("COBOL")}
            labelled = {
                (label["rule"], label["file"], label["line"])
                for label in DOC["labels"]
                if label["corpus"] == corpus and mod.LATEST_RUN in label["sets"]
            }
            assert labelled == findings, corpus

    def test_precision_did_not_regress(self):
        table = mod.precision(DOC)
        for rule, runs in table.items():
            for older, newer in zip(mod.RUNS, mod.RUNS[1:]):
                if older in runs and newer in runs:
                    assert runs[newer][0] / runs[newer][1] >= runs[older][0] / runs[older][1], (
                        rule,
                        newer,
                    )
        cobol004 = table["COBOL004"]["leftovers"]
        assert cobol004[0] / cobol004[1] >= 0.9


class TestValidate:
    def test_rejects_bad_verdict_sets_and_duplicates(self):
        doc = {
            "labels": [
                _label("COBOL001", "MAYBE", ["after"]),
                _label("COBOL001", "TP", ["later"], line=2),
                _label("COBOL001", "TP", ["after"], line=3),
                _label("COBOL001", "TP", ["after"], line=3),
            ]
        }
        problems = mod.validate(doc)
        assert len(problems) == 3

    def test_rejects_missing_fields(self):
        assert mod.validate({"labels": [{"rule": "COBOL001"}]})
        assert mod.validate({}) == ["'labels' must be a list"]


class TestPrecision:
    def test_counts_per_rule_and_set(self):
        doc = {
            "labels": [
                _label("COBOL004", "TP", ["before", "after"], line=1),
                _label("COBOL004", "FP", ["before"], line=2),
                _label("COBOL004", "FP", ["before"], line=3),
                _label("COBOL007", "TP", ["after"], line=4),
            ]
        }
        assert mod.precision(doc) == {
            "COBOL004": {"after": (1, 1), "before": (1, 3)},
            "COBOL007": {"after": (1, 1)},
        }

    def test_main_prints_table(self, capsys):
        assert mod.main(["--labels", str(LABELS_PATH)]) == 0
        out = capsys.readouterr().out
        assert "COBOL004" in out and "before" in out

    def test_main_fails_on_invalid_labels(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"labels": [{"rule": "x"}]}), encoding="utf-8")
        assert mod.main(["--labels", str(bad)]) == 1
