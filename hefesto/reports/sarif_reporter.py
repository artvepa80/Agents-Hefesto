"""
SARIF 2.1.0 reporter (``hefesto analyze --output sarif``).

Produces a SARIF log that GitHub code scanning accepts
(``github/codeql-action/upload-sarif``), for every analyzer, not only COBOL:

* one ``reportingDescriptor`` per rule (``rule_id`` when the analyzer sets
  one, such as ``COBOL004`` or ``SC2086``; otherwise the issue type, such as
  ``HARDCODED_SECRET``) with name, short/full description, help text and
  markdown, a help URI, a default level and properties: tags (``security``
  or ``maintainability``, plus ``external/cwe/cwe-N`` from
  ``hefesto.reports.cwe_map`` or from ``metadata["cwe"]``, no zero-padding),
  ``precision``, ``problem.severity`` and, for security rules,
  ``security-severity`` (CRITICAL 9.5, HIGH 8.0, MEDIUM 5.5, LOW 3.0);
* when any rule has a CWE, ``run.taxonomies`` holds one CWE tool component
  (MITRE, the pinned list version, only the ids used in the run) and each
  such rule has ``relationships`` pointing at it;
* results with ``level`` (CRITICAL/HIGH -> error, MEDIUM -> warning,
  LOW -> note), the message, a repo-relative URI (``uriBaseId`` %SRCROOT%),
  the start line, ``partialFingerprints`` that survive line shifts (rule,
  file and the text of the flagged line, not its number) and, for COBOL
  findings that come from a copybook, a related location in the copybook;
* GitHub upload limits are respected: at most 25,000 results per run
  (highest severity kept), 1,000 related locations per result, 20 tags per
  rule, and the serialized log is kept under 10 MB once gzipped. What was
  dropped is reported in ``invocations[0].toolExecutionNotifications``
  (level ``warning``), as are files left out as vendored JavaScript (level
  ``note``), files that could not be analyzed (level ``error``) and files
  decoded with the latin-1 fallback (level ``warning``), with the file as
  location.

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
from hefesto.reports.cwe_map import CWE_NAMES, CWE_VERSION, links_for

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
        self._not_analyzed: List[Dict[str, Any]] = []
        self._decoded_with_fallback: List[Dict[str, Any]] = []

    def generate(self, report: AnalysisReport) -> str:
        """SARIF log as a JSON string."""
        return json.dumps(self.generate_dict(report), indent=2, ensure_ascii=False)

    def generate_dict(self, report: AnalysisReport) -> Dict[str, Any]:
        meta = getattr(report, "meta", None) or {}
        self._not_analyzed = list(meta.get("not_analyzed") or [])
        self._decoded_with_fallback = list(meta.get("decoded_with_fallback") or [])
        issues = sorted(
            report.get_all_issues(),
            key=lambda i: (_RANK.get(i.severity.value, 4), i.file_path, i.line, _rule_id(i)),
        )
        notes: List[str] = []
        info = _info_notes(report)
        if len(issues) > self.max_results:
            notes.append(
                f"{len(issues) - self.max_results} lower-severity results were dropped to stay "
                f"within the {self.max_results:,}-results limit of GitHub code scanning."
            )
            issues = issues[: self.max_results]
        log = self._log(issues, notes, info)
        while issues and _gzip_size(log) > MAX_GZIP_BYTES:
            keep = len(issues) * 3 // 4
            notes.append(
                f"{len(issues) - keep} lower-severity results were dropped to keep the "
                "gzipped SARIF under 10 MB."
            )
            issues = issues[:keep]
            log = self._log(issues, notes, info)
        return log

    # ------------------------------------------------------------- building

    def _log(
        self, issues: List[AnalysisIssue], notes: List[str], info: List[str]
    ) -> Dict[str, Any]:
        by_rule: Dict[str, List[AnalysisIssue]] = {}
        for issue in issues:
            by_rule.setdefault(_rule_id(issue), []).append(issue)
        order = list(by_rule)
        index = {rid: n for n, rid in enumerate(order)}
        seen: Dict[str, int] = {}
        results = [self._result(issue, index, seen) for issue in self._stable_order(issues)]
        invocation: Dict[str, Any] = {"executionSuccessful": True}
        notifications = self._not_analyzed_notifications()
        notifications += self._fallback_notifications()
        notifications += [{"level": "warning", "message": {"text": text}} for text in notes]
        notifications += [{"level": "note", "message": {"text": text}} for text in info]
        if notifications:
            invocation["toolExecutionNotifications"] = notifications
        rules = [_rule(rid, by_rule[rid]) for rid in order]
        run: Dict[str, Any] = {
            "tool": {
                "driver": {
                    "name": "HefestoAI",
                    "informationUri": INFORMATION_URI,
                    "version": _version(),
                    "semanticVersion": _version(),
                    "rules": rules,
                }
            },
            "invocations": [invocation],
            "columnKind": "utf16CodeUnits",
        }
        taxonomy = _cwe_taxonomy(rules)
        if taxonomy:
            run["taxonomies"] = [taxonomy]
        run["results"] = results
        return {
            "$schema": SARIF_SCHEMA,
            "version": SARIF_VERSION,
            "runs": [run],
        }

    def _not_analyzed_notifications(self) -> List[Dict[str, Any]]:
        """One ``error`` notification per found file that could not be analyzed."""
        from hefesto.core.analyzer_engine import not_analyzed_message

        return [
            self._file_notification("error", not_analyzed_message(e), e) for e in self._not_analyzed
        ]

    def _fallback_notifications(self) -> List[Dict[str, Any]]:
        """One ``warning`` per file that was analyzed after a fallback decode."""
        from hefesto.core.analyzer_engine import decoded_with_fallback_message

        return [
            self._file_notification("warning", decoded_with_fallback_message(e), e)
            for e in self._decoded_with_fallback
        ]

    def _file_notification(self, level: str, text: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        uri, base = self._uri(str(entry.get("path", "")))
        location: Dict[str, Any] = {"uri": uri}
        if base:
            location["uriBaseId"] = base
        return {
            "level": level,
            "message": {"text": text},
            "locations": [{"physicalLocation": {"artifactLocation": location}}],
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
    links = _cwe_links(issues)
    _append_cwe_tags(tags, links)
    suggestions = ((i.suggestion or "").strip() for i in issues)
    suggestion = next((text for text in suggestions if text), "")
    help_uri = COBOL_HELP_URI if kind.startswith("COBOL_") else RULES_HELP_URI
    help_text = suggestion or f"See {help_uri} for this rule."
    severity = min((i.severity.value for i in issues), key=lambda s: _RANK.get(s, 4))
    properties: Dict[str, Any] = {
        "tags": tags[:MAX_TAGS],
        "precision": _rule_precision(issues),
        "problem.severity": PROBLEM_SEVERITY.get(severity, "warning"),
    }
    if security:
        properties["security-severity"] = SECURITY_SEVERITY.get(severity, "5.5")
    rule: Dict[str, Any] = {
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
    _attach_cwe_relationships(rule, links)
    return rule


def _append_cwe_tags(tags: List[str], links: List[Tuple[str, str]]) -> None:
    for digits, _kind in links:
        tag = f"external/cwe/cwe-{digits}"
        if tag not in tags:
            tags.append(tag)


def _attach_cwe_relationships(rule: Dict[str, Any], links: List[Tuple[str, str]]) -> None:
    if not links:
        return
    rule["relationships"] = [
        {
            "target": {"id": digits, "toolComponent": {"name": "CWE", "index": 0}},
            "kinds": [kind],
        }
        for digits, kind in links
    ]


def _cwe_for_issue(issue: AnalysisIssue) -> List[Tuple[str, str]]:
    """(digit string, relationship kind). Metadata overrides the registry.

    Digits are not zero-padded. A metadata value is copied as written, so
    an existing ``CWE-20`` tag stays ``cwe-20``.
    """
    metadata = issue.metadata or {}
    if "cwe" in metadata:
        raw = metadata.get("cwe")
        if not isinstance(raw, str):
            return []
        return [(digits, "relevant") for digits in _CWE.findall(raw)]
    return [(str(row.cwe_id), row.kind) for row in links_for(issue.issue_type.value)]


def _cwe_links(issues: List[AnalysisIssue]) -> List[Tuple[str, str]]:
    """Unique CWE links for one rule, numeric id order (first kind wins)."""
    found: Dict[str, str] = {}
    for issue in issues:
        for digits, kind in _cwe_for_issue(issue):
            found.setdefault(digits, kind)
    return [(digits, found[digits]) for digits in sorted(found, key=lambda d: (int(d), d))]


def _rule_precision(issues: List[AnalysisIssue]) -> str:
    """Confidence-derived precision, unless the mapping forces one.

    PICKLE_USAGE forces ``low``: the detector flags the import only.
    """
    precision = _precision(issues[0].confidence)
    for issue in issues:
        for row in links_for(issue.issue_type.value):
            if row.precision:
                return row.precision
    return precision


def _cwe_taxonomy(rules: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """CWE tool component listing only the ids referenced by ``rules``."""
    seen = set()
    ids: List[str] = []
    for rule in rules:
        for relationship in rule.get("relationships") or []:
            digits = str(relationship["target"]["id"])
            if digits not in seen:
                seen.add(digits)
                ids.append(digits)
    if not ids:
        return None
    ids.sort(key=lambda digits: (int(digits), digits))
    return {
        "name": "CWE",
        "organization": "MITRE",
        "version": CWE_VERSION,
        "informationUri": "https://cwe.mitre.org/data/downloads.html",
        "taxa": [_taxon(digits) for digits in ids],
    }


def _taxon(digits: str) -> Dict[str, Any]:
    name = CWE_NAMES.get(int(digits), f"CWE-{digits}")
    return {
        "id": digits,
        "name": name,
        "shortDescription": {"text": name},
        "helpUri": f"https://cwe.mitre.org/data/definitions/{digits}.html",
    }


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


def _info_notes(report: AnalysisReport) -> List[str]:
    """Run-level notes that are not findings (``level: note``)."""
    vendored = (getattr(report, "meta", None) or {}).get("vendored_skipped") or {}
    if not vendored.get("count"):
        return []
    from hefesto.core.analyzer_engine import vendored_skip_message

    return [vendored_skip_message(vendored["count"])]
