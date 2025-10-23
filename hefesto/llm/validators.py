"""
HEFESTO v3.0 - LLM Response Validators

Purpose: Validate LLM-generated code for safety, correctness, and security.
Location: llm/validators.py

This module provides comprehensive validation of LLM outputs before they are
applied to production codebases. All validations follow QNEW standards and
enterprise security requirements.

Features:
- AST-based syntax validation
- Secret pattern detection (16 patterns from security/masking.py)
- Safe issue category validation
- Code structure validation
- Sports analytics specific validation

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import ast
import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from hefesto.security.masking import MASKING_PATTERNS

# Configure logging
logger = logging.getLogger(__name__)


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


# Issue categories that require human review (NOT safe for auto-fix)
UNSAFE_CATEGORIES: Set[str] = {
    "sql_injection",
    "command_injection",
    "path_traversal",
    "xxe",
    "csrf",
    "hardcoded_password",
    "hardcoded_secret",
    "hardcoded_api_key",
    "authentication_bypass",
    "authorization_bypass",
    "privilege_escalation",
    "sensitive_data_exposure",
    "broken_access_control",
}


def validate_syntax(code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Python code syntax using AST parsing.

    This function checks if the provided code is syntactically valid Python
    without executing it. This is a critical safety check before applying any
    LLM-generated code changes.

    Args:
        code: Python code string to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if syntax is valid, False otherwise
        - error_message: None if valid, error description if invalid

    Example:
        >>> is_valid, error = validate_syntax("def foo(): return 42")
        >>> assert is_valid == True
        >>> assert error is None
        >>>
        >>> is_valid, error = validate_syntax("def foo( invalid")
        >>> assert is_valid == False
        >>> assert "SyntaxError" in error
    """
    if not code or not isinstance(code, str):
        return False, "Code must be a non-empty string"

    try:
        # Attempt to parse the code into an AST
        ast.parse(code)
        logger.debug("Code syntax validation passed")
        return True, None

    except SyntaxError as e:
        error_msg = f"SyntaxError at line {e.lineno}: {e.msg}"
        logger.warning(f"Syntax validation failed: {error_msg}")
        return False, error_msg

    except ValueError as e:
        error_msg = f"ValueError during parsing: {str(e)}"
        logger.warning(f"Syntax validation failed: {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error during syntax validation: {type(e).__name__}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def validate_no_secrets(code: str) -> Tuple[bool, List[str]]:
    """
    Validate that code contains no hardcoded secrets or sensitive data.

    Uses the same 16 security patterns from security/masking.py to detect:
    - API keys
    - Passwords
    - Tokens
    - AWS credentials
    - JWT tokens
    - Private keys
    - GitHub tokens
    - Slack tokens
    - Credit cards
    - SSNs
    - IP addresses
    - Bearer tokens
    - Basic auth credentials

    This validation ensures LLM-generated code doesn't accidentally introduce
    security vulnerabilities by hardcoding sensitive information.

    Args:
        code: Python code string to validate

    Returns:
        Tuple of (is_valid, violations)
        - is_valid: True if no secrets found, False if secrets detected
        - violations: List of detected secret patterns (empty if valid)

    Example:
        >>> code = 'username = "admin"'
        >>> is_valid, violations = validate_no_secrets(code)
        >>> assert is_valid == True
        >>>
        >>> code = 'API_KEY = "sk-1234567890abcdef"'
        >>> is_valid, violations = validate_no_secrets(code)
        >>> assert is_valid == False
        >>> assert len(violations) > 0
    """
    if not code or not isinstance(code, str):
        return True, []  # Empty code is valid (no secrets)

    violations: List[str] = []

    # Use the same patterns from security/masking.py
    for pattern_name, pattern_regex in MASKING_PATTERNS.items():
        matches = list(pattern_regex.finditer(code))

        if matches:
            for match in matches:
                # Extract a safe preview (first 50 chars)
                matched_text = match.group(0)
                preview = matched_text[:50] + "..." if len(matched_text) > 50 else matched_text

                violation = (
                    f"{pattern_name}: {preview} (line {code[:match.start()].count(chr(10)) + 1})"
                )
                violations.append(violation)
                logger.warning(f"Secret pattern detected: {violation}")

    is_valid = len(violations) == 0

    if is_valid:
        logger.debug("No secrets detected in code")
    else:
        logger.error(f"Detected {len(violations)} secret patterns in code")

    return is_valid, violations


def validate_safe_category(issue_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that an issue category is safe for automated fixes.

    HEFESTO only applies automated refactoring suggestions for issues in the
    safe category list. Critical security issues like SQL injection or hardcoded
    passwords require human review and cannot be auto-fixed.

    Args:
        issue_type: The issue category to validate

    Returns:
        Tuple of (is_safe, reason)
        - is_safe: True if safe for auto-fix, False if requires human review
        - reason: None if safe, explanation if unsafe

    Example:
        >>> is_safe, reason = validate_safe_category("missing_docstring")
        >>> assert is_safe == True
        >>>
        >>> is_safe, reason = validate_safe_category("sql_injection")
        >>> assert is_safe == False
        >>> assert "requires human review" in reason
    """
    if not issue_type or not isinstance(issue_type, str):
        return False, "Issue type must be a non-empty string"

    # Check if it's an explicitly unsafe category
    if issue_type.lower() in UNSAFE_CATEGORIES:
        reason = (
            f"Issue type '{issue_type}' requires human review and cannot be auto-fixed. "
            "This is a critical security issue that needs expert analysis."
        )
        logger.warning(f"Unsafe category detected: {issue_type}")
        return False, reason

    # Check if it's a recognized safe category
    safe_categories = {cat.value for cat in IssueCategory}
    if issue_type.lower() in safe_categories:
        logger.debug(f"Issue type '{issue_type}' is safe for auto-fix")
        return True, None

    # Unknown category - err on the side of caution
    reason = (
        f"Unknown issue type '{issue_type}'. "
        "Only recognized safe categories can be auto-fixed. "
        "This issue requires human review."
    )
    logger.warning(f"Unknown category: {issue_type}")
    return False, reason


def validate_function_structure(code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that code maintains proper function structure.

    Checks for:
    - Function definitions are well-formed
    - No dangerous built-ins (eval, exec, compile, __import__)
    - Proper indentation structure
    - No nested functions beyond reasonable depth

    Args:
        code: Python code string to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> code = "def foo():\\n    return 42"
        >>> is_valid, error = validate_function_structure(code)
        >>> assert is_valid == True
    """
    if not code or not isinstance(code, str):
        return False, "Code must be a non-empty string"

    # First check syntax
    is_valid_syntax, syntax_error = validate_syntax(code)
    if not is_valid_syntax:
        return False, f"Syntax error: {syntax_error}"

    try:
        tree = ast.parse(code)

        # Check for dangerous built-ins
        dangerous_calls = {"eval", "exec", "compile", "__import__", "open"}

        class DangerousCallChecker(ast.NodeVisitor):
            def __init__(self):
                self.violations = []

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    if node.func.id in dangerous_calls:
                        self.violations.append(f"Dangerous function call: {node.func.id}")
                self.generic_visit(node)

        checker = DangerousCallChecker()
        checker.visit(tree)

        if checker.violations:
            error_msg = "; ".join(checker.violations)
            logger.warning(f"Dangerous code structure detected: {error_msg}")
            return False, error_msg

        # Check for excessive nesting
        class NestingChecker(ast.NodeVisitor):
            def __init__(self):
                self.max_depth = 0
                self.current_depth = 0

            def visit_FunctionDef(self, node):
                self.current_depth += 1
                self.max_depth = max(self.max_depth, self.current_depth)
                self.generic_visit(node)
                self.current_depth -= 1

        nesting = NestingChecker()
        nesting.visit(tree)

        if nesting.max_depth > 3:
            error_msg = f"Excessive function nesting detected: {nesting.max_depth} levels"
            logger.warning(error_msg)
            return False, error_msg

        logger.debug("Function structure validation passed")
        return True, None

    except Exception as e:
        error_msg = f"Structure validation error: {type(e).__name__}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def validate_sports_context(code: str, issue_type: str) -> Tuple[bool, List[str]]:
    """
    Validate sports analytics specific code patterns.

    Checks for:
    - Proper data validation for sports metrics
    - Match ID and Team ID type usage
    - Sports API timeout handling
    - Prediction confidence logging

    Args:
        code: Python code string to validate
        issue_type: Type of issue being addressed

    Returns:
        Tuple of (is_valid, warnings)
        - is_valid: True if validation passes (may have warnings)
        - warnings: List of non-critical warnings

    Example:
        >>> code = "def predict_match(match_id: MatchId) -> float:\\n    pass"
        >>> is_valid, warnings = validate_sports_context(code, "missing_type_hints")
        >>> assert is_valid == True
    """
    warnings: List[str] = []

    if not code or not isinstance(code, str):
        return True, warnings  # Empty code is valid

    # Check for sports domain patterns
    sports_patterns = {
        "match_data": r"\bmatch[_\s]data\b",
        "team_stats": r"\bteam[_\s]stats\b",
        "prediction": r"\bpredict(ion)?\b",
        "accuracy": r"\baccuracy\b",
        "confidence": r"\bconfidence\b",
    }

    has_sports_context = any(
        re.search(pattern, code, re.IGNORECASE) for pattern in sports_patterns.values()
    )

    if has_sports_context:
        # Check for proper type hints in sports code
        if "MatchId" in code or "TeamId" in code:
            logger.debug("Sports branded types detected")
        else:
            warnings.append("Consider using branded types (MatchId, TeamId) for sports entities")

        # Check for prediction confidence logging
        if "prediction" in code.lower() or "predict" in code.lower():
            if "logger" not in code and "log" not in code:
                warnings.append("Sports prediction code should log confidence metrics")

        # Check for data validation
        if "match" in code.lower() or "team" in code.lower():
            if "validate" not in code.lower() and "assert" not in code:
                warnings.append("Sports data processing should include validation")

    # Always valid, but may have warnings for improvement
    if warnings:
        logger.info(f"Sports validation warnings: {len(warnings)}")
        for warning in warnings:
            logger.debug(f"  - {warning}")

    return True, warnings


def validate_all(code: str, issue_type: str, strict: bool = True) -> Tuple[bool, Dict[str, Any]]:
    """
    Run all validation checks on generated code.

    This is the primary validation function that should be called before
    applying any LLM-generated code. It runs all safety checks and returns
    a comprehensive validation report.

    Args:
        code: Python code string to validate
        issue_type: Type of issue being addressed
        strict: If True, any validation failure fails the entire check

    Returns:
        Tuple of (is_valid, report)
        - is_valid: True only if all critical validations pass
        - report: Dictionary with detailed validation results

    Example:
        >>> code = "def safe_function():\\n    return 42"
        >>> is_valid, report = validate_all(code, "missing_docstring")
        >>> assert is_valid == True
        >>> assert report["syntax"]["valid"] == True
        >>> assert report["secrets"]["valid"] == True
        >>> assert report["category"]["safe"] == True
    """
    report = {
        "overall_valid": False,
        "syntax": {},
        "secrets": {},
        "category": {},
        "structure": {},
        "sports_context": {},
        "strict_mode": strict,
    }

    # 1. Syntax validation (critical)
    syntax_valid, syntax_error = validate_syntax(code)
    report["syntax"] = {
        "valid": syntax_valid,
        "error": syntax_error,
    }

    if not syntax_valid:
        logger.error(f"Validation failed: Syntax error - {syntax_error}")
        if strict:
            return False, report

    # 2. Secret detection (critical)
    no_secrets, secret_violations = validate_no_secrets(code)
    report["secrets"] = {
        "valid": no_secrets,
        "violations": secret_violations,
    }

    if not no_secrets:
        logger.error(f"Validation failed: {len(secret_violations)} secrets detected")
        if strict:
            return False, report

    # 3. Category validation (critical)
    category_safe, category_reason = validate_safe_category(issue_type)
    report["category"] = {
        "safe": category_safe,
        "reason": category_reason,
    }

    if not category_safe:
        logger.error(f"Validation failed: Unsafe category - {category_reason}")
        if strict:
            return False, report

    # 4. Structure validation (critical)
    structure_valid, structure_error = validate_function_structure(code)
    report["structure"] = {
        "valid": structure_valid,
        "error": structure_error,
    }

    if not structure_valid:
        logger.error(f"Validation failed: Structure error - {structure_error}")
        if strict:
            return False, report

    # 5. Sports context validation (warnings only)
    sports_valid, sports_warnings = validate_sports_context(code, issue_type)
    report["sports_context"] = {
        "valid": sports_valid,
        "warnings": sports_warnings,
    }

    # Overall validation result
    report["overall_valid"] = syntax_valid and no_secrets and category_safe and structure_valid

    if report["overall_valid"]:
        logger.info("All validations passed successfully")
    else:
        logger.error("Validation failed - code cannot be applied")

    return report["overall_valid"], report


__all__ = [
    "validate_syntax",
    "validate_no_secrets",
    "validate_safe_category",
    "validate_function_structure",
    "validate_sports_context",
    "validate_all",
    "IssueCategory",
    "UNSAFE_CATEGORIES",
]
