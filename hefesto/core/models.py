"""
HEFESTO Core Data Models

Purpose: Centralized data models and types for the Hefesto AI-powered code quality system.
Location: core/models.py

This module provides all core data structures used throughout the Hefesto system:
- Code validation models
- Suggestion feedback models
- Budget tracking models
- LLM event models
- Issue classification models
- Result types and enums

All models use dataclasses for type safety and are designed for JSON serialization
for use with the API, BigQuery, and other integrations.

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# ============================================================================
# ENUMS - Classification Types
# ============================================================================


class IssueCategory(str, Enum):
    """
    Safe issue categories that HEFESTO can automatically address.

    These categories represent issues that are safe for automated refactoring
    without risk of breaking functionality or introducing security problems.
    """

    # Code quality issues
    CODE_COMPLEXITY = "code_complexity"
    LONG_FUNCTION = "long_function"
    DUPLICATE_CODE = "duplicate_code"
    UNUSED_VARIABLE = "unused_variable"
    UNUSED_IMPORT = "unused_import"

    # Security issues (safe to auto-fix)
    HARDCODED_TEMP_PATH = "hardcoded_temp_path"
    WEAK_CRYPTO = "weak_crypto"
    INSECURE_HASH = "insecure_hash"

    # Performance issues
    INEFFICIENT_LOOP = "inefficient_loop"
    MEMORY_LEAK = "memory_leak"
    RESOURCE_LEAK = "resource_leak"

    # Best practices
    MISSING_DOCSTRING = "missing_docstring"
    MISSING_TYPE_HINTS = "missing_type_hints"
    INCONSISTENT_NAMING = "inconsistent_naming"
    MISSING_ERROR_HANDLING = "missing_error_handling"

    # Sports analytics specific
    MISSING_DATA_VALIDATION = "missing_data_validation"
    MISSING_METRIC_LOGGING = "missing_metric_logging"
    INEFFICIENT_DATA_PROCESSING = "inefficient_data_processing"


class IssueSeverity(str, Enum):
    """Issue severity levels matching industry standards."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ValidationStatus(str, Enum):
    """Validation result status."""

    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"
    ERROR = "error"


class BudgetStatus(str, Enum):
    """Budget status levels for alerts."""

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EXCEEDED = "EXCEEDED"
    UNKNOWN = "UNKNOWN"


class LLMModel(str, Enum):
    """Supported LLM models."""

    GEMINI_2_FLASH_EXP = "gemini-2.0-flash-exp"
    GEMINI_2_FLASH = "gemini-2.0-flash"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_FLASH_8B = "gemini-1.5-flash-8b"
    GEMINI_1_5_PRO = "gemini-1.5-pro"


class SuggestionAction(str, Enum):
    """User actions on suggestions."""

    SHOWN = "shown"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"
    FAILED = "failed"


# ============================================================================
# VALIDATION MODELS
# ============================================================================


@dataclass
class ValidationResult:
    """
    Result of code validation checks.

    Contains detailed validation information including syntax,
    security, and structural checks.
    """

    valid: bool
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "valid": self.valid,
            "error_message": self.error_message,
            "details": self.details,
        }


@dataclass
class SuggestionValidationResult:
    """
    Comprehensive validation result for LLM suggestions.

    Attributes:
        valid: Overall validation status
        confidence: Confidence score (0-1)
        issues: List of validation issues found
        safe_to_apply: Whether suggestion can be auto-applied
        warnings: Non-critical warnings
        validation_passed: Whether all checks passed
        similarity_score: Code similarity to original (0-1, syntactic)
        semantic_similarity: Semantic code similarity (0-1, ML-based, Pro only)
        is_duplicate: Whether suggestion is semantically duplicate (>0.85)
        details: Detailed validation breakdown
    """

    valid: bool
    confidence: float
    issues: List[str]
    safe_to_apply: bool
    warnings: List[str] = field(default_factory=list)
    validation_passed: bool = True
    similarity_score: float = 0.0
    semantic_similarity: Optional[float] = None
    is_duplicate: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "valid": self.valid,
            "confidence": self.confidence,
            "issues": self.issues,
            "safe_to_apply": self.safe_to_apply,
            "warnings": self.warnings,
            "validation_passed": self.validation_passed,
            "similarity_score": self.similarity_score,
            "semantic_similarity": self.semantic_similarity,
            "is_duplicate": self.is_duplicate,
            "details": self.details,
        }


# ============================================================================
# CODE ISSUE MODELS
# ============================================================================


@dataclass
class CodeIssue:
    """
    Represents a code quality or security issue.

    Used to pass issue information to the refactoring engine.
    """

    type: str
    severity: IssueSeverity
    line: int
    description: str
    file_path: Optional[str] = None
    column: Optional[int] = None
    suggested_fix: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "severity": self.severity.value,
            "line": self.line,
            "description": self.description,
            "file_path": self.file_path,
            "column": self.column,
            "suggested_fix": self.suggested_fix,
            "metadata": self.metadata,
        }


