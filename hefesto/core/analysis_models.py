"""
Analysis Data Models for Hefesto Analyze Command

Data structures for code analysis results, issues, and reports.
v4.4.0: Added enterprise fields (engine, rule_id, confidence, source)
        and DevOps issue types for Ola 1 languages.

Copyright 2025 Narapa LLC, Miami, Florida
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


class AnalysisIssueSeverity(str, Enum):
    """Analysis issue severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnalysisIssueType(str, Enum):
    """Types of analysis issues."""

    # Complexity
    HIGH_COMPLEXITY = "HIGH_COMPLEXITY"
    VERY_HIGH_COMPLEXITY = "VERY_HIGH_COMPLEXITY"

    # Code Smells
    LONG_FUNCTION = "LONG_FUNCTION"
    LONG_PARAMETER_LIST = "LONG_PARAMETER_LIST"
    DEEP_NESTING = "DEEP_NESTING"
    DUPLICATE_CODE = "DUPLICATE_CODE"
    DEAD_CODE = "DEAD_CODE"
    MAGIC_NUMBER = "MAGIC_NUMBER"
    GOD_CLASS = "GOD_CLASS"
    INCOMPLETE_TODO = "INCOMPLETE_TODO"

    # Security
    HARDCODED_SECRET = "HARDCODED_SECRET"
    SQL_INJECTION_RISK = "SQL_INJECTION_RISK"
    EVAL_USAGE = "EVAL_USAGE"
    PICKLE_USAGE = "PICKLE_USAGE"
    ASSERT_IN_PRODUCTION = "ASSERT_IN_PRODUCTION"
    BARE_EXCEPT = "BARE_EXCEPT"

    # Best Practices
    MISSING_DOCSTRING = "MISSING_DOCSTRING"
    POOR_NAMING = "POOR_NAMING"
    STYLE_VIOLATION = "STYLE_VIOLATION"

    # YAML Issues (v4.4.0)
    YAML_SYNTAX_ERROR = "YAML_SYNTAX_ERROR"
    YAML_DUPLICATE_KEY = "YAML_DUPLICATE_KEY"
    YAML_INDENTATION = "YAML_INDENTATION"
    YAML_SECRET_EXPOSURE = "YAML_SECRET_EXPOSURE"
    YAML_UNSAFE_COMMAND = "YAML_UNSAFE_COMMAND"

    # Terraform/HCL Issues (v4.4.0)
    TF_OPEN_SECURITY_GROUP = "TF_OPEN_SECURITY_GROUP"
    TF_HARDCODED_SECRET = "TF_HARDCODED_SECRET"
    TF_MISSING_ENCRYPTION = "TF_MISSING_ENCRYPTION"
    TF_PUBLIC_ACCESS = "TF_PUBLIC_ACCESS"
    TF_OVERLY_PERMISSIVE = "TF_OVERLY_PERMISSIVE"

    # Shell Issues (v4.4.0)
    SHELL_UNQUOTED_VARIABLE = "SHELL_UNQUOTED_VARIABLE"
    SHELL_COMMAND_INJECTION = "SHELL_COMMAND_INJECTION"
    SHELL_UNSAFE_TEMP = "SHELL_UNSAFE_TEMP"
    SHELL_DEPRECATED_SYNTAX = "SHELL_DEPRECATED_SYNTAX"
    SHELL_UNSAFE_COMMAND = "SHELL_UNSAFE_COMMAND"
    SHELL_MISSING_SAFETY = "SHELL_MISSING_SAFETY"
    # Dockerfile Security
    DOCKERFILE_INSECURE_BASE_IMAGE = "DOCKERFILE_INSECURE_BASE_IMAGE"
    DOCKERFILE_LATEST_TAG = "DOCKERFILE_LATEST_TAG"
    DOCKERFILE_MISSING_USER = "DOCKERFILE_MISSING_USER"
    DOCKERFILE_PRIVILEGE_ESCALATION = "DOCKERFILE_PRIVILEGE_ESCALATION"
    DOCKERFILE_SECRET_EXPOSURE = "DOCKERFILE_SECRET_EXPOSURE"
    DOCKERFILE_WEAK_PERMISSIONS = "DOCKERFILE_WEAK_PERMISSIONS"

    # Dockerfile Issues (v4.4.0)
    DOCKER_LATEST_TAG = "DOCKER_LATEST_TAG"
    DOCKER_ROOT_USER = "DOCKER_ROOT_USER"
    DOCKER_APT_CLEANUP = "DOCKER_APT_CLEANUP"
    DOCKER_CURL_BASH = "DOCKER_CURL_BASH"
    DOCKER_SECRET_IN_ENV = "DOCKER_SECRET_IN_ENV"

    # SQL Issues (v4.4.0)
    SQL_SYNTAX_ERROR = "SQL_SYNTAX_ERROR"
    SQL_DROP_WITHOUT_WHERE = "SQL_DROP_WITHOUT_WHERE"
    SQL_SELECT_STAR = "SQL_SELECT_STAR"
    SQL_MISSING_INDEX_HINT = "SQL_MISSING_INDEX_HINT"

    # Generic/External Provider
    EXTERNAL_FINDING = "EXTERNAL_FINDING"


