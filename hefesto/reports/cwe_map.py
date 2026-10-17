"""Rule-to-CWE mapping for SARIF tags and the CWE taxonomy.

One table feeds both GitHub code-scanning tags (``external/cwe/cwe-N``,
no zero-padding) and SARIF 2.1.0 ``relationships`` on each rule. The
SARIF writer turns the ids used in a run into ``run.taxonomies``.

Approved by Arturo on 2026-10-17 (design item 29). Ids are CWE 4.20.
An issue ``metadata["cwe"]`` overrides this table; that override is
applied by the SARIF writer, which also leaves the COBOL tag text as
written (no zero-padding).

Relationship kinds are the SARIF names (equal, superset, relevant).
``precision`` on a row replaces the confidence-derived rule precision.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

CWE_VERSION = "4.20"

# Weakness names from CWE 4.20. A mapped id must be in this dict.
# CWE-20 is not a Python mapping; COBOL rules still emit it from metadata.
CWE_NAMES: Dict[int, str] = {
    20: "Improper Input Validation",
    78: (
        "Improper Neutralization of Special Elements used in an OS Command "
        "('OS Command Injection')"
    ),
    89: ("Improper Neutralization of Special Elements used in an SQL Command " "('SQL Injection')"),
    95: (
        "Improper Neutralization of Directives in Dynamically Evaluated Code " "('Eval Injection')"
    ),
    396: "Declaration of Catch for Generic Exception",
    502: "Deserialization of Untrusted Data",
    798: "Use of Hard-coded Credentials",
}


@dataclass(frozen=True)
class CweMapping:
    """One CWE linked from a rule, and how tight the fit is."""

    cwe_id: int
    kind: str
    precision: Optional[str] = None


# None: the rule is explicitly unmapped (no CWE tag, no relationship).
RULE_CWE: Dict[str, Optional[Tuple[CweMapping, ...]]] = {
    "HARDCODED_SECRET": (CweMapping(798, "equal"),),
    "SQL_INJECTION_RISK": (CweMapping(89, "superset"),),
    "COMMAND_INJECTION": (CweMapping(78, "superset"),),
    "EVAL_USAGE": (CweMapping(95, "relevant"),),
    # Import-only detector: do not claim deserialization was found.
    "PICKLE_USAGE": (CweMapping(502, "relevant", precision="low"),),
    "BARE_EXCEPT": (CweMapping(396, "equal"),),
    "ASSERT_IN_PRODUCTION": None,
}

EXPLICIT_NONE_REASON: Dict[str, str] = {
    "ASSERT_IN_PRODUCTION": (
        "No CWE. CWE-617 (Reachable Assertion) is about assertions that crash; "
        "this rule is about assert statements removed by python -O. "
        "CWE-703 is a Pillar and discouraged for mapping."
    ),
}


def links_for(issue_type: str) -> Tuple[CweMapping, ...]:
    """CWE rows for an issue type. Empty when the type is unmapped or explicit none."""
    mapped = RULE_CWE.get(issue_type)
    if not mapped:
        return ()
    return mapped
