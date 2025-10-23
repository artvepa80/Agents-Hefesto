"""
Gemini API Client - Direct Google Generative AI Integration

This client uses google.generativeai SDK directly instead of Vertex AI,
which requires project allowlist access.

Author: OMEGA Development Team
Date: 2025-10-01
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
except ImportError:
    raise ImportError(
        "google-generativeai not installed. Install with: pip install google-generativeai"
    )

import time
from dataclasses import dataclass  # noqa: F811

from hefesto.llm.provider import IssueFinding, LLMProvider, RefactorSuggestion, TestSuggestion
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
# Using Gemini 2.0 Flash (experimental) - latest and fastest model
DEFAULT_MODEL = "gemini-2.0-flash-exp"
FALLBACK_MODEL = "gemini-1.5-flash"

# Generation config
DEFAULT_GENERATION_CONFIG = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
}

# Safety settings (permissive for code generation)
SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_ONLY_HIGH",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_ONLY_HIGH",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_ONLY_HIGH",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_ONLY_HIGH",
    },
]


@dataclass
class GeminiConfig:
    """Configuration for Gemini API client."""

    api_key: str
    model: str = DEFAULT_MODEL
    temperature: float = 0.2
    max_output_tokens: int = 2048
    top_p: float = 0.95
    top_k: int = 40


class GeminiAPIClient(LLMProvider):
    """
    Gemini API client implementation using google.generativeai SDK.

    This bypasses Vertex AI and uses Gemini API directly, which doesn't
    require project allowlist access.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        **kwargs,
    ):
        """
        Initialize Gemini API client.

        Args:
            api_key: Google AI API key (or from GEMINI_API_KEY env var)
            model: Model name (default: gemini-1.5-flash)
            **kwargs: Additional generation config parameters
        """
        # Get API key from env if not provided
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. Set environment variable or pass api_key parameter. "
                "Get your API key at: https://aistudio.google.com/app/apikey"
            )

        # Configure genai with API key
        genai.configure(api_key=self.api_key)

        # Model configuration
        self.model_name = model
        self.generation_config = {
            **DEFAULT_GENERATION_CONFIG,
            **kwargs,
        }

        # Initialize model
        try:
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config,
                safety_settings=SAFETY_SETTINGS,
            )
            logger.info(f"✅ Gemini API client initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini model: {e}")
            # Try fallback model
            if self.model_name != FALLBACK_MODEL:
                logger.info(f"Trying fallback model: {FALLBACK_MODEL}")
                self.model_name = FALLBACK_MODEL
                self.model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config=self.generation_config,
                    safety_settings=SAFETY_SETTINGS,
                )
            else:
                raise

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate completion from prompt.

        Args:
            prompt: Input prompt
            **kwargs: Override generation config

        Returns:
            LLMResponse with generated text and metadata
        """
        try:
            # Merge generation config
            gen_config = {**self.generation_config, **kwargs}

            # Generate content
            response = self.model.generate_content(
                prompt,
                generation_config=gen_config,
                safety_settings=SAFETY_SETTINGS,
            )

            # Extract text
            text = response.text if hasattr(response, "text") else ""

            # Mask sensitive data in response
            mask_result = mask_text(text)
            masked_text = mask_result.masked_text

            # Extract metadata
            metadata = {
                "model": self.model_name,
                "finish_reason": getattr(response, "finish_reason", None),
                "safety_ratings": getattr(response, "safety_ratings", []),
            }

            # Try to get token counts
            try:
                if hasattr(response, "usage_metadata"):
                    metadata["input_tokens"] = response.usage_metadata.prompt_token_count
                    metadata["output_tokens"] = response.usage_metadata.candidates_token_count
                    metadata["total_tokens"] = response.usage_metadata.total_token_count
            except Exception:
                pass

            return LLMResponse(
                text=masked_text,
                raw_text=text,
                metadata=metadata,
                success=True,
            )

        except Exception as e:
            logger.error(f"❌ Gemini API error: {e}")
            return LLMResponse(
                text="",
                raw_text="",
                metadata={"error": str(e), "model": self.model_name},
                success=False,
                error=str(e),
            )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Input text

        Returns:
            Token count
        """
        try:
            result = self.model.count_tokens(text)
            return result.total_tokens if hasattr(result, "total_tokens") else 0
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            # Rough estimate: 1 token ≈ 4 chars
            return len(text) // 4

    def list_models(self) -> List[str]:
        """
        List available models.

        Returns:
            List of model names
        """
        try:
            models = genai.list_models()
            return [
                model.name
                for model in models
                if "generateContent" in model.supported_generation_methods
            ]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return [DEFAULT_MODEL, FALLBACK_MODEL]

    def validate_api_key(self) -> bool:
        """
        Validate API key by making a test request.

        Returns:
            True if API key is valid
        """
        try:
            response = self.generate("Hello")
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
        prompt = f"""You are HEFESTO v3.0, an expert code quality assistant for sports analytics.

TASK: Propose a code fix for the following issue.

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
            response = self.generate(prompt, temperature=0.2)

            if not response.success:
                raise RuntimeError(f"LLM generation failed: {response.error}")

            # Parse JSON response
            import json
            import re

            # Extract JSON from response (handle markdown code blocks)
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

        response = self.generate(prompt, temperature=0.2)

        # Parse response (simplified)
        import json

        try:
            data = json.loads(response.text.strip())
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
        """Initialize the Gemini API client and validate credentials."""
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
            refactored_code=proposal.unified_diff,  # Use unified_diff as refactored code
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

        response = self.generate(prompt, temperature=0.2)

        # Parse response
        import json

        try:
            data = json.loads(response.text.strip())
        except Exception:
            # Fallback
            data = {
                "test_code": f"# Generated test\n{response.text[:500]}",
                "test_framework": "pytest",
                "coverage_areas": ["basic functionality"],
                "edge_cases": ["error handling"],
            }

        # Extract function signature
        import re

        sig_match = re.search(r"def\s+(\w+)\s*\([^)]*\)", func)
        function_sig = sig_match.group(0) if sig_match else "unknown_function()"

        return TestSuggestion(
            function_signature=function_sig,
            test_code=data.get("test_code", ""),
            test_framework=data.get("test_framework", "pytest"),
            coverage_areas=data.get("coverage_areas", []),
            edge_cases=data.get("edge_cases", []),
            confidence=0.8,
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
        Perform health check on the Gemini API provider.

        Returns:
            Dictionary with health status information
        """
        try:
            start_time = time.time()

            # Simple test generation
            response = self.generate("test", max_output_tokens=10)

            latency_ms = int((time.time() - start_time) * 1000)

            if response.success:
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "provider_type": "gemini_api",
                    "model_name": self.model_name,
                }
            else:
                return {
                    "status": "unhealthy",
                    "latency_ms": latency_ms,
                    "provider_type": "gemini_api",
                    "model_name": self.model_name,
                    "error": response.error,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "provider_type": "gemini_api",
                "model_name": self.model_name,
                "error": str(e),
            }

    def estimate_impact(
        self,
        issue_description: str,
        severity: str,
        affected_areas: Optional[List[str]] = None,
    ) -> ImpactEstimate:
        """
        Estimate business impact of an issue.

        Args:
            issue_description: Description of the issue
            severity: Issue severity (CRITICAL, HIGH, MEDIUM, LOW)
            affected_areas: List of affected system areas (optional)

        Returns:
            ImpactEstimate with business impact analysis
        """
        areas_str = ", ".join(affected_areas) if affected_areas else "Unknown"

        prompt = f"""Estimate the business impact of this issue:

ISSUE: {issue_description}
SEVERITY: {severity}
AFFECTED AREAS: {areas_str}

Provide:
1. Business risk assessment
2. Estimated effort to fix
3. Priority recommendation
4. Action items

Format as JSON:
{{
  "severity": "{severity}",
  "business_risk": "...",
  "estimated_effort": "...",
  "priority": "...",
  "recommendations": ["..."]
}}"""

        response = self.generate(prompt, temperature=0.2)

        # Parse response
        import json

        try:
            data = json.loads(response.text.strip())
        except Exception:
            data = {
                "severity": severity,
                "business_risk": "Unknown",
                "estimated_effort": "Unknown",
                "priority": "MEDIUM",
                "recommendations": ["Manual assessment required"],
            }

        return ImpactEstimate(**data)


# Convenience function
def create_gemini_client(
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    **kwargs,
) -> GeminiAPIClient:
    """
    Create and configure Gemini API client.

    Args:
        api_key: Google AI API key
        model: Model name
        **kwargs: Additional config

    Returns:
        Configured GeminiAPIClient
    """
    return GeminiAPIClient(api_key=api_key, model=model, **kwargs)


# Test function
def test_gemini_client():
    """Test Gemini API client."""
    print("Testing Gemini API Client...")

    try:
        client = create_gemini_client()
        print(f"✅ Client initialized: {client.model_name}")

        # Test generation
        response = client.generate("Say 'Hello, HEFESTO v3.0!' and nothing else.")
        print(f"\n📤 Test prompt: 'Say Hello, HEFESTO v3.0!'")  # noqa: F541
        print(f"📥 Response: {response.text}")
        print(f"✅ Success: {response.success}")

        if response.metadata.get("input_tokens"):
            print(
                f"📊 Tokens - Input: {response.metadata['input_tokens']}, "
                f"Output: {response.metadata['output_tokens']}"
            )

        # List available models
        models = client.list_models()
        print(f"\n📋 Available models: {len(models)}")
        for model in models[:5]:
            print(f"  • {model}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    test_gemini_client()
