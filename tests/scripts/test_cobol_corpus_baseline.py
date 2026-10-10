"""Offline tests for scripts/cobol_corpus_baseline.py (no network)."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "cobol_corpus_baseline.py"
BASELINE_PATH = Path(__file__).parents[2] / "benchmark" / "cobol" / "baseline.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("cobol_corpus_baseline_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cobol_corpus_baseline_script"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def _report(root: Path, issues):
    files = {}
    for rule, rel, line, sev in issues:
        files.setdefault(rel, []).append(
            {"file": str(root / rel), "line": line, "rule_id": rule, "severity": sev}
        )
    return {
        "summary": {"files_analyzed": len(files), "total_loc": 100, "duration_seconds": 0.5},
        "files": [{"file": str(root / rel), "issues": iss} for rel, iss in files.items()],
    }


def _run(corpus_findings):
    return {
        "corpora": {
            name: {"commit": "abc", "findings": findings, "timing": {"analyze_seconds": 1.0}}
            for name, findings in corpus_findings.items()
        }
    }


class TestSummarize:
    def test_counts_and_relative_paths(self, tmp_path):
        report = _report(
            tmp_path,
            [
                ("COBOL001", "src/a.cbl", 10, "HIGH"),
                ("COBOL001", "src/a.cbl", 20, "HIGH"),
                ("COBOL008", "src/b.cbl", 5, "CRITICAL"),
                ("missing-safety", "run.sh", 1, "MEDIUM"),
            ],
        )
        data = mod.summarize(report, tmp_path)
        assert data["total_findings"] == 4
        assert data["cobol_findings"] == 3
        assert data["by_rule"] == {"COBOL001": 2, "COBOL008": 1, "missing-safety": 1}
        assert data["by_severity"] == {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 1}
        assert data["per_file"]["src/a.cbl"] == {"COBOL001": 2}
        assert ["COBOL008", "src/b.cbl", 5] in data["findings"]
        assert data["findings"] == sorted(data["findings"])

    def test_falls_back_to_type_when_no_rule_id(self, tmp_path):
        report = {
            "files": [{"file": str(tmp_path / "x.cbl"), "issues": [{"type": "T", "line": 1}]}]
        }
        assert mod.summarize(report, tmp_path)["by_rule"] == {"T": 1}


class TestDiff:
    def test_no_changes(self):
        base = _run({"c": [["COBOL001", "a.cbl", 1]]})
        result = mod.diff(base, base)
        assert result["c"]["rules"] == {}
        assert not mod.has_changes(result)
        assert "no finding changes" in mod.format_diff(result)

    def test_new_and_removed_per_rule(self):
        base = _run({"c": [["COBOL001", "a.cbl", 1], ["COBOL004", "a.cbl", 9]]})
        cur = _run(
            {"c": [["COBOL001", "a.cbl", 1], ["COBOL011", "b.cbl", 3], ["COBOL011", "b.cbl", 3]]}
        )
        result = mod.diff(base, cur)
        rules = result["c"]["rules"]
        assert rules["COBOL004"] == {"new": [], "removed": [["a.cbl", 9]]}
        assert rules["COBOL011"] == {"new": [["b.cbl", 3], ["b.cbl", 3]], "removed": []}
        assert "COBOL001" not in rules
        assert mod.has_changes(result)
        text = mod.format_diff(result)
        assert "COBOL011: +2 -0" in text and "- a.cbl:9" in text

    def test_missing_corpus_and_commit_change(self):
        base = _run({"c": [], "gone": []})
        cur = _run({"c": []})
        cur["corpora"]["c"]["commit"] = "def"
        result = mod.diff(base, cur)
        assert result["gone"] == {"status": "missing in current"}
        assert result["c"]["commit_changed"] == ["abc", "def"]
        assert mod.has_changes(result)

    def test_main_compare_with_saved_run(self, tmp_path, capsys):
        base = _run({"c": [["COBOL001", "a.cbl", 1]]})
        (tmp_path / "b.json").write_text(json.dumps(base))
        (tmp_path / "cur.json").write_text(json.dumps(base))
        args = [
            "compare",
            "--baseline",
            str(tmp_path / "b.json"),
            "--current",
            str(tmp_path / "cur.json"),
        ]
        assert mod.main(args) == 0
        capsys.readouterr()
        cur = _run({"c": []})
        (tmp_path / "cur.json").write_text(json.dumps(cur))
        assert mod.main(args + ["--json"]) == 1
        out = json.loads(capsys.readouterr().out)
        assert out["c"]["rules"]["COBOL001"]["removed"] == [["a.cbl", 1]]


class TestCommittedBaseline:
    def test_baseline_matches_pins(self):
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        assert data["schema_version"] == mod.SCHEMA_VERSION
        pins = {c["name"]: c for c in mod.CORPORA}
        assert set(data["corpora"]) == set(pins)
        for name, corpus in data["corpora"].items():
            assert corpus["commit"] == pins[name]["commit"]
            assert corpus["license"] == pins[name]["license"]
            assert (
                corpus["total_findings"]
                == len(corpus["findings"])
                == sum(corpus["by_rule"].values())
            )
            assert all(not f[1].startswith("/") for f in corpus["findings"])


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_checkout_pins_local_repo(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q"], cwd=src, check=True)
    (src / "a.cbl").write_text("x\n")
    subprocess.run(git + ["add", "."], cwd=src, check=True)
    subprocess.run(git + ["commit", "-qm", "one"], cwd=src, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True
    ).stdout.strip()
    (src / "a.cbl").write_text("y\n")
    subprocess.run(git + ["commit", "-qam", "two"], cwd=src, check=True)
    corpus = {"name": "local", "url": src.as_uri(), "commit": sha, "license": "MIT"}
    subprocess.run(
        ["git", "config", "uploadpack.allowReachableSHA1InWant", "true"], cwd=src, check=True
    )
    path = mod.checkout(corpus, tmp_path / "work")
    assert (path / "a.cbl").read_text() == "x\n"
    assert mod.checkout(corpus, tmp_path / "work") == path  # reused


class TestHefestoRef:
    def test_committed_baseline_from_clean_tree(self):
        ref = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["hefesto"]
        assert ref["dirty"] is False, "regenerate the baseline after committing the analyzer"
        assert ref["commit"] and len(ref["commit"]) == 40
        assert ref["analyzer_tree"] and len(ref["analyzer_tree"]) == 40

    @pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
    def test_dirty_flag(self, tmp_path, monkeypatch, capsys):
        git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(git + ["init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / "hefesto").mkdir()
        (tmp_path / "hefesto" / "a.py").write_text("x = 1\n")
        (tmp_path / "pyproject.toml").write_text('version = "9.9.9"\n')
        subprocess.run(git + ["add", "."], cwd=tmp_path, check=True)
        subprocess.run(git + ["commit", "-qm", "one"], cwd=tmp_path, check=True)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "rev-parse", "HEAD:hefesto"], cwd=tmp_path, capture_output=True, text=True
        ).stdout.strip()
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        assert mod._hefesto_ref() == {
            "version": "9.9.9",
            "commit": head,
            "analyzer_tree": tree,
            "dirty": False,
        }
        (tmp_path / "docs.md").write_text("unrelated\n")
        assert mod._hefesto_ref()["dirty"] is False
        (tmp_path / "hefesto" / "a.py").write_text("x = 2\n")
        assert mod._hefesto_ref()["dirty"] is True
        assert "uncommitted analyzer changes" in capsys.readouterr().err
