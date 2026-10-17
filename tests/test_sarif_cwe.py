"""CWE tags and the SARIF 2.1.0 taxonomy for Python security rules.

One mapping feeds both outputs: GitHub code-scanning tags
``external/cwe/cwe-N`` (no zero-padding) and ``run.taxonomies`` plus
``reportingDescriptor.relationships``. Assert has no CWE. An issue
``metadata["cwe"]`` overrides the table; the COBOL tag text is unchanged.

Every log is validated against the vendored OASIS SARIF 2.1.0 schema.
"""

from hefesto.core.analysis_models import AnalysisIssueType
from hefesto.reports import SARIFReporter
from tests.test_sarif_reporter import _issue, _report, _validate

# Issue types emitted by hefesto/analyzers/security.py. Each one is in the
# registry as a CWE or as an explicit "none".
PYTHON_SECURITY_TYPES = (
    "HARDCODED_SECRET",
    "SQL_INJECTION_RISK",
    "COMMAND_INJECTION",
    "EVAL_USAGE",
    "PICKLE_USAGE",
    "BARE_EXCEPT",
    "ASSERT_IN_PRODUCTION",
)

# (cwe id, relationship kind, rule precision override or None)
EXPECTED = {
    "HARDCODED_SECRET": (798, "equal", None),
    "SQL_INJECTION_RISK": (89, "superset", None),
    "COMMAND_INJECTION": (78, "superset", None),
    "EVAL_USAGE": (95, "relevant", None),
    "PICKLE_USAGE": (502, "relevant", "low"),
    "BARE_EXCEPT": (396, "equal", None),
    "ASSERT_IN_PRODUCTION": None,
}

CWE_TAG = "external/cwe/cwe-{}"


def _log(tmp_path, issues):
    path = tmp_path / "app.py"
    if not path.exists():
        path.write_text("x = 1\n")
    log = SARIFReporter(root=str(tmp_path)).generate_dict(_report(issues))
    _validate(log)
    return log


def _rules(log):
    return {rule["id"]: rule for rule in log["runs"][0]["tool"]["driver"]["rules"]}


def _cwe_tags(rule):
    return [tag for tag in rule["properties"]["tags"] if tag.startswith("external/cwe/")]


def _taxonomy(log):
    taxonomies = log["runs"][0].get("taxonomies") or []
    assert len(taxonomies) == 1
    taxonomy = taxonomies[0]
    assert taxonomy["name"] == "CWE"
    assert taxonomy["organization"] == "MITRE"
    assert taxonomy["version"] == "4.20"
    assert "rules" not in taxonomy
    return taxonomy


def test_registry_covers_every_python_security_rule():
    """I-7: every Python security rule has a CWE or an explicit none with a reason.

    Mapped ids must be in the pinned CWE 4.20 list.
    """
    from hefesto.reports.cwe_map import CWE_NAMES, CWE_VERSION, EXPLICIT_NONE_REASON, RULE_CWE

    assert CWE_VERSION == "4.20"
    assert set(RULE_CWE) == set(PYTHON_SECURITY_TYPES)
    for issue_type in PYTHON_SECURITY_TYPES:
        assert issue_type in {member.value for member in AnalysisIssueType}
        expected = EXPECTED[issue_type]
        mapped = RULE_CWE[issue_type]
        if expected is None:
            assert mapped is None
            assert EXPLICIT_NONE_REASON[issue_type]
            continue
        cwe_id, kind, precision = expected
        assert len(mapped) == 1
        assert mapped[0].cwe_id == cwe_id
        assert mapped[0].kind == kind
        assert mapped[0].precision == precision
        assert cwe_id in CWE_NAMES
    for issue_type, mapped in RULE_CWE.items():
        if mapped is None:
            assert EXPLICIT_NONE_REASON[issue_type]
            continue
        for row in mapped:
            assert row.cwe_id in CWE_NAMES


