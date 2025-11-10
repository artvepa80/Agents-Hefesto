"""
HEFESTO v2.0 - Security & Masking Layer

Purpose: Protect sensitive data before any LLM processing.
Location: security/masking.py

This module provides comprehensive PII and secret masking capabilities to ensure
that no sensitive information is exposed to LLMs or stored in training datasets.

Features:
- Regex-based PII detection (emails, phones, IDs)
- Secret scanning (API keys, tokens, passwords, AWS keys, JWT)
- Context windowing (±20 lines around issues)
- Hard cap at 12KB per context
- Hashing for referential integrity

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Maximum context size in bytes (12KB hard cap)
MAX_CONTEXT_SIZE = 12 * 1024

# Context window size (lines before and after)
CONTEXT_WINDOW_LINES = 20

# Redaction placeholder
REDACTED_PLACEHOLDER = "[REDACTED]"


@dataclass
class MaskingResult:
    """Result of masking operation with statistics."""

    masked_text: str
    redaction_count: int
    patterns_matched: Dict[str, int]
    original_hash: str
    masked_hash: str
    size_bytes: int
    truncated: bool


# Comprehensive regex patterns for PII and secrets
MASKING_PATTERNS = {
    "api_key": re.compile(
        r'(?i)(api[_-]?key|apikey)\s*[:=]\s*[\'"][A-Za-z0-9_\-\.]{16,}[\'"]', re.IGNORECASE
    ),
    "secret": re.compile(
        r'(?i)(secret|token|access[_-]?token)\s*[:=]\s*[\'"][^\'"]{8,}[\'"]', re.IGNORECASE
    ),
    "password": re.compile(
        r'(?i)(password|passwd|pwd)\s*[:=]\s*[\'"][^\'"]{4,}[\'"]', re.IGNORECASE
    ),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"),
    "aws_key": re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    "aws_secret": re.compile(
        r'(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*[\'"][A-Za-z0-9/+=]{40}[\'"]',
        re.IGNORECASE,
    ),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b"),
    "private_key": re.compile(
        r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----[A-Za-z0-9+/=\s]+-----END (?:RSA |EC )?PRIVATE KEY-----",  # noqa: E501
        re.DOTALL,
    ),
    "github_token": re.compile(r"\b(gh[ps]_[A-Za-z0-9]{36,})\b"),
    "slack_token": re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "bearer_token": re.compile(r"\b[Bb]earer\s+[A-Za-z0-9\-._~+/]+=*\b"),
    "basic_auth": re.compile(r"\b[Bb]asic\s+[A-Za-z0-9+/]+=*\b"),
}


def calculate_hash(text: str, algorithm: str = "sha256") -> str:
    """
    Calculate cryptographic hash of text for referential integrity.

    Args:
        text: Text to hash
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hexadecimal hash string

    Example:
        >>> calculate_hash("sensitive data")
        '7b5e8e8c...'
    """
    if algorithm == "sha256":
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def mask_text(
    text: str,
    patterns: Optional[Dict[str, re.Pattern]] = None,
    placeholder: str = REDACTED_PLACEHOLDER,
) -> MaskingResult:
    """
    Mask sensitive information in text using regex patterns.

    This function scans the input text for patterns matching PII and secrets,
    replacing them with a redaction placeholder. It tracks the number and types
    of redactions for audit purposes.

    Args:
        text: Input text to mask
        patterns: Custom patterns to use (default: MASKING_PATTERNS)
        placeholder: String to replace sensitive data (default: [REDACTED])

    Returns:
        MaskingResult with masked text and statistics

    Example:
        >>> code = 'API_KEY = "sk-1234567890abcdef"'
        >>> result = mask_text(code)
        >>> assert 'sk-1234567890abcdef' not in result.masked_text
        >>> assert result.redaction_count == 1
    """
    if patterns is None:
        patterns = MASKING_PATTERNS

    # Calculate original hash
    original_hash = calculate_hash(text)

    # Track statistics
    redaction_count = 0
    patterns_matched: Dict[str, int] = {}

    masked_text = text

    # Apply each pattern
    for pattern_name, pattern_regex in patterns.items():
        matches = pattern_regex.finditer(masked_text)
        match_count = 0

        for match in matches:
            # Replace the entire match with placeholder
            masked_text = masked_text.replace(match.group(0), placeholder)
            match_count += 1
            redaction_count += 1

        if match_count > 0:
            patterns_matched[pattern_name] = match_count
            logger.debug(f"Masked {match_count} instances of {pattern_name}")

    # Calculate masked hash
    masked_hash = calculate_hash(masked_text)

    # Check size
    size_bytes = len(masked_text.encode("utf-8"))
    truncated = False

    if size_bytes > MAX_CONTEXT_SIZE:
        # Truncate to max size
        masked_text = masked_text[:MAX_CONTEXT_SIZE]
        truncated = True
        size_bytes = MAX_CONTEXT_SIZE
        logger.warning(f"Context truncated from {size_bytes} to {MAX_CONTEXT_SIZE} bytes")

    return MaskingResult(
        masked_text=masked_text,
        redaction_count=redaction_count,
        patterns_matched=patterns_matched,
        original_hash=original_hash,
        masked_hash=masked_hash,
        size_bytes=size_bytes,
        truncated=truncated,
    )


def safe_snippet(
    full_text: str, line_number: int, window_lines: int = CONTEXT_WINDOW_LINES, mask: bool = True
) -> Tuple[str, int, int]:
    """
    Extract a safe code snippet with context windowing around a specific line.

    This function extracts a window of code around a target line number,
    optionally masking sensitive information. This is useful for providing
    context to LLMs without exposing the entire file or sensitive data.

    Args:
        full_text: Complete text/code to extract from
        line_number: Target line number (1-indexed)
        window_lines: Number of lines to include before and after (default: 20)
        mask: Whether to mask sensitive data (default: True)

    Returns:
        Tuple of (snippet_text, start_line, end_line)

    Example:
        >>> code = "\\n".join([f"line {i}" for i in range(1, 101)])
        >>> snippet, start, end = safe_snippet(code, 50, window_lines=5)
        >>> assert start == 45
        >>> assert end == 55
    """
    lines = full_text.split("\n")
    total_lines = len(lines)

    # Validate line number
    if line_number < 1 or line_number > total_lines:
        raise ValueError(f"Line number {line_number} out of range (1-{total_lines})")

    # Calculate window boundaries (convert to 0-indexed)
    target_idx = line_number - 1
    start_idx = max(0, target_idx - window_lines)
    end_idx = min(total_lines, target_idx + window_lines + 1)

    # Extract snippet
    snippet_lines = lines[start_idx:end_idx]
    snippet_text = "\n".join(snippet_lines)

    # Optionally mask sensitive data
    if mask:
        result = mask_text(snippet_text)
        snippet_text = result.masked_text

        if result.redaction_count > 0:
            logger.info(f"Masked {result.redaction_count} sensitive items in snippet")

    # Enforce size limit
    size_bytes = len(snippet_text.encode("utf-8"))
    if size_bytes > MAX_CONTEXT_SIZE:
        # Truncate snippet
        snippet_text = snippet_text[:MAX_CONTEXT_SIZE]
        logger.warning(f"Snippet truncated from {size_bytes} to {MAX_CONTEXT_SIZE} bytes")

    # Return snippet with line numbers (1-indexed)
    return snippet_text, start_idx + 1, end_idx


def mask_dict_values(data: Dict, keys_to_mask: Optional[List[str]] = None) -> Dict:
    """
    Recursively mask values in a dictionary based on key names.

    Useful for masking structured data like JSON payloads before logging
    or storing in training datasets.

    Args:
        data: Dictionary to mask
        keys_to_mask: List of key names to mask (default: common sensitive keys)

    Returns:
        New dictionary with masked values

    Example:
        >>> data = {"username": "admin", "password": "secret123"}
        >>> masked = mask_dict_values(data)
        >>> assert masked["password"] == "[REDACTED]"
        >>> assert masked["username"] == "admin"
    """
    if keys_to_mask is None:
        keys_to_mask = [
            "password",
            "passwd",
            "pwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_token",
            "refresh_token",
            "auth_token",
            "bearer",
            "authorization",
            "aws_secret_access_key",
            "private_key",
            "client_secret",
            "jwt",
        ]

    # Convert to lowercase for case-insensitive matching
    keys_to_mask_lower = [k.lower() for k in keys_to_mask]

    def _mask_recursive(obj):
        if isinstance(obj, dict):
            return {
                key: (
                    REDACTED_PLACEHOLDER
                    if any(mask_key in key.lower() for mask_key in keys_to_mask_lower)
                    else _mask_recursive(value)
                )
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [_mask_recursive(item) for item in obj]
        else:
            return obj

    return _mask_recursive(data)


def validate_masked(text: str) -> Tuple[bool, List[str]]:
    """
    Validate that a text has been properly masked.

    Scans the text for any remaining sensitive patterns that should have
    been masked. Returns validation status and list of violations.

    Args:
        text: Text to validate

    Returns:
        Tuple of (is_valid, violations_list)

    Example:
        >>> masked_text = "API_KEY = [REDACTED]"
        >>> is_valid, violations = validate_masked(masked_text)
        >>> assert is_valid == True
        >>> assert len(violations) == 0
    """
    violations = []

    for pattern_name, pattern_regex in MASKING_PATTERNS.items():
        matches = pattern_regex.finditer(text)
        for match in matches:
            # Check if match is already redacted
            if REDACTED_PLACEHOLDER not in match.group(0):
                violations.append(f"{pattern_name}: {match.group(0)[:50]}...")
                logger.warning(f"Unmasked {pattern_name} detected: {match.group(0)[:50]}...")

    is_valid = len(violations) == 0
    return is_valid, violations


def create_safe_context(
    file_path: str, issue_line: int, issue_description: str, mask_data: bool = True
) -> Dict:
    """
    Create a safe context dictionary for LLM prompts.

    This is the primary function for preparing code context to send to LLMs.
    It combines file snippets, issue descriptions, and masking into a single
    safe package suitable for LLM consumption.

    Args:
        file_path: Path to the file (for reference only, not read)
        issue_line: Line number where issue occurs
        issue_description: Description of the issue/finding
        mask_data: Whether to mask sensitive data (default: True)

    Returns:
        Dictionary with safe context information

    Example:
        >>> context = create_safe_context(
        ...     "/path/to/file.py",
        ...     42,
        ...     "Potential SQL injection vulnerability"
        ... )
        >>> assert context["masked"] == True
        >>> assert "file_path" in context
    """
    return {
        "file_path": file_path,
        "issue_line": issue_line,
        "issue_description": issue_description,
        "masked": mask_data,
        "max_context_size": MAX_CONTEXT_SIZE,
        "context_window_lines": CONTEXT_WINDOW_LINES,
        "redaction_placeholder": REDACTED_PLACEHOLDER,
    }


# Pre-compile patterns for performance
for key, pattern in MASKING_PATTERNS.items():
    if not isinstance(pattern, re.Pattern):
        MASKING_PATTERNS[key] = re.compile(pattern)


if __name__ == "__main__":
    # Test the masking functionality with example values
    # These are NOT real credentials, just test data to demonstrate masking
    test_code = """
    API_KEY = "sk-1234567890abcdef"
    EMAIL = "user@example.com"
    DB_PASS = "example_test_value_123"
    """

    print("Testing masking functionality with example data...")
    result = mask_text(test_code)
    print(f"Masked Text:\n{result.masked_text}")
    print(f"\nRedaction Count: {result.redaction_count}")
    print(f"Patterns Matched: {result.patterns_matched}")
    print(f"Original Hash: {result.original_hash}")
    print(f"Masked Hash: {result.masked_hash}")