@dataclass
class AnalysisIssue:
    """
    Represents a single code analysis issue.

    v4.4.0 Enterprise fields:
    - engine: Source of the finding (internal:<analyzer> or provider:<name>)
    - rule_id: External rule ID (SC2086, DL3000, etc.)
    - confidence: Detection confidence (0.0-1.0)
    - source: Code context (code, string_literal, template_literal, comment)
    """

    file_path: str
    line: int
    column: int
    issue_type: AnalysisIssueType
    severity: AnalysisIssueSeverity
    message: str
    function_name: Optional[str] = None
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Enterprise fields (v4.4.0)
    engine: str = "internal"
    rule_id: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[Literal["code", "string_literal", "template_literal", "comment"]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "file": self.file_path,
            "line": self.line,
            "column": self.column,
            "type": self.issue_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "function": self.function_name,
            "suggestion": self.suggestion,
            "code_snippet": self.code_snippet,
            "metadata": self.metadata,
            "engine": self.engine,
        }
        if self.rule_id:
            result["rule_id"] = self.rule_id
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.source:
            result["source"] = self.source
        return result


@dataclass
class ProviderResult:
    """
    Result from an external provider execution.

    Provides traceability and error handling for enterprise deployments.
    """

    provider_name: str
    provider_version: str
    issues: List[AnalysisIssue]
    duration_ms: float
    success: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider_name,
            "version": self.provider_version,
            "issues_count": len(self.issues),
            "duration_ms": self.duration_ms,
            "success": self.success,
            "errors": self.errors,
        }


@dataclass
class FileAnalysisResult:
    """Analysis results for a single file."""

    file_path: str
    issues: List[AnalysisIssue]
    lines_of_code: int
    analysis_duration_ms: float
    language: Optional[str] = None
    provider_results: List[ProviderResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "file": self.file_path,
            "issues": [issue.to_dict() for issue in self.issues],
            "loc": self.lines_of_code,
            "duration_ms": self.analysis_duration_ms,
        }
        if self.language:
            result["language"] = self.language
        if self.provider_results:
            result["providers"] = [pr.to_dict() for pr in self.provider_results]
        return result


@dataclass
class AnalysisSummary:
    """Summary statistics for analysis run."""

    files_analyzed: int
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    total_loc: int
    duration_seconds: float
    providers_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "files_analyzed": self.files_analyzed,
            "total_issues": self.total_issues,
            "critical": self.critical_issues,
            "high": self.high_issues,
            "medium": self.medium_issues,
            "low": self.low_issues,
            "total_loc": self.total_loc,
            "duration_seconds": self.duration_seconds,
        }
        if self.providers_used:
            result["providers_used"] = self.providers_used
        return result


@dataclass
class AnalysisReport:
    """Complete analysis report."""

    summary: AnalysisSummary
    file_results: List[FileAnalysisResult]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_all_issues(self) -> List[AnalysisIssue]:
        """Get all issues across all files."""
        issues = []
        for file_result in self.file_results:
            issues.extend(file_result.issues)
        return issues

    def get_issues_by_severity(self, severity: AnalysisIssueSeverity) -> List[AnalysisIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.get_all_issues() if issue.severity == severity]

    def get_issues_by_engine(self, engine: str) -> List[AnalysisIssue]:
        """Get all issues from a specific engine/provider."""
        return [issue for issue in self.get_all_issues() if issue.engine == engine]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": self.summary.to_dict(),
            "files": [file_result.to_dict() for file_result in self.file_results],
            "timestamp": self.timestamp.isoformat(),
        }


__all__ = [
    "AnalysisIssueSeverity",
    "AnalysisIssueType",
    "AnalysisIssue",
    "ProviderResult",
    "FileAnalysisResult",
    "AnalysisSummary",
    "AnalysisReport",
]