@dataclass
class RefactoringRequest:
    """
    Request for code refactoring.

    Contains the code to refactor and the issue to address.
    """

    code: str
    issue: CodeIssue
    file_path: Optional[str] = None
    context: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "issue": self.issue.to_dict(),
            "file_path": self.file_path,
            "context": self.context,
            "metadata": self.metadata,
        }


@dataclass
class RefactoringResponse:
    """
    Response from refactoring engine.

    Contains the suggested code and validation results.
    """

    original_code: str
    suggested_code: str
    validation_result: SuggestionValidationResult
    suggestion_id: str
    issue: CodeIssue
    explanation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "original_code": self.original_code,
            "suggested_code": self.suggested_code,
            "validation_result": self.validation_result.to_dict(),
            "suggestion_id": self.suggestion_id,
            "issue": self.issue.to_dict(),
            "explanation": self.explanation,
            "metadata": self.metadata,
        }


# ============================================================================
# FEEDBACK MODELS
# ============================================================================


@dataclass
class SuggestionFeedback:
    """
    Feedback data for a code refactoring suggestion.

    Used to track user acceptance and results in the feedback loop.

    Attributes:
        suggestion_id: Unique identifier (SUG-XXXXXXXXXXXX format)
        llm_event_id: Foreign key to llm_events table
        file_path: File where issue was detected
        issue_type: Type of issue (security, performance, etc.)
        severity: Issue severity level
        shown_to_user: Whether suggestion was displayed
        user_accepted: User's decision (None = pending)
        applied_successfully: Whether application succeeded
        time_to_apply_seconds: Time taken to apply
        ci_passed: CI pipeline result
        tests_passed: Test suite result
        coverage_improved: Code coverage change
        user_comment: Free-text feedback
        rejection_reason: Why suggestion was rejected
        confidence_score: LLM confidence (0.0-1.0)
        validation_passed: Validation result
        similarity_score: Code similarity (0.0-1.0)
        timestamp: When feedback was recorded
    """

    suggestion_id: str
    llm_event_id: Optional[str] = None
    file_path: Optional[str] = None
    issue_type: Optional[str] = None
    severity: Optional[str] = None
    shown_to_user: bool = True
    user_accepted: Optional[bool] = None
    applied_successfully: Optional[bool] = None
    time_to_apply_seconds: Optional[int] = None
    ci_passed: Optional[bool] = None
    tests_passed: Optional[bool] = None
    coverage_improved: Optional[bool] = None
    user_comment: Optional[str] = None
    rejection_reason: Optional[str] = None
    confidence_score: Optional[float] = None
    validation_passed: Optional[bool] = None
    similarity_score: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "suggestion_id": self.suggestion_id,
            "llm_event_id": self.llm_event_id,
            "file_path": self.file_path,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "shown_to_user": self.shown_to_user,
            "user_accepted": self.user_accepted,
            "applied_successfully": self.applied_successfully,
            "time_to_apply_seconds": self.time_to_apply_seconds,
            "ci_passed": self.ci_passed,
            "tests_passed": self.tests_passed,
            "coverage_improved": self.coverage_improved,
            "user_comment": self.user_comment,
            "rejection_reason": self.rejection_reason,
            "confidence_score": self.confidence_score,
            "validation_passed": self.validation_passed,
            "similarity_score": self.similarity_score,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class FeedbackMetrics:
    """
    Aggregated metrics from feedback loop.

    Used for analytics and reporting.
    """

    total: int
    accepted: int
    rejected: int
    pending: int
    acceptance_rate: float
    avg_confidence: float
    avg_similarity: float
    avg_time_to_apply: float
    period: str
    filters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "pending": self.pending,
            "acceptance_rate": self.acceptance_rate,
            "avg_confidence": self.avg_confidence,
            "avg_similarity": self.avg_similarity,
            "avg_time_to_apply": self.avg_time_to_apply,
            "period": self.period,
            "filters": self.filters,
        }


# ============================================================================
# BUDGET TRACKING MODELS
# ============================================================================


