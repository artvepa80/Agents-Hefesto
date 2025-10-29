"""
Hefesto Core Analysis Engine.

This module contains the core orchestration logic for code analysis.
"""

# Import core models
# Enums; Validation Models; Code Issue Models; Feedback Models
# Budget Models; LLM Event Models; Semantic Models (Pro)
# CICD Models (Pro); License Models; Utility Functions
from hefesto.core.models import (
    BudgetStatus,
    BudgetStatusInfo,
    BudgetSummary,
    CodeEmbedding,
    CodeIssue,
    DeploymentFeedback,
    FeedbackMetrics,
    IssueCategory,
    IssueSeverity,
    LicenseInfo,
    LLMEvent,
    LLMModel,
    RefactoringRequest,
    RefactoringResponse,
    SimilarityResult,
    SuggestionAction,
    SuggestionFeedback,
    SuggestionValidationResult,
    TestFeedback,
    TokenUsage,
    ValidationResult,
    ValidationStatus,
    generate_deployment_id,
    generate_event_id,
    generate_suggestion_id,
)

# Try to import analyzer engine if it exists
try:
    from hefesto.core.analyzer_engine import AnalyzerEngine  # noqa: F401

    _has_analyzer = True
except ImportError:
    _has_analyzer = False

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

# Add AnalyzerEngine if available
if _has_analyzer:
    __all__.append("AnalyzerEngine")
