"""
HEFESTO v3.5 - Enhanced Suggestion Validator

Purpose: Validate LLM-generated code suggestions with confidence scoring and similarity analysis.
Location: llm/suggestion_validator.py

This module extends the existing validators.py with v3.5-specific enhancements:
- Code similarity analysis (prevent drastic changes)
- Confidence scoring (0-1 scale)
- Enhanced dangerous pattern detection
- Issue-specific validation rules
- Structured validation response

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import ast
import difflib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

# Import semantic analyzer (Phase 1)
from hefesto.llm.semantic_analyzer import get_semantic_analyzer

# Import existing validation infrastructure
from hefesto.llm.validators import (
    validate_function_structure,
    validate_no_secrets,
    validate_safe_category,
    validate_sports_context,
    validate_syntax,
)

# Configure logging
logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Validation result categories"""

    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


@dataclass
class SuggestionValidationResult:
    """
    Structured validation result for LLM suggestions.

    Attributes:
        valid: Overall validation status
        confidence: Confidence score (0-1)
        issues: List of validation issues
        safe_to_apply: Whether suggestion is safe to auto-apply
        warnings: Non-critical warnings
        validation_passed: Whether all checks passed
        similarity_score: Code similarity to original (0-1, syntactic)
        semantic_similarity: Semantic code similarity (0-1, ML-based)
        is_duplicate: Whether suggestion is semantically duplicate (>0.85)
        details: Detailed validation breakdown
    """

    valid: bool
    confidence: float
    issues: List[str]
    safe_to_apply: bool
    warnings: List[str] = None
    validation_passed: bool = True
    similarity_score: float = 0.0
    semantic_similarity: Optional[float] = None
    is_duplicate: bool = False
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.details is None:
            self.details = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
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