@dataclass
class TokenUsage:
    """
    Token usage and cost for a single LLM request.

    Attributes:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        total_tokens: Total tokens (input + output)
        estimated_cost_usd: Estimated cost in USD
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


@dataclass
class BudgetSummary:
    """
    Budget usage summary for a time period.

    Contains aggregated usage statistics and budget status.
    """

    period: str
    start_time: str
    request_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    active_days: int
    estimated_cost_usd: float
    daily_limit_usd: Optional[float] = None
    monthly_limit_usd: Optional[float] = None
    budget_limit_usd: Optional[float] = None
    budget_remaining_usd: Optional[float] = None
    budget_utilization_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period": self.period,
            "start_time": self.start_time,
            "request_count": self.request_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "active_days": self.active_days,
            "estimated_cost_usd": self.estimated_cost_usd,
            "daily_limit_usd": self.daily_limit_usd,
            "monthly_limit_usd": self.monthly_limit_usd,
            "budget_limit_usd": self.budget_limit_usd,
            "budget_remaining_usd": self.budget_remaining_usd,
            "budget_utilization_pct": self.budget_utilization_pct,
        }


@dataclass
class BudgetStatusInfo:
    """
    Budget status with alert information.

    Used for monitoring and alerting on budget thresholds.
    """

    level: BudgetStatus
    message: str
    utilization_pct: float
    cost_usd: float
    limit_usd: Optional[float] = None
    remaining_usd: Optional[float] = None
    usage_summary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "message": self.message,
            "utilization_pct": self.utilization_pct,
            "cost_usd": self.cost_usd,
            "limit_usd": self.limit_usd,
            "remaining_usd": self.remaining_usd,
            "usage_summary": self.usage_summary,
        }


# ============================================================================
# LLM EVENT MODELS
# ============================================================================


@dataclass
class LLMEvent:
    """
    Record of an LLM API call.

    Used for tracking, auditing, and budget monitoring.
    """

    event_id: str
    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    success: bool
    request_type: str
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "request_type": self.request_type,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


# ============================================================================
# SEMANTIC ANALYSIS MODELS (PRO FEATURE)
# ============================================================================


@dataclass
class CodeEmbedding:
    """
    Semantic embedding of a code snippet.

    Pro Feature: Requires commercial license.
    """

    code: str
    embedding: List[float]
    language: str = "python"
    model: str = "code-embeddings-v1"
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "embedding": self.embedding,
            "language": self.language,
            "model": self.model,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SimilarityResult:
    """
    Result of semantic similarity comparison.

    Pro Feature: Requires commercial license.
    """

    code1: str
    code2: str
    similarity_score: float
    is_duplicate: bool
    threshold: float
    method: str = "cosine"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code1": self.code1,
            "code2": self.code2,
            "similarity_score": self.similarity_score,
            "is_duplicate": self.is_duplicate,
            "threshold": self.threshold,
            "method": self.method,
        }


# ============================================================================
# CICD INTEGRATION MODELS (PRO FEATURE)
# ============================================================================


@dataclass
class DeploymentFeedback:
    """
    Feedback from deployment pipeline.

    Pro Feature: Tracks whether suggestions break deployments.
    """

    suggestion_id: str
    deployment_id: str
    environment: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    rollback_required: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "suggestion_id": self.suggestion_id,
            "deployment_id": self.deployment_id,
            "environment": self.environment,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "rollback_required": self.rollback_required,
            "metadata": self.metadata,
        }


@dataclass
class TestFeedback:
    """
    Feedback from test suite execution.

    Pro Feature: Tracks test results after applying suggestions.
    """

    suggestion_id: str
    test_run_id: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    coverage_before: Optional[float] = None
    coverage_after: Optional[float] = None
    duration_seconds: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "suggestion_id": self.suggestion_id,
            "test_run_id": self.test_run_id,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "coverage_before": self.coverage_before,
            "coverage_after": self.coverage_after,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================================
# LICENSE MODELS
# ============================================================================


@dataclass
class LicenseInfo:
    """
    License validation information.

    Contains details about the active license.
    """

    license_key: str
    tier: str
    valid: bool
    expires_at: Optional[datetime] = None
    features: List[str] = field(default_factory=list)
    limits: Dict[str, Any] = field(default_factory=dict)
    customer_email: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "license_key": self.license_key,
            "tier": self.tier,
            "valid": self.valid,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "features": self.features,
            "limits": self.limits,
            "customer_email": self.customer_email,
        }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def generate_suggestion_id() -> str:
    """
    Generate unique suggestion ID.

    Returns:
        Suggestion ID in format: SUG-XXXXXXXXXXXX
    """
    return f"SUG-{uuid.uuid4().hex[:12].upper()}"


def generate_event_id() -> str:
    """
    Generate unique event ID.

    Returns:
        Event ID in format: EVT-XXXXXXXXXXXX
    """
    return f"EVT-{uuid.uuid4().hex[:12].upper()}"


def generate_deployment_id() -> str:
    """
    Generate unique deployment ID.

    Returns:
        Deployment ID in format: DEP-XXXXXXXXXXXX
    """
    return f"DEP-{uuid.uuid4().hex[:12].upper()}"


# ============================================================================
# EXPORTS
# ============================================================================


__all__ = [
    # Enums
    "IssueCategory",
    "IssueSeverity",
    "ValidationStatus",
    "BudgetStatus",
    "LLMModel",
    "SuggestionAction",
    # Validation Models
    "ValidationResult",
    "SuggestionValidationResult",
    # Code Issue Models
    "CodeIssue",
    "RefactoringRequest",
    "RefactoringResponse",
    # Feedback Models
    "SuggestionFeedback",
    "FeedbackMetrics",
    # Budget Models
    "TokenUsage",
    "BudgetSummary",
    "BudgetStatusInfo",
    # LLM Event Models
    "LLMEvent",
    # Semantic Models (Pro)
    "CodeEmbedding",
    "SimilarityResult",
    # CICD Models (Pro)
    "DeploymentFeedback",
    "TestFeedback",
    # License Models
    "LicenseInfo",
    # Utility Functions
    "generate_suggestion_id",
    "generate_event_id",
    "generate_deployment_id",
]
