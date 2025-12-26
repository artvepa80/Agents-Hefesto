"""
OpenAI API Provider - OpenAI GPT Integration

This provider integrates OpenAI's GPT models for code analysis and refactoring.
Uses the official openai SDK for reliable, high-quality responses.

Author: OMEGA Development Team
Date: 2025-11-13
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from openai import APIConnectionError, APIError, OpenAI, RateLimitError
except ImportError:
    raise ImportError("openai SDK not installed. Install with: pip install openai")

from hefesto.llm.provider import (  # noqa: F401
    IssueFinding,
    LLMProvider,
    ProviderConfig,
    RefactorSuggestion,
    TestSuggestion,
)
from hefesto.security.masking import mask_text, validate_masked

logger = logging.getLogger(__name__)


# Data classes for structured responses
@dataclass
class LLMResponse:
    """Generic LLM response wrapper."""

    text: str
    raw_text: str
    metadata: Dict[str, Any]
    success: bool
    error: Optional[str] = None


@dataclass
class PatchProposal:
    """Patch proposal from LLM."""

    unified_diff: str
    explanation: str
    confidence: float
    file_path: str
    original_lines: List[str]
    proposed_lines: List[str]
    safety_notes: List[str]


@dataclass
class IssueExplanation:
    """Detailed explanation of a code issue."""

    summary: str
    root_cause: str
    impact: str
    recommendations: List[str]
    severity: str


@dataclass
class ImpactEstimate:
    """Business impact estimate."""

    severity: str
    business_risk: str
    estimated_effort: str
    priority: str
    recommendations: List[str]


# Model configuration
DEFAULT_MODEL = "gpt-4o"
FALLBACK_MODEL = "gpt-4o-mini"

# Generation config
DEFAULT_GENERATION_CONFIG = {
    "temperature": 0.2,
    "max_tokens": 2048,
}


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider implementation using openai SDK.

    This provider uses OpenAI's GPT models for code analysis,
    offering high-quality refactoring suggestions and detailed explanations.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        **kwargs,
    ):
        """
        Initialize OpenAI API provider.

        Args:
            api_key: OpenAI API key (or from OPENAI_API_KEY env var)
            model: Model name (default: gpt-4o)
            **kwargs: Additional generation config parameters
        """
        # Get API key from env if not provided
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Set environment variable or pass api_key parameter. "
                "Get your API key at: https://platform.openai.com/api-keys"
            )

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)

        # Model configuration
        self.model_name = model
        self.generation_config = {
            **DEFAULT_GENERATION_CONFIG,
            **kwargs,
        }

        logger.info(f"✅ OpenAI API provider initialized with model: {self.model_name}")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """
        Generate completion from prompt.

        Args:
            prompt: Input prompt
            system_prompt: Optional system prompt for context
            **kwargs: Override generation config

        Returns:
            LLMResponse with generated text and metadata
        """
        try:
            # Merge generation config
            gen_config = {**self.generation_config, **kwargs}

            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Call OpenAI API
            start_time = time.time()

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=gen_config.get("temperature", 0.2),
                max_tokens=gen_config.get("max_tokens", 2048),
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract text from response
            text = ""
            if response.choices and len(response.choices) > 0:
                text = response.choices[0].message.content or ""

            # Mask sensitive data in response
            mask_result = mask_text(text)
            masked_text = mask_result.masked_text

            # Extract metadata
            metadata = {
                "model": self.model_name,
                "finish_reason": response.choices[0].finish_reason if response.choices else None,
                "latency_ms": latency_ms,
            }

            # Add token usage if available
            if hasattr(response, "usage") and response.usage:
                metadata["input_tokens"] = response.usage.prompt_tokens
                metadata["output_tokens"] = response.usage.completion_tokens
                metadata["total_tokens"] = response.usage.total_tokens

            return LLMResponse(
                text=masked_text,
                raw_text=text,
                metadata=metadata,
                success=True,
            )

        except RateLimitError as e:
            logger.error(f"❌ OpenAI API rate limit: {e}")
            return LLMResponse(
                text="",
                raw_text="",
                metadata={"error": "rate_limit", "model": self.model_name},
                success=False,
                error=f"Rate limit exceeded: {str(e)}",
            )
        except APIConnectionError as e:
            logger.error(f"❌ OpenAI API connection error: {e}")
            return LLMResponse(
                text="",
                raw_text="",
                metadata={"error": "connection_error", "model": self.model_name},
                success=False,
                error=f"Connection error: {str(e)}",
            )
        except APIError as e:
            logger.error(f"❌ OpenAI API error: {e}")
            return LLMResponse(
                text="",
                raw_text="",
                metadata={"error": "api_error", "model": self.model_name},
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return LLMResponse(
                text="",
                raw_text="",
                metadata={"error": "unknown", "model": self.model_name},
                success=False,
                error=str(e),
            )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Input text

        Returns:
            Token count (estimated)
        """
        try:
            # Use tiktoken for accurate token counting
            import tiktoken

            encoding = tiktoken.encoding_for_model(self.model_name)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            # Rough estimate: 1 token ≈ 4 chars for GPT models
            return len(text) // 4

    def validate_api_key(self) -> bool:
        """
        Validate API key by making a test request.

        Returns:
            True if API key is valid
        """
        try:
            response = self.generate("Hello", max_tokens=10)
            return response.success
        except Exception:
            return False

    def propose_patch(
        self,
        file_path: str,
        issue_description: str,
        code_context: str,
        rule_id: Optional[str] = None,
        severity: str = "MEDIUM",
        mask_sensitive: bool = True,
    ) -> PatchProposal:
        """
        Generate a patch proposal to fix a code issue.

        Args:
            file_path: Path to the file with the issue
            issue_description: Description of the issue to fix
            code_context: Code context around the issue
            rule_id: Rule ID that detected the issue (optional)
            severity: Issue severity (CRITICAL, HIGH, MEDIUM, LOW)
            mask_sensitive: Whether to mask sensitive data (default: True)

        Returns:
            PatchProposal with unified diff and explanation
        """
        # Mask sensitive data if requested
        if mask_sensitive:
            mask_result = mask_text(code_context)
            code_context = mask_result.masked_text

            # Validate masking
            is_valid, violations = validate_masked(code_context)
            if not is_valid:
                logger.error(f"Masking validation failed: {violations}")
                raise ValueError("Sensitive data detected in context after masking")

        # Build prompt for code refactoring
        system_prompt = (
            "You are HEFESTO v3.0, an expert code quality assistant. "
            "Your responses must be precise, secure, and follow best practices."
        )

        prompt = f"""TASK: Propose a code fix for the following issue.

FILE: {file_path}
ISSUE: {issue_description}
SEVERITY: {severity}
{f"RULE_ID: {rule_id}" if rule_id else ""}

CODE CONTEXT:
```
{code_context}
```

INSTRUCTIONS:
1. Analyze the code and identify the exact problem
2. Propose a safe, minimal fix that addresses the issue
3. Generate a unified diff showing the changes
4. Explain your reasoning and any safety considerations

RESPONSE FORMAT (JSON):
{{
  "unified_diff": "--- a/{file_path}\\n+++ b/{file_path}\\n@@ -1,1 +1,1 @@\\n-old code\\n+new code",
  "explanation": "Detailed explanation of the fix",
  "confidence": 0.0-1.0,
  "safety_notes": ["List of safety considerations"]
}}

Generate the JSON response now:"""

        try:
            # Generate response
            response = self.generate(prompt, system_prompt=system_prompt, temperature=0.2)

            if not response.success:
                raise RuntimeError(f"LLM generation failed: {response.error}")

            # Parse JSON response
            text = response.text.strip()
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to parse the whole response as JSON
                json_str = text

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback: create a basic patch from the response
                logger.warning("Failed to parse JSON, using fallback")
                data = {
                    "unified_diff": f"--- a/{file_path}\n+++ b/{file_path}\n{text[:500]}",
                    "explanation": text[:1000],
                    "confidence": 0.5,
                    "safety_notes": ["Manual review recommended"],
                }

            # Build PatchProposal
            proposal = PatchProposal(
                unified_diff=data.get("unified_diff", ""),
                explanation=data.get("explanation", ""),
                confidence=float(data.get("confidence", 0.0)),
                file_path=file_path,
                original_lines=[],
                proposed_lines=[],
                safety_notes=data.get("safety_notes", []),
            )

            logger.info(
                f"Generated patch for {file_path} with confidence {proposal.confidence:.2f}"
            )

            return proposal

        except Exception as e:
            logger.error(f"Failed to generate patch: {e}", exc_info=True)
            raise

    def explain_issue(
        self,
        file_path: str,
        issue_description: str,
        code_context: str,
        rule_id: Optional[str] = None,
        severity: str = "MEDIUM",
        mask_sensitive: bool = True,
    ) -> IssueExplanation:
        """
        Generate a detailed explanation of a code issue.

        Args:
            file_path: Path to the file with the issue
            issue_description: Brief description of the issue
            code_context: Code context around the issue
            rule_id: Rule ID that detected the issue (optional)
            severity: Issue severity (CRITICAL, HIGH, MEDIUM, LOW)
            mask_sensitive: Whether to mask sensitive data (default: True)

        Returns:
            IssueExplanation with detailed analysis
        """
        if mask_sensitive:
            mask_result = mask_text(code_context)
            code_context = mask_result.masked_text

        system_prompt = (
            "You are HEFESTO v3.0, an expert code quality assistant "
            "specializing in detailed issue analysis."
        )

        prompt = f"""Explain this code issue in detail:

FILE: {file_path}
ISSUE: {issue_description}
SEVERITY: {severity}

CODE:
```
{code_context}
```

Provide:
1. Summary of the issue
2. Root cause analysis
3. Business/security impact
4. Specific recommendations

Format as JSON:
{{
  "summary": "...",
  "root_cause": "...",
  "impact": "...",
  "recommendations": ["...", "..."],
  "severity": "{severity}"
}}"""

        response = self.generate(prompt, system_prompt=system_prompt, temperature=0.2)

        # Parse response
        try:
            text = response.text.strip()
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = text

            data = json.loads(json_str)
        except Exception:
            data = {
                "summary": response.text[:200],
                "root_cause": "Analysis failed",
                "impact": "Unknown",
                "recommendations": ["Manual review required"],
                "severity": severity,
            }

        return IssueExplanation(**data)

    # =========================================================================
    # LLMProvider Abstract Methods Implementation
    # =========================================================================

    def initialize(self) -> bool:
        """Initialize the OpenAI API provider and validate credentials."""
        return self.validate_api_key()

    def suggest_refactor(self, code: str, issue: Dict[str, Any]) -> RefactorSuggestion:
        """
        Suggest code refactoring to fix identified issues.

        Args:
            code: The problematic code
            issue: Dictionary with issue details (type, severity, line, description, file_path)

        Returns:
            RefactorSuggestion with proposed changes
        """
        file_path = issue.get("file_path", "unknown.py")
        issue_desc = issue.get("description", "Code issue detected")
        severity = issue.get("severity", "MEDIUM")
        issue_type = issue.get("type", "unknown")

        # Use propose_patch method to generate refactoring
        proposal = self.propose_patch(
            file_path=file_path,
            issue_description=issue_desc,
            code_context=code,
            severity=severity,
            mask_sensitive=True,
        )

        # Convert PatchProposal to RefactorSuggestion
        return RefactorSuggestion(
            original_code=code,
            refactored_code=proposal.unified_diff,
            explanation=proposal.explanation,
            confidence=proposal.confidence,
            safety_validated=len(proposal.safety_notes) == 0,
            issues_addressed=[issue_type],
            estimated_impact=f"{severity} severity issue",
        )

    def generate_tests(self, func: str) -> TestSuggestion:
        """
        Generate comprehensive tests for a given function.

        Args:
            func: Complete function definition

        Returns:
            TestSuggestion with generated test code
        """
        system_prompt = (
            "You are HEFESTO v3.0, an expert in test generation. "
            "Generate comprehensive, production-ready tests."
        )

        prompt = f"""Generate comprehensive pytest tests for this function:

```python
{func}
```

Provide:
1. Test code using pytest
2. Normal cases, edge cases, and error conditions
3. Clear test names and assertions

Format as JSON:
{{
  "test_code": "...",
  "test_framework": "pytest",
  "coverage_areas": ["...", "..."],
  "edge_cases": ["...", "..."]
}}"""

        response = self.generate(prompt, system_prompt=system_prompt, temperature=0.2)

        # Parse response
        try:
            text = response.text.strip()
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = text

            data = json.loads(json_str)
        except Exception:
            # Fallback
            data = {
                "test_code": f"# Generated test\n{response.text[:500]}",
                "test_framework": "pytest",
                "coverage_areas": ["basic functionality"],
                "edge_cases": ["error handling"],
            }

        # Extract function signature
        sig_match = re.search(r"def\s+(\w+)\s*\([^)]*\)", func)
        function_sig = sig_match.group(0) if sig_match else "unknown_function()"

        return TestSuggestion(
            function_signature=function_sig,
            test_code=data.get("test_code", ""),
            test_framework=data.get("test_framework", "pytest"),
            coverage_areas=data.get("coverage_areas", []),
            edge_cases=data.get("edge_cases", []),
            confidence=0.85,
        )

    def explain_finding(self, issue: Dict[str, Any]) -> IssueFinding:
        """
        Provide detailed explanation of a code issue.

        Args:
            issue: Dictionary with issue details

        Returns:
            IssueFinding with detailed explanation
        """
        file_path = issue.get("file_path", "unknown.py")
        issue_desc = issue.get("description", "Code issue")
        severity = issue.get("severity", "MEDIUM")
        code_context = issue.get("code_context", "")

        # Use explain_issue method
        explanation = self.explain_issue(
            file_path=file_path,
            issue_description=issue_desc,
            code_context=code_context,
            severity=severity,
            mask_sensitive=True,
        )

        # Convert IssueExplanation to IssueFinding
        return IssueFinding(
            summary=explanation.summary,
            technical_details=explanation.root_cause,
            severity=explanation.severity,
            root_cause=explanation.root_cause,
            consequences=[explanation.impact],
            recommendations=explanation.recommendations,
            sports_context=None,
        )

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the OpenAI API provider.

        Returns:
            Dictionary with health status information
        """
        try:
            start_time = time.time()

            # Simple test generation
            response = self.generate("test", max_tokens=10)

            latency_ms = int((time.time() - start_time) * 1000)

            if response.success:
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "provider_type": "openai",
                    "model_name": self.model_name,
                }
            else:
                return {
                    "status": "unhealthy",
                    "latency_ms": latency_ms,
                    "provider_type": "openai",
                    "model_name": self.model_name,
                    "error": response.error,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "provider_type": "openai",
                "model_name": self.model_name,
                "error": str(e),
            }


# Convenience function
def create_openai_client(
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    **kwargs,
) -> OpenAIProvider:
    """
    Create and configure OpenAI API client.

    Args:
        api_key: OpenAI API key
        model: Model name
        **kwargs: Additional config

    Returns:
        Configured OpenAIProvider
    """
    return OpenAIProvider(api_key=api_key, model=model, **kwargs)


# Test function
def test_openai_client():
    """Test OpenAI API client."""
    print("Testing OpenAI API Client...")

    try:
        client = create_openai_client()
        print(f"✅ Client initialized: {client.model_name}")

        # Test generation
        response = client.generate("Say 'Hello, HEFESTO v3.0!' and nothing else.")
        print("\n📤 Test prompt: 'Say Hello, HEFESTO v3.0!'")
        print(f"📥 Response: {response.text}")
        print(f"✅ Success: {response.success}")

        if response.metadata.get("input_tokens"):
            print(
                f"📊 Tokens - Input: {response.metadata['input_tokens']}, "
                f"Output: {response.metadata['output_tokens']}"
            )

        # Health check
        health = client.health_check()
        print(f"\n💚 Health: {health['status']}")
        print(f"⏱️  Latency: {health['latency_ms']}ms")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    test_openai_client()