class SuggestionValidator:
    """
    Enhanced validator for LLM-generated code suggestions.

    This validator builds on the existing validators.py infrastructure and adds:
    - Similarity analysis to detect drastic changes
    - Confidence scoring based on multiple factors
    - Enhanced dangerous pattern detection
    - Issue-specific validation rules

    Usage:
        validator = SuggestionValidator()
        result = validator.validate(original_code, suggested_code, "security")

        if result.safe_to_apply:
            apply_suggestion(suggested_code)
        else:
            logger.warning(f"Unsafe suggestion: {result.issues}")
    """

    def __init__(
        self,
        min_similarity: float = 0.3,
        max_similarity: float = 0.95,
        confidence_threshold: float = 0.5,
    ):
        """
        Initialize the suggestion validator.

        Args:
            min_similarity: Minimum similarity to original code (0-1)
            max_similarity: Maximum similarity (too high = no real change)
            confidence_threshold: Minimum confidence for safe_to_apply
        """
        self.min_similarity = min_similarity
        self.max_similarity = max_similarity
        self.confidence_threshold = confidence_threshold

        # Dangerous patterns (extended from validators.py)
        self.dangerous_calls: Set[str] = {
            "eval",
            "exec",
            "compile",
            "__import__",
            "os.system",
            "subprocess.call",
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.check_output",
            "os.popen",
            "commands.getoutput",
        }

        # Dangerous imports
        self.dangerous_imports: Set[str] = {
            "pickle",
            "marshal",
            "shelve",
            "dill",
        }

        logger.info(
            f"SuggestionValidator initialized: "
            f"min_similarity={min_similarity}, "
            f"confidence_threshold={confidence_threshold}"
        )

    def calculate_similarity(self, original: str, suggested: str) -> float:
        """
        Calculate similarity between original and suggested code.

        Uses SequenceMatcher to compare code strings, ignoring whitespace
        differences but considering structural changes.

        Args:
            original: Original code string
            suggested: Suggested code string

        Returns:
            Similarity score (0-1), where:
            - 0.0: Completely different
            - 0.5: 50% similar
            - 1.0: Identical

        Example:
            >>> validator = SuggestionValidator()
            >>> original = "def foo(): return 1"
            >>> suggested = "def foo(): return 2"
            >>> similarity = validator.calculate_similarity(original, suggested)
            >>> assert 0.8 < similarity < 1.0
        """
        if not original or not suggested:
            return 0.0

        # Normalize whitespace for fairer comparison
        original_normalized = " ".join(original.split())
        suggested_normalized = " ".join(suggested.split())

        # Use SequenceMatcher for similarity ratio
        matcher = difflib.SequenceMatcher(None, original_normalized, suggested_normalized)
        similarity = matcher.ratio()

        logger.debug(f"Code similarity: {similarity:.2f}")
        return similarity

    def check_dangerous_patterns(self, code: str) -> Tuple[bool, List[str]]:
        """
        Check for dangerous code patterns beyond basic validation.

        Detects:
        - Dangerous function calls (eval, exec, os.system, subprocess)
        - Dangerous imports (pickle, marshal)
        - Shell injection patterns
        - File system manipulation

        Args:
            code: Code string to check

        Returns:
            Tuple of (is_safe, violations)
        """
        violations: List[str] = []

        try:
            tree = ast.parse(code)

            # Check for dangerous calls
            class DangerousPatternChecker(ast.NodeVisitor):
                def __init__(self, validator):
                    self.validator = validator
                    self.violations = []

                def visit_Call(self, node):
                    # Check direct function calls
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.validator.dangerous_calls:
                            self.violations.append(f"Dangerous function: {node.func.id}")

                    # Check attribute calls (os.system, subprocess.call)
                    elif isinstance(node.func, ast.Attribute):
                        full_name = self._get_full_name(node.func)
                        if full_name in self.validator.dangerous_calls:
                            self.violations.append(f"Dangerous function: {full_name}")

                    self.generic_visit(node)

                def visit_Import(self, node):
                    for alias in node.names:
                        if alias.name.split(".")[0] in self.validator.dangerous_imports:
                            self.violations.append(f"Dangerous import: {alias.name}")
                    self.generic_visit(node)

                def visit_ImportFrom(self, node):
                    if (
                        node.module
                        and node.module.split(".")[0] in self.validator.dangerous_imports
                    ):
                        self.violations.append(f"Dangerous import from: {node.module}")
                    self.generic_visit(node)

                def _get_full_name(self, node):
                    """Get full qualified name of an attribute"""
                    if isinstance(node, ast.Name):
                        return node.id
                    elif isinstance(node, ast.Attribute):
                        prefix = self._get_full_name(node.value)
                        return f"{prefix}.{node.attr}"
                    return ""

            checker = DangerousPatternChecker(self)
            checker.visit(tree)
            violations.extend(checker.violations)

        except SyntaxError as e:
            violations.append(f"Syntax error during pattern check: {e}")
        except Exception as e:
            logger.error(f"Pattern check error: {e}")
            violations.append(f"Pattern check failed: {type(e).__name__}")

        # Additional regex-based checks for patterns AST might miss
        dangerous_patterns = [
            (r"__import__\s*\(", "Dynamic import detected"),
            (r"globals\s*\(\s*\)", "globals() access detected"),
            (r"locals\s*\(\s*\)", "locals() manipulation detected"),
            (r"setattr\s*\(", "setattr() usage (potential security risk)"),
            (r"getattr\s*\(.*\bgetattr\b", "Nested getattr (potential exploit)"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):
                violations.append(message)

        is_safe = len(violations) == 0

        if not is_safe:
            logger.warning(f"Dangerous patterns found: {len(violations)}")
            for v in violations:
                logger.debug(f"  - {v}")

        return is_safe, violations

    def check_semantic_similarity(
        self,
        original_code: str,
        suggested_code: str,
        duplicate_threshold: float = 0.85,
    ) -> Tuple[Optional[float], bool, List[str]]:
        """
        Check semantic similarity using ML embeddings (Phase 1 feature).

        Uses semantic analyzer to detect code similarity beyond syntactic matching.
        Can identify duplicate suggestions even when variable names or structure differ.

        Args:
            original_code: Original code string
            suggested_code: Suggested code string
            duplicate_threshold: Similarity threshold for duplicate detection (default: 0.85)

        Returns:
            Tuple of (semantic_similarity, is_duplicate, warnings)
            - semantic_similarity: 0.0-1.0 score, or None if semantic analysis unavailable
            - is_duplicate: True if similarity > threshold
            - warnings: List of warning messages

        Example:
            >>> validator = SuggestionValidator()
            >>> sim, is_dup, warns = validator.check_semantic_similarity(
            ...     "def add(a, b): return a + b",
            ...     "def sum_two(x, y): return x + y"
            ... )
            >>> assert sim > 0.80  # Semantically similar despite different names
            >>> assert is_dup == True  # Detected as duplicate
        """
        warnings: List[str] = []

        try:
            # Get semantic analyzer singleton
            analyzer = get_semantic_analyzer()

            # Calculate semantic similarity
            semantic_sim = analyzer.calculate_similarity(
                original_code, suggested_code, language="python"
            )

            # Check if duplicate
            is_duplicate = semantic_sim >= duplicate_threshold

            if is_duplicate:
                warnings.append(
                    f"Semantically duplicate suggestion detected "
                    f"(similarity: {semantic_sim:.1%}). "
                    "This suggestion may have been made before."
                )
                logger.info(
                    f"Duplicate detected: semantic_similarity={semantic_sim:.2f} "
                    f">= threshold={duplicate_threshold}"
                )
            else:
                logger.debug(
                    f"Semantic similarity: {semantic_sim:.2f} "
                    f"(threshold: {duplicate_threshold})"
                )

            return semantic_sim, is_duplicate, warnings

        except Exception as e:
            # Non-blocking: If semantic analysis fails, continue without it
            logger.warning(
                f"Semantic similarity check failed (non-blocking): {e}. "
                "Continuing with syntactic similarity only."
            )
            return None, False, []

    def calculate_confidence(
        self,
        similarity: float,
        syntax_valid: bool,
        no_secrets: bool,
        no_dangerous_patterns: bool,
        category_safe: bool,
        structure_valid: bool,
        issue_type: str,
    ) -> float:
        """
        Calculate confidence score for the suggestion.

        Confidence is based on multiple factors:
        - Syntax validity (critical)
        - No secrets detected (critical)
        - No dangerous patterns (critical)
        - Safe issue category (important)
        - Structure validity (important)
        - Similarity to original (moderate - too low or too high is bad)

        Args:
            similarity: Code similarity score (0-1)
            syntax_valid: Whether syntax is valid
            no_secrets: Whether no secrets detected
            no_dangerous_patterns: Whether no dangerous patterns found
            category_safe: Whether issue category is safe
            structure_valid: Whether structure is valid
            issue_type: Type of issue being addressed

        Returns:
            Confidence score (0-1)
        """
        confidence = 1.0

        # Critical factors (each failure reduces confidence significantly)
        if not syntax_valid:
            confidence *= 0.0  # Invalid syntax = zero confidence

        if not no_secrets:
            confidence *= 0.0  # Secrets = zero confidence

        if not no_dangerous_patterns:
            confidence *= 0.1  # Dangerous patterns = very low confidence

        # Important factors
        if not category_safe:
            confidence *= 0.3  # Unsafe category = low confidence

        if not structure_valid:
            confidence *= 0.5  # Invalid structure = reduced confidence

        # Similarity factor (sweet spot is 0.3-0.8)
        if similarity < self.min_similarity:
            # Too different - might be rewriting entire function
            similarity_penalty = similarity / self.min_similarity
            confidence *= 0.5 + 0.5 * similarity_penalty
            logger.debug(f"Low similarity penalty: {1 - similarity_penalty:.2f}")

        elif similarity > self.max_similarity:
            # Too similar - might not be fixing anything
            similarity_penalty = (1.0 - similarity) / (1.0 - self.max_similarity)
            confidence *= 0.7 + 0.3 * similarity_penalty
            logger.debug(f"High similarity penalty: {1 - similarity_penalty:.2f}")

        # Issue-specific adjustments
        safe_issue_types = {
            "missing_docstring": 1.0,
            "missing_type_hints": 1.0,
            "unused_variable": 0.95,
            "unused_import": 0.95,
            "code_complexity": 0.85,
            "long_function": 0.80,
        }

        risky_issue_types = {
            "security": 0.7,
            "authentication": 0.6,
            "authorization": 0.6,
            "data_validation": 0.75,
        }

        issue_key = issue_type.lower()
        if issue_key in safe_issue_types:
            confidence *= safe_issue_types[issue_key]
        elif issue_key in risky_issue_types:
            confidence *= risky_issue_types[issue_key]

        # Ensure confidence is in valid range
        confidence = max(0.0, min(1.0, confidence))

        logger.debug(f"Calculated confidence: {confidence:.2f}")
        return confidence

    def validate(
        self,
        original_code: str,
        suggested_code: str,
        issue_type: str,
    ) -> SuggestionValidationResult:
        """
        Validate an LLM-generated code suggestion.

        This is the main validation method that runs all checks and returns
        a comprehensive validation result with confidence scoring.

        Args:
            original_code: Original code before suggestion
            suggested_code: Suggested code from LLM
            issue_type: Type of issue being addressed

        Returns:
            SuggestionValidationResult with validation details

        Example:
            >>> validator = SuggestionValidator()
            >>> original = "def foo():\\n    x = 1\\n    return x"
            >>> suggested = "def foo() -> int:\\n    return 1"
            >>> result = validator.validate(original, suggested, "unused_variable")
            >>> assert result.valid == True
            >>> assert result.confidence > 0.5
            >>> assert result.safe_to_apply == True
        """
        issues: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # 1. Calculate similarity (syntactic)
        similarity = self.calculate_similarity(original_code, suggested_code)
        details["similarity"] = similarity

        if similarity < self.min_similarity:
            warnings.append(
                f"Large change detected (similarity: {similarity:.1%}). "
                "Review carefully before applying."
            )
        elif similarity > self.max_similarity:
            warnings.append(
                f"Minimal change detected (similarity: {similarity:.1%}). "
                "May not address the issue effectively."
            )

        # 1.5. Semantic similarity check (Phase 1 - ML-based)
        semantic_similarity, is_duplicate, semantic_warnings = self.check_semantic_similarity(
            original_code, suggested_code, duplicate_threshold=0.85
        )
        details["semantic_similarity"] = semantic_similarity
        details["is_duplicate"] = is_duplicate
        warnings.extend(semantic_warnings)

        if is_duplicate:
            logger.warning(
                f"Duplicate suggestion detected via semantic analysis "
                f"(semantic_similarity={semantic_similarity:.1%})"
            )

        # 2. Syntax validation
        syntax_valid, syntax_error = validate_syntax(suggested_code)
        details["syntax"] = {"valid": syntax_valid, "error": syntax_error}

        if not syntax_valid:
            issues.append(f"Syntax error: {syntax_error}")

        # 3. Secret detection
        no_secrets, secret_violations = validate_no_secrets(suggested_code)
        details["secrets"] = {"valid": no_secrets, "violations": secret_violations}

        if not no_secrets:
            issues.append(f"Hardcoded secrets detected: {len(secret_violations)} patterns")
            for violation in secret_violations[:3]:  # Show first 3
                issues.append(f"  - {violation}")

        # 4. Category validation
        category_safe, category_reason = validate_safe_category(issue_type)
        details["category"] = {"safe": category_safe, "reason": category_reason}

        if not category_safe:
            issues.append(f"Unsafe issue category: {category_reason}")

        # 5. Structure validation
        structure_valid, structure_error = validate_function_structure(suggested_code)
        details["structure"] = {"valid": structure_valid, "error": structure_error}

        if not structure_valid:
            issues.append(f"Structure error: {structure_error}")

        # 6. Dangerous pattern detection (v3.5 enhancement)
        no_dangerous_patterns, dangerous_violations = self.check_dangerous_patterns(suggested_code)
        details["dangerous_patterns"] = {
            "safe": no_dangerous_patterns,
            "violations": dangerous_violations,
        }

        if not no_dangerous_patterns:
            issues.append(f"Dangerous patterns detected: {len(dangerous_violations)}")
            for violation in dangerous_violations:
                issues.append(f"  - {violation}")

        # 7. Sports context validation (warnings only)
        sports_valid, sports_warnings = validate_sports_context(suggested_code, issue_type)
        details["sports_context"] = {"valid": sports_valid, "warnings": sports_warnings}
        warnings.extend(sports_warnings)

        # 8. Calculate confidence score
        confidence = self.calculate_confidence(
            similarity=similarity,
            syntax_valid=syntax_valid,
            no_secrets=no_secrets,
            no_dangerous_patterns=no_dangerous_patterns,
            category_safe=category_safe,
            structure_valid=structure_valid,
            issue_type=issue_type,
        )
        details["confidence_factors"] = {
            "similarity": similarity,
            "syntax_valid": syntax_valid,
            "no_secrets": no_secrets,
            "no_dangerous_patterns": no_dangerous_patterns,
            "category_safe": category_safe,
            "structure_valid": structure_valid,
        }

        # 9. Determine overall validity
        valid = (
            syntax_valid
            and no_secrets
            and category_safe
            and structure_valid
            and no_dangerous_patterns
        )

        # 10. Determine if safe to auto-apply
        safe_to_apply = valid and confidence >= self.confidence_threshold

        # Log result
        if valid:
            logger.info(
                f"Validation PASSED: confidence={confidence:.2f}, "
                f"similarity={similarity:.2f}, semantic_similarity={semantic_similarity}, "
                f"is_duplicate={is_duplicate}, safe_to_apply={safe_to_apply}"
            )
        else:
            logger.warning(
                f"Validation FAILED: {len(issues)} issues found, " f"confidence={confidence:.2f}"
            )

        return SuggestionValidationResult(
            valid=valid,
            confidence=confidence,
            issues=issues,
            safe_to_apply=safe_to_apply,
            warnings=warnings,
            validation_passed=valid,
            similarity_score=similarity,
            semantic_similarity=semantic_similarity,
            is_duplicate=is_duplicate,
            details=details,
        )


# Singleton instance
_validator_instance: Optional[SuggestionValidator] = None


def get_validator(
    min_similarity: float = 0.3,
    max_similarity: float = 0.95,
    confidence_threshold: float = 0.5,
) -> SuggestionValidator:
    """
    Get singleton instance of SuggestionValidator.

    Args:
        min_similarity: Minimum similarity to original code
        max_similarity: Maximum similarity to original code
        confidence_threshold: Minimum confidence for safe_to_apply

    Returns:
        SuggestionValidator instance
    """
    global _validator_instance

    if _validator_instance is None:
        _validator_instance = SuggestionValidator(
            min_similarity=min_similarity,
            max_similarity=max_similarity,
            confidence_threshold=confidence_threshold,
        )

    return _validator_instance


__all__ = [
    "SuggestionValidator",
    "SuggestionValidationResult",
    "ValidationResult",
    "get_validator",
]