def test_every_mapped_rule_emits_the_tag_and_the_relationship(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("\n".join("x = 1" for _ in PYTHON_SECURITY_TYPES) + "\n")
    issues = []
    for line, issue_type in enumerate(PYTHON_SECURITY_TYPES, start=1):
        confidence = 0.99 if issue_type == "PICKLE_USAGE" else None
        issues.append(
            _issue(
                path,
                line,
                issue_type,
                "HIGH",
                confidence=confidence,
            )
        )
    log = _log(tmp_path, issues)
    rules = _rules(log)
    taxonomy = _taxonomy(log)
    taxa = {taxon["id"]: taxon for taxon in taxonomy["taxa"]}
    assert [taxon["id"] for taxon in taxonomy["taxa"]] == sorted(taxa, key=int)

    for issue_type, expected in EXPECTED.items():
        rule = rules[issue_type]
        tags = _cwe_tags(rule)
        relationships = rule.get("relationships") or []
        if expected is None:
            assert tags == []
            assert relationships == []
            continue
        cwe_id, kind, precision = expected
        digits = str(cwe_id)
        assert tags == [CWE_TAG.format(digits)]
        padded = f"{cwe_id:03d}"
        if padded != digits:
            assert CWE_TAG.format(padded) not in tags
        assert len(relationships) == 1
        relationship = relationships[0]
        assert relationship["kinds"] == [kind]
        assert relationship["target"] == {
            "id": digits,
            "toolComponent": {"name": "CWE", "index": 0},
        }
        assert taxa[digits]["helpUri"] == (f"https://cwe.mitre.org/data/definitions/{digits}.html")
        assert taxa[digits]["name"]
        if precision:
            assert rule["properties"]["precision"] == precision
        else:
            assert rule["properties"]["precision"] != "low"


def test_unmapped_rules_emit_neither_tag_nor_relationship(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("x = 1\n")
    issues = [
        _issue(path, 1, "ASSERT_IN_PRODUCTION", "MEDIUM"),
        _issue(path, 1, "LONG_FUNCTION", "MEDIUM"),
        _issue(path, 1, "TF_HARDCODED_SECRET", "HIGH"),
        _issue(path, 1, "MISSING_DOCSTRING", "LOW"),
    ]
    log = _log(tmp_path, issues)
    assert "taxonomies" not in log["runs"][0]
    for rule in _rules(log).values():
        assert _cwe_tags(rule) == []
        assert "relationships" not in rule


def test_tag_and_taxonomy_agree(tmp_path):
    """I-8: every CWE tag has a matching taxon and relationship, and the reverse."""
    path = tmp_path / "app.py"
    path.write_text("a\nb\nc\n")
    issues = [
        _issue(path, 1, "SQL_INJECTION_RISK", "CRITICAL"),
        _issue(path, 2, "LONG_FUNCTION", "LOW"),
        _issue(path, 3, "BARE_EXCEPT", "MEDIUM"),
    ]
    log = _log(tmp_path, issues)
    taxonomy = _taxonomy(log)
    taxon_ids = {taxon["id"] for taxon in taxonomy["taxa"]}
    referenced = set()
    for rule in _rules(log).values():
        tags = _cwe_tags(rule)
        relationships = rule.get("relationships") or []
        tag_ids = {tag.split("cwe-")[-1] for tag in tags}
        rel_ids = set()
        for relationship in relationships:
            target = relationship["target"]
            assert target["toolComponent"]["name"] == "CWE"
            rel_ids.add(target["id"])
            referenced.add(target["id"])
        assert tag_ids == rel_ids
        assert len(tags) <= 20
    assert referenced == taxon_ids
    assert taxon_ids == {"89", "396"}
    assert _cwe_tags(_rules(log)["LONG_FUNCTION"]) == []


def test_metadata_cwe_overrides_the_registry_and_cobol_tag_is_unchanged(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("x = 1\n")
    secret = _issue(path, 1, "HARDCODED_SECRET", "CRITICAL", metadata={"cwe": "CWE-259"})
    cobol = _issue(
        path,
        1,
        "COBOL_ACCEPT_UNVALIDATED",
        "HIGH",
        rule_id="COBOL010",
        metadata={"cwe": "CWE-20"},
        confidence=0.95,
    )
    # Digits in metadata are kept as written (no zero-padding added or removed).
    as_written = _issue(
        path,
        1,
        "EVAL_USAGE",
        "HIGH",
        metadata={"cwe": "CWE-020"},
    )
    log = _log(tmp_path, [secret, cobol, as_written])
    rules = _rules(log)
    assert _cwe_tags(rules["HARDCODED_SECRET"]) == ["external/cwe/cwe-259"]
    assert "external/cwe/cwe-798" not in rules["HARDCODED_SECRET"]["properties"]["tags"]
    assert rules["COBOL010"]["properties"]["tags"] == [
        "security",
        "cobol",
        "external/cwe/cwe-20",
    ]
    assert rules["COBOL010"]["properties"]["precision"] == "very-high"
    assert _cwe_tags(rules["EVAL_USAGE"]) == ["external/cwe/cwe-020"]
    taxonomy = _taxonomy(log)
    assert {taxon["id"] for taxon in taxonomy["taxa"]} == {"259", "20", "020"}


def test_sarif_cwe_output_is_deterministic(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("eval(a)\nimport pickle\n")
    forward = [
        _issue(path, 1, "EVAL_USAGE", "CRITICAL"),
        _issue(path, 2, "PICKLE_USAGE", "HIGH"),
        _issue(path, 1, "ASSERT_IN_PRODUCTION", "MEDIUM"),
    ]
    first = _log(tmp_path, forward)
    second = _log(tmp_path, list(reversed(forward)))
    assert first == second
    again = SARIFReporter(root=str(tmp_path)).generate(_report(forward))
    assert again == SARIFReporter(root=str(tmp_path)).generate(_report(list(reversed(forward))))
