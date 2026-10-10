"""
SARIF 2.1.0 reporter (``hefesto analyze --output sarif``).

Produces a SARIF log that GitHub code scanning accepts
(``github/codeql-action/upload-sarif``), for every analyzer, not only COBOL:

* one ``reportingDescriptor`` per rule (``rule_id`` when the analyzer sets
  one, such as ``COBOL004`` or ``SC2086``; otherwise the issue type, such as
  ``HARDCODED_SECRET``) with name, short/full description, help text and
  markdown, a help URI, a default level and properties: tags (``security``
  or ``maintainability``, plus ``external/cwe/cwe-N`` when known),
  ``precision``, ``problem.severity`` and, for security rules,
  ``security-severity`` (CRITICAL 9.5, HIGH 8.0, MEDIUM 5.5, LOW 3.0);
* results with ``level`` (CRITICAL/HIGH -> error, MEDIUM -> warning,
  LOW -> note), the message, a repo-relative URI (``uriBaseId`` %SRCROOT%),
  the start line, ``partialFingerprints`` that survive line shifts (rule,
  file and the text of the flagged line, not its number) and, for COBOL
  findings that come from a copybook, a related location in the copybook;
* GitHub upload limits are respected: at most 25,000 results per run
  (highest severity kept), 1,000 related locations per result, 20 tags per
  rule, and the serialized log is kept under 10 MB once gzipped. What was
  dropped is reported in ``invocations[0].toolExecutionNotifications``.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import gzip
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from hefesto.core.analysis_models import AnalysisIssue, AnalysisReport

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
INFORMATION_URI = "https://github.com/artvepa80/Agents-Hefesto"
RULES_HELP_URI = INFORMATION_URI + "/blob/main/docs/ANALYSIS_RULES.md"
COBOL_HELP_URI = INFORMATION_URI + "#language-support"
FINGERPRINT_KEY = "hefestoFingerprint/v1"

# GitHub code scanning upload limits (docs: "SARIF support for code scanning")
MAX_RESULTS = 25_000
MAX_RELATED_LOCATIONS = 1_000
MAX_TAGS = 20
MAX_GZIP_BYTES = 10 * 1024 * 1024

LEVELS = {"CRITICAL": "error", "HIGH": "error", "MEDIUM": "warning", "LOW": "note"}
PROBLEM_SEVERITY = {
    "CRITICAL": "error",
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "recommendation",
}
SECURITY_SEVERITY = {"CRITICAL": "9.5", "HIGH": "8.0", "MEDIUM": "5.5", "LOW": "3.0"}
_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

# Issue types that are security findings (tagged "security", given a
# security-severity so GitHub shows them as security alerts).
_SECURITY_WORDS = re.compile(
    r"SECRET|CREDENTIAL|INJECTION|EVAL_USAGE|PICKLE|UNSAFE|TLS_BYPASS|PRIVILEGE"
    r"|PUBLIC_ACCESS|OPEN_SECURITY_GROUP|OVERLY_PERMISSIVE|MISSING_ENCRYPTION"
    r"|INSECURE|MISCONFIGURATION|EXECUTION_POLICY|REMOTE_CODE|INVOKE_EXPRESSION"
    r"|ROOT_USER|CURL_BASH|MISSING_USER|WEAK_PERMISSIONS|ACCEPT_UNVALIDATED"
    r"|CONNECT_LITERAL|MISSING_SAFETY"
)
_CWE = re.compile(r"CWE-(\d+)", re.I)
_DIGITS = re.compile(r"\d+")
_SPACES = re.compile(r"\s+")


class SARIFReporter:
    """Generates SARIF 2.1.0 logs for GitHub code scanning and other tools."""

    def __init__(self, root: Optional[str] = None, max_results: int = MAX_RESULTS) -> None:
        """``root``: directory URIs are made relative to (default: the git
        top level of the current directory, else the current directory)."""
        self.root = Path(root).resolve() if root else _default_root()
        self.max_results = max_results
        self._lines: Dict[str, List[str]] = {}

    def generate(self, report: AnalysisReport) -> str:
        """SARIF log as a JSON string."""
        return json.dumps(self.generate_dict(report), indent=2, ensure_ascii=False)

    def generate_dict(self, report: AnalysisReport) -> Dict[str, Any]:
        issues = sorted(
            report.get_all_issues(),
            key=lambda i: (_RANK.get(i.severity.value, 4), i.file_path, i.line, _rule_id(i)),
        )
        notes: List[str] = []
        if len(issues) > self.max_results:
            notes.append(
                f"{len(issues) - self.max_results} lower-severity results were dropped to stay "
                f"within the {self.max_results:,}-results limit of GitHub code scanning."
            )
            issues = issues[: self.max_results]
        log = self._log(issues, notes)
        while issues and _gzip_size(log) > MAX_GZIP_BYTES:
            keep = len(issues) * 3 // 4
            notes.append(
                f"{len(issues) - keep} lower-severity results were dropped to keep the "
                "gzipped SARIF under 10 MB."
            )
            issues = issues[:keep]
            log = self._log(issues, notes)
        return log

    # ------------------------------------------------------------- building

    def _log(self, issues: List[AnalysisIssue], notes: List[str]) -> Dict[str, Any]:
        by_rule: Dict[str, List[AnalysisIssue]] = {}
        for issue in issues:
            by_rule.setdefault(_rule_id(issue), []).append(issue)
        order = list(by_rule)
        index = {rid: n for n, rid in enumerate(order)}
        seen: Dict[str, int] = {}
        results = [self._result(issue, index, seen) for issue in self._stable_order(issues)]
        invocation: Dict[str, Any] = {"executionSuccessful": True}
        if notes:
            invocation["toolExecutionNotifications"] = [
                {"level": "warning", "message": {"text": text}} for text in notes
            ]
        return {
            "$schema": SARIF_SCHEMA,
            "version": SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "HefestoAI",
                            "informationUri": INFORMATION_URI,
                            "version": _version(),
                            "semanticVersion": _version(),
                            "rules": [_rule(rid, by_rule[rid]) for rid in order],
                        }
                    },
                    "invocations": [invocation],
                    "columnKind": "utf16CodeUnits",
                    "results": results,
                }
            ],
        }

    def _stable_order(self, issues: List[AnalysisIssue]) -> List[AnalysisIssue]:
        """File/line order, so occurrence numbers in fingerprints are stable."""
        return sorted(issues, key=lambda i: (self._uri(i.file_path)[0], i.line, _rule_id(i)))

    def _result(
        self, issue: AnalysisIssue, index: Dict[str, int], seen: Dict[str, int]
    ) -> Dict[str, Any]:
        rid = _rule_id(issue)
        uri, base = self._uri(issue.file_path)
        location: Dict[str, Any] = {"uri": uri}
        if base:
            location["uriBaseId"] = base
        result: Dict[str, Any] = {
            "ruleId": rid,
            "ruleIndex": index[rid],
            "level": LEVELS.get(issue.severity.value, "warning"),
            "message": {"text": issue.message.strip() or rid},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": location,
                        "region": {"startLine": max(1, int(issue.line or 1))},
                    }
                }
            ],
            "partialFingerprints": {FINGERPRINT_KEY: self._fingerprint(issue, rid, uri, seen)},
        }
        related = self._related(issue)
        if related:
            result["relatedLocations"] = related[:MAX_RELATED_LOCATIONS]
        properties: Dict[str, Any] = {"severity": issue.severity.value, "engine": issue.engine}
        if issue.function_name:
            properties["function"] = issue.function_name
        if issue.confidence is not None:
            properties["confidence"] = issue.confidence
        result["properties"] = properties
        return result

    def _related(self, issue: AnalysisIssue) -> List[Dict[str, Any]]:
        """COBOL: the copybook line a finding was expanded from."""
        origin = (issue.metadata or {}).get("expanded_from")
        if not isinstance(origin, dict) or not origin.get("file"):
            return []
        uri, base = self._uri(str(origin["file"]))
        location: Dict[str, Any] = {"uri": uri}
        if base:
            location["uriBaseId"] = base
        return [
            {
                "id": 1,
                "message": {"text": f"copybook {origin.get('copybook', '')}".strip()},
                "physicalLocation": {
                    "artifactLocation": location,
                    "region": {"startLine": max(1, int(origin.get("line") or 1))},
                },
            }
        ]

    def _uri(self, path: str) -> Tuple[str, Optional[str]]:
        """Repo-relative URI (with %SRCROOT%), or an absolute file URI outside the root."""
        absolute = Path(path).resolve()
        try:
            relative = absolute.relative_to(self.root)
        except ValueError:
            return absolute.as_uri(), None
        return quote(relative.as_posix()), "%SRCROOT%"

    def _fingerprint(self, issue: AnalysisIssue, rid: str, uri: str, seen: Dict[str, int]) -> str:
        """Hash of rule, file and flagged text (not the line number) + occurrence."""
        context = self._line_text(issue.file_path, issue.line)
        if not context:
            context = _DIGITS.sub("#", issue.message)
        origin = (issue.metadata or {}).get("expanded_from")
        if isinstance(origin, dict) and origin.get("file"):
            copied = self._line_text(str(origin["file"]), int(origin.get("line") or 0))
            context += f"|{origin.get('copybook')}:{copied or origin.get('line')}"
        digest = hashlib.sha256(f"{rid}|{uri}|{context}".encode("utf-8")).hexdigest()[:32]
        seen[digest] = seen.get(digest, 0) + 1
        return f"{digest}:{seen[digest]}"

    def _line_text(self, path: str, line: int) -> str:
        if path not in self._lines:
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
                self._lines[path] = text.splitlines()
            except OSError:
                self._lines[path] = []
        lines = self._lines[path]
        if 1 <= line <= len(lines):
            return _SPACES.sub(" ", lines[line - 1]).strip()
        return ""


# ----------------------------------------------------------------- rules


def _rule_id(issue: AnalysisIssue) -> str:
    return issue.rule_id or issue.issue_type.value


def _rule(rid: str, issues: List[AnalysisIssue]) -> Dict[str, Any]:
    """Reporting descriptor for one rule (its highest severity is the default)."""
    issue = issues[0]
    kind = issue.issue_type.value
    title = kind.replace("_", " ").capitalize().replace("Cobol ", "COBOL ", 1)
    security = bool(_SECURITY_WORDS.search(kind))
    tags = ["security" if security else "maintainability"]
    if kind.startswith("COBOL_"):
        tags.append("cobol")
    for other in issues:
        tags += [tag for tag in _cwe_tags(other) if tag not in tags]
    suggestions = ((i.suggestion or "").strip() for i in issues)
    suggestion = next((text for text in suggestions if text), "")
    help_uri = COBOL_HELP_URI if kind.startswith("COBOL_") else RULES_HELP_URI
    help_text = suggestion or f"See {help_uri} for this rule."
    severity = min((i.severity.value for i in issues), key=lambda s: _RANK.get(s, 4))
    properties: Dict[str, Any] = {
        "tags": tags[:MAX_TAGS],
        "precision": _precision(issue.confidence),
        "problem.severity": PROBLEM_SEVERITY.get(severity, "warning"),
    }
    if security:
        properties["security-severity"] = SECURITY_SEVERITY.get(severity, "5.5")
    return {
        "id": rid,
        "name": "".join(part.capitalize() for part in kind.split("_")),
        "shortDescription": {"text": title},
        "fullDescription": {"text": f"{title} ({rid}), reported by HefestoAI."},
        "help": {
            "text": help_text,
            "markdown": f"**{title}** (`{rid}`)\n\n{help_text}\n\n[Rule documentation]({help_uri})",
        },
        "helpUri": help_uri,
        "defaultConfiguration": {"level": LEVELS.get(severity, "warning")},
        "properties": properties,
    }


def _cwe_tags(issue: AnalysisIssue) -> List[str]:
    cwe = (issue.metadata or {}).get("cwe")
    if not isinstance(cwe, str):
        return []
    return [f"external/cwe/cwe-{n}" for n in _CWE.findall(cwe)]


def _precision(confidence: Optional[float]) -> str:
    if confidence is None:
        return "medium"
    if confidence >= 0.9:
        return "very-high"
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


# ----------------------------------------------------------------- helpers


def _version() -> str:
    try:
        from hefesto.__version__ import __version__

        return str(__version__)
    except Exception:  # pragma: no cover - version lookup must never fail SARIF
        return "0.0.0"


def _gzip_size(log: Dict[str, Any]) -> int:
    return len(gzip.compress(json.dumps(log).encode("utf-8")))


def _default_root() -> Path:
    """Git top level of the current directory, else $GITHUB_WORKSPACE, else the cwd."""
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    workspace = os.environ.get("GITHUB_WORKSPACE")
    return Path(workspace).resolve() if workspace else here
