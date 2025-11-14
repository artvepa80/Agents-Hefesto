"""
HEFESTO v3.0 - LLM Provider Abstraction Layer

Purpose: Abstract base class for LLM providers to enable multi-provider support.
Location: llm/provider.py

This module defines the interface that all LLM providers must implement,
enabling HEFESTO to support multiple AI backends (Vertex AI, OpenAI, Claude, etc.)
with consistent behavior and safety guarantees.

Features:
- Abstract LLMProvider base class
- Standardized method signatures
- Type-safe interfaces
- Provider-agnostic error handling
- Consistent response formats

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

# Configure logging
logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    """Supported LLM provider types."""

    VERTEX_AI = "vertex_ai"
    OPENAI = "openai"
    CLAUDE = "claude"
    LOCAL = "local"


class SafetyLevel(str, Enum):
    """Safety filtering levels for LLM providers."""

    STRICT = "strict"
    MODERATE = "moderate"
    PERMISSIVE = "permissive"


@dataclass
class RefactorSuggestion:
    """
    Structured refactoring suggestion from LLM.

    Attributes:
        original_code: The original problematic code
        refactored_code: The proposed refactored code
        explanation: Natural language explanation of the changes
        confidence: Confidence score (0.0 to 1.0)
        safety_validated: Whether the suggestion passed safety validation
        issues_addressed: List of issue types addressed by this refactor
        estimated_impact: Estimated business impact (optional)
    """

    original_code: str
    refactored_code: str
    explanation: str
    confidence: float
    safety_validated: bool
    issues_addressed: List[str]
    estimated_impact: Optional[str] = None


@dataclass
class TestSuggestion:
    """
    Structured test generation suggestion from LLM.

    Attributes:
        function_signature: The function being tested
        test_code: Generated test code
        test_framework: Testing framework used (pytest, unittest, etc.)
        coverage_areas: Areas of functionality covered
        edge_cases: Edge cases tested
        confidence: Confidence score (0.0 to 1.0)
    """

    function_signature: str
    test_code: str
    test_framework: str
    coverage_areas: List[str]
    edge_cases: List[str]
    confidence: float


@dataclass
class IssueFinding:
    """
    Structured explanation of a code issue from LLM.

    Attributes:
        summary: Brief summary of the issue
        technical_details: Detailed technical explanation
        severity: Issue severity (CRITICAL, HIGH, MEDIUM, LOW)
        root_cause: Identified root cause
        consequences: Potential consequences if not fixed
        recommendations: Recommended actions
        sports_context: Sports analytics specific context (optional)
    """

    summary: str
    technical_details: str
    severity: str
    root_cause: str
    consequences: List[str]
    recommendations: List[str]
    sports_context: Optional[str] = None


@dataclass
class ProviderConfig:
    """
    Configuration for LLM provider initialization.

    Attributes:
        provider_type: Type of LLM provider
        project_id: Cloud project ID (for cloud providers)
        location: Cloud region/location
        model_name: Specific model to use
        temperature: Temperature for generation (0.0-1.0)
        max_tokens: Maximum tokens per response
        safety_level: Safety filtering level
        timeout_seconds: Request timeout in seconds
        retry_attempts: Number of retry attempts
        api_key: API key (for API-based providers)
        service_account_path: Path to service account JSON (for GCP)
    """

    provider_type: ProviderType
    project_id: Optional[str] = None
    location: Optional[str] = None
    model_name: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 512
    safety_level: SafetyLevel = SafetyLevel.STRICT
    timeout_seconds: int = 30
    retry_attempts: int = 3
    api_key: Optional[str] = None
    service_account_path: Optional[str] = None


class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.

    All LLM provider implementations must inherit from this class and implement
    the required methods. This ensures consistent behavior across different
    AI backends and enables easy provider switching.

    Enterprise Requirements:
    - All implementations MUST validate inputs before sending to LLM
    - All implementations MUST mask sensitive data using security.masking
    - All implementations MUST implement retry logic with exponential backoff
    - All implementations MUST log all interactions for audit purposes
    - All implementations MUST enforce token limits to prevent costs

    Sports Analytics Context:
    Providers should understand sports domain vocabulary and provide context-aware
    suggestions for football (soccer) analytics code. This includes:
    - Match prediction algorithms
    - Team performance metrics
    - Player statistics processing
    - Real-time sports data handling
    """

    def __init__(self, config: ProviderConfig):
        """
        Initialize the LLM provider with configuration.

        Args:
            config: Provider configuration object

        Raises:
            ValueError: If configuration is invalid
            ConnectionError: If provider initialization fails
        """
        self.config = config
        self.provider_type = config.provider_type
        self._initialized = False
        logger.info(f"Initializing {self.provider_type} provider")

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the provider connection and validate credentials.

        This method must be called before using any provider methods.
        It should validate credentials, test connectivity, and prepare
        the provider for requests.

        Returns:
            True if initialization successful, False otherwise

        Raises:
            ConnectionError: If unable to connect to provider
            ValueError: If credentials are invalid
        """
        pass

    @abstractmethod
    def suggest_refactor(self, code: str, issue: Dict[str, Any]) -> RefactorSuggestion:
        """
        Suggest code refactoring to fix identified issues.

        This method analyzes problematic code and suggests safe refactorings
        that address the identified issues while maintaining functionality.

        Args:
            code: The problematic code to refactor
            issue: Dictionary containing issue details:
                - type: Issue type (e.g., "sql_injection", "hardcoded_secret")
                - severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
                - line: Line number where issue occurs
                - description: Human-readable description
                - file_path: Path to file containing the issue

        Returns:
            RefactorSuggestion with proposed changes and explanation

        Raises:
            ValueError: If code or issue data is invalid
            RuntimeError: If provider request fails after retries

        Example:
            >>> provider = VertexProvider(config)
            >>> provider.initialize()
            >>> issue = {
            ...     "type": "sql_injection",
            ...     "severity": "CRITICAL",
            ...     "line": 42,
            ...     "description": "Unsafe SQL concatenation",
            ...     "file_path": "api/users.py"
            ... }
            >>> suggestion = provider.suggest_refactor(
            ...     'query = "SELECT * FROM users WHERE id=" + user_id',
            ...     issue
            ... )
            >>> print(suggestion.refactored_code)
        """
        pass

    @abstractmethod
    def generate_tests(self, func: str) -> TestSuggestion:
        """
        Generate comprehensive tests for a given function.

        This method analyzes a function signature and implementation,
        then generates appropriate unit tests covering normal cases,
        edge cases, and error conditions.

        Args:
            func: Complete function definition including signature and body

        Returns:
            TestSuggestion with generated test code and coverage details

        Raises:
            ValueError: If function code is invalid or unparseable
            RuntimeError: If provider request fails after retries

        Example:
            >>> provider = VertexProvider(config)
            >>> provider.initialize()
            >>> function_code = '''
            ... def calculate_team_form(matches: List[str]) -> float:
            ...     wins = matches.count('W')
            ...     return wins / len(matches)
            ... '''
            >>> tests = provider.generate_tests(function_code)
            >>> print(tests.test_code)
        """
        pass

    @abstractmethod
    def explain_finding(self, issue: Dict[str, Any]) -> IssueFinding:
        """
        Provide detailed explanation of a code issue or finding.

        This method generates natural language explanations of code issues,
        including technical details, business impact, and remediation guidance.

        Args:
            issue: Dictionary containing issue details:
                - type: Issue type (e.g., "memory_leak", "hardcoded_secret")
                - severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
                - line: Line number where issue occurs
                - description: Brief description
                - file_path: Path to file containing the issue
                - code_context: Surrounding code for context (optional)

        Returns:
            IssueFinding with detailed explanation and recommendations

        Raises:
            ValueError: If issue data is invalid
            RuntimeError: If provider request fails after retries

        Example:
            >>> provider = VertexProvider(config)
            >>> provider.initialize()
            >>> issue = {
            ...     "type": "hardcoded_secret",
            ...     "severity": "CRITICAL",
            ...     "line": 15,
            ...     "description": "API key in source code",
            ...     "file_path": "config/settings.py",
            ...     "code_context": 'API_KEY = "sk-1234567890"'
            ... }
            >>> finding = provider.explain_finding(issue)
            >>> print(finding.summary)
            >>> print(finding.recommendations)
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the provider.

        This method tests the provider's availability and returns diagnostic
        information about its status, latency, and any errors.

        Returns:
            Dictionary containing:
                - status: "healthy", "degraded", or "unhealthy"
                - latency_ms: Response latency in milliseconds
                - provider_type: Provider type identifier
                - model_name: Model being used
                - error: Error message if unhealthy (optional)

        Example:
            >>> provider = VertexProvider(config)
            >>> provider.initialize()
            >>> health = provider.health_check()
            >>> assert health["status"] == "healthy"
            >>> assert health["latency_ms"] < 1000
        """
        pass

    def validate_config(self) -> bool:
        """
        Validate provider configuration.

        Checks that all required configuration parameters are present
        and valid for this provider type.

        Returns:
            True if configuration is valid, False otherwise
        """
        # Basic validation
        if self.config.temperature < 0 or self.config.temperature > 1:
            logger.error(f"Invalid temperature: {self.config.temperature}")
            return False

        if self.config.max_tokens <= 0:
            logger.error(f"Invalid max_tokens: {self.config.max_tokens}")
            return False

        if self.config.retry_attempts < 0:
            logger.error(f"Invalid retry_attempts: {self.config.retry_attempts}")
            return False

        logger.debug("Provider configuration validated successfully")
        return True

    def get_provider_info(self) -> Dict[str, str]:
        """
        Get provider information for logging and diagnostics.

        Returns:
            Dictionary with provider details
        """
        return {
            "provider_type": str(self.provider_type),
            "model_name": self.config.model_name or "default",
            "temperature": str(self.config.temperature),
            "max_tokens": str(self.config.max_tokens),
            "safety_level": str(self.config.safety_level),
            "initialized": str(self._initialized),
        }


# Utility function for provider factory pattern
def create_provider(provider_type: str, **kwargs) -> LLMProvider:
    """
    Factory function to create provider instances.

    Args:
        provider_type: Type of provider to create ("vertex_ai", "openai", etc.)
        **kwargs: Configuration parameters for the provider

    Returns:
        Initialized LLMProvider instance

    Raises:
        ValueError: If provider_type is not supported

    Example:
        >>> provider = create_provider(
        ...     "vertex_ai",
        ...     project_id="my-project",
        ...     location="us-central1",
        ...     model_name="gemini-1.5-flash"
        ... )
        >>> provider.initialize()
    """
    from hefesto.llm.claude_provider import ClaudeProvider
    from hefesto.llm.gemini_api_client import GeminiAPIClient
    from hefesto.llm.openai_provider import OpenAIProvider

    provider_map = {
        "gemini": GeminiAPIClient,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }

    if provider_type not in provider_map:
        raise ValueError(
            f"Unsupported provider type: {provider_type}. "
            f"Supported types: {list(provider_map.keys())}"
        )

    # Instantiate provider with kwargs
    # Modern providers (Gemini, Claude, OpenAI) use api_key/model pattern
    provider_class = provider_map[provider_type]
    provider = provider_class(**kwargs)

    logger.info(f"Created provider: {provider_type}")
    return provider


__all__ = [
    "LLMProvider",
    "ProviderConfig",
    "ProviderType",
    "SafetyLevel",
    "RefactorSuggestion",
    "TestSuggestion",
    "IssueFinding",
    "create_provider",
]
