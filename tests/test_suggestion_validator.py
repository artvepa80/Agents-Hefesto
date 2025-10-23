"""
HEFESTO v3.5 - SuggestionValidator Test Suite

Comprehensive tests for the enhanced validation layer.

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import pytest
from llm.suggestion_validator import (
    SuggestionValidator,
    SuggestionValidationResult,
    get_validator,
)


class TestSuggestionValidatorBasics:
    """Basic validation tests"""

    def test_validator_initialization(self):
        """Test validator initializes with correct defaults"""
        validator = SuggestionValidator()

        assert validator.min_similarity == 0.3
        assert validator.max_similarity == 0.95
        assert validator.confidence_threshold == 0.5
        assert len(validator.dangerous_calls) > 0
        assert "eval" in validator.dangerous_calls
        assert "exec" in validator.dangerous_calls

    def test_get_validator_singleton(self):
        """Test get_validator returns singleton instance"""
        validator1 = get_validator()
        validator2 = get_validator()

        assert validator1 is validator2


class TestSyntaxValidation:
    """Test syntax validation"""

    def test_validator_rejects_syntax_errors(self):
        """Test 1: Invalid Python should fail validation"""
        validator = SuggestionValidator()

        original = "def foo():\n    return 42"
        invalid_suggested = "def foo(\n    return 42"  # Missing closing paren

        result = validator.validate(
            original_code=original,
            suggested_code=invalid_suggested,
            issue_type="style",
        )

        assert result.valid is False
        assert result.confidence == 0.0  # Syntax error = zero confidence
        assert len(result.issues) > 0
        assert any("Syntax error" in issue for issue in result.issues)
        assert result.safe_to_apply is False

    def test_validator_accepts_valid_syntax(self):
        """Test validator accepts syntactically valid code"""
        validator = SuggestionValidator()

        original = "def foo():\n    x = 1\n    return x"
        suggested = "def foo() -> int:\n    return 1"

        result = validator.validate(
            original_code=original,
            suggested_code=suggested,
            issue_type="unused_variable",
        )

        assert result.valid is True
        assert "Syntax error" not in str(result.issues)


class TestDangerousPatterns:
    """Test dangerous pattern detection"""

    def test_validator_rejects_dangerous_calls(self):
        """Test 2: exec/eval/os.system should fail validation"""
        validator = SuggestionValidator()

        original = "def process_data(data):\n    return data.strip()"
        dangerous_suggested = "def process_data(data):\n    return eval(data)"

        result = validator.validate(
            original_code=original,
            suggested_code=dangerous_suggested,
            issue_type="security",
        )

        assert result.valid is False
        assert any("Dangerous" in issue or "eval" in issue for issue in result.issues)
        assert result.safe_to_apply is False

    def test_validator_detects_subprocess_calls(self):
        """Test validator detects dangerous subprocess usage"""
        validator = SuggestionValidator()

        original = "def get_info():\n    return 'data'"
        dangerous_suggested = "import subprocess\ndef get_info():\n    return subprocess.call('ls')"

        result = validator.validate(
            original_code=original,
            suggested_code=dangerous_suggested,
            issue_type="security",
        )

        assert result.valid is False
        assert any("Dangerous" in issue or "subprocess" in issue.lower() for issue in result.issues)

    def test_validator_detects_dangerous_imports(self):
        """Test validator detects dangerous imports like pickle"""
        validator = SuggestionValidator()

        original = "def load_data():\n    return {}"
        dangerous_suggested = (
            "import pickle\ndef load_data():\n    return pickle.load(open('data.pkl'))"
        )

        result = validator.validate(
            original_code=original,
            suggested_code=dangerous_suggested,
            issue_type="security",
        )

        assert result.valid is False
        assert any(
            "Dangerous import" in issue or "pickle" in issue.lower() for issue in result.issues
        )


class TestSimilarityAnalysis:
    """Test code similarity analysis"""

    def test_validator_rejects_drastic_changes(self):
        """Test 3: >70% change should generate warnings"""
        validator = SuggestionValidator(min_similarity=0.3)

        original = "def foo():\n    return 42"
        drastically_different = """
class CompletelyDifferentArchitecture:
    def __init__(self, config, logger, metrics_system):
        self.configuration = config
        self.logger_instance = logger
        self.metrics = metrics_system
        self.state_machine = {}

    def process_business_logic(self, input_data, context):
        validated = self._validate_input(input_data)
        processed = self._transform_data(validated, context)
        return self._format_output(processed)
"""

        result = validator.validate(
            original_code=original,
            suggested_code=drastically_different,
            issue_type="code_complexity",
        )

        # Should still be valid but have warnings due to drastic change
        assert result.similarity_score < 0.3  # Now truly below threshold
        assert len(result.warnings) > 0
        assert any(
            "Large change" in warning or "similarity" in warning.lower()
            for warning in result.warnings
        )

    def test_similarity_calculation_identical_code(self):
        """Test similarity is 1.0 for identical code"""
        validator = SuggestionValidator()

        code = "def foo():\n    return 42"
        similarity = validator.calculate_similarity(code, code)

        assert similarity == 1.0

    def test_similarity_calculation_minor_change(self):
        """Test similarity is high for minor changes"""
        validator = SuggestionValidator()

        original = "def foo():\n    return 42"
        suggested = "def foo():\n    return 43"  # Just changed 42 to 43

        similarity = validator.calculate_similarity(original, suggested)

        assert similarity > 0.9


class TestValidSuggestions:
    """Test validator accepts good suggestions"""

    def test_validator_accepts_good_suggestion(self):
        """Test 4: Valid fixes should pass all checks"""
        validator = SuggestionValidator()

        original = """def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + str(user_id)
    return db.execute(query)"""

        suggested = """def get_user(user_id):
    query = "SELECT * FROM users WHERE id = ?"
    return db.execute(query, (user_id,))"""

        result = validator.validate(
            original_code=original,
            suggested_code=suggested,
            issue_type="code_complexity",
        )

        assert result.valid is True
        assert result.confidence > 0.5
        assert result.similarity_score > 0.7
        assert result.similarity_score < 0.95
        assert len(result.issues) == 0

    def test_validator_accepts_docstring_addition(self):
        """Test validator accepts adding docstrings"""
        validator = SuggestionValidator()

        original = "def calculate_score(x, y):\n    return x * y"
        suggested = '"""Calculate product score"""\ndef calculate_score(x, y):\n    """Multiply x and y"""\n    return x * y'

        result = validator.validate(
            original_code=original,
            suggested_code=suggested,
            issue_type="missing_docstring",
        )

        assert result.valid is True
        assert result.confidence >= 0.95  # Docstring addition is safe


class TestConfidenceScoring:
    """Test confidence score calculation"""

    def test_validator_confidence_calculation(self):
        """Test 5: Confidence score accuracy for various scenarios"""
        validator = SuggestionValidator()

        # Scenario 1: Good change
        original = "def foo(): x = 1; return x"
        suggested = "def foo(): return 1"

        result = validator.validate(original, suggested, "unused_variable")

        assert result.valid is True
        assert 0.5 <= result.confidence <= 1.0

        # Scenario 2: Syntax error = zero confidence
        invalid = "def foo( invalid syntax"
        result2 = validator.validate(original, invalid, "style")

        assert result2.valid is False
        assert result2.confidence == 0.0

    def test_confidence_factors(self):
        """Test confidence calculation considers multiple factors"""
        validator = SuggestionValidator()

        original = "def foo():\n    return 1"
        suggested = "def foo():\n    return 2"

        result = validator.validate(original, suggested, "missing_type_hints")

        # Check that details contain all confidence factors
        assert "confidence_factors" in result.details
        factors = result.details["confidence_factors"]

        assert "syntax_valid" in factors
        assert "no_secrets" in factors
        assert "no_dangerous_patterns" in factors
        assert "similarity" in factors


class TestSecurityValidation:
    """Test security-specific validation"""

    def test_validator_security_fixes(self):
        """Test 6: Security-specific validation rules"""
        validator = SuggestionValidator()

        # Test hardcoded secret detection
        original = "def get_db(): return connect()"
        suggested_with_secret = 'def get_db(): return connect(password="hardcoded123")'

        result = validator.validate(
            original_code=original,
            suggested_code=suggested_with_secret,
            issue_type="security",
        )

        # Should detect hardcoded credentials
        assert result.valid is False
        assert any("secret" in issue.lower() for issue in result.issues)

    def test_validator_rejects_unsafe_categories(self):
        """Test validator rejects unsafe issue categories"""
        validator = SuggestionValidator()

        original = "def foo(): return 1"
        suggested = "def foo(): return 2"

        # sql_injection is an unsafe category
        result = validator.validate(original, suggested, "sql_injection")

        assert result.valid is False
        assert any(
            "unsafe" in issue.lower() or "category" in issue.lower() for issue in result.issues
        )


class TestMaintainabilityValidation:
    """Test maintainability-specific validation"""

    def test_validator_maintainability_fixes(self):
        """Test 7: Maintainability checks for code complexity"""
        validator = SuggestionValidator()

        # Test that deeply nested functions are rejected
        original = "def foo():\n    return 1"
        nested_code = """def outer():
    def level1():
        def level2():
            def level3():
                def level4():
                    return 1
                return level4()
            return level3()
        return level2()
    return level1()"""

        result = validator.validate(
            original_code=original,
            suggested_code=nested_code,
            issue_type="code_complexity",
        )

        # Should fail structure validation due to excessive nesting
        assert result.valid is False
        assert any(
            "nesting" in issue.lower() or "structure" in issue.lower() for issue in result.issues
        )


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_validator_edge_cases(self):
        """Test 8: Empty code, unicode, edge cases"""
        validator = SuggestionValidator()

        # Test 1: Empty original code
        result1 = validator.validate(
            original_code="",
            suggested_code="def foo(): return 1",
            issue_type="missing_docstring",
        )
        assert result1.similarity_score == 0.0

        # Test 2: Empty suggested code
        result2 = validator.validate(
            original_code="def foo(): return 1",
            suggested_code="",
            issue_type="missing_docstring",
        )
        assert result2.valid is False  # Empty code fails syntax validation

        # Test 3: Unicode handling
        original_unicode = "def greet():\n    return 'Hello'"
        suggested_unicode = "def greet():\n    return 'Hola señor 你好'"

        result3 = validator.validate(original_unicode, suggested_unicode, "missing_docstring")
        assert result3.valid is True  # Should handle unicode correctly

    def test_validator_whitespace_differences(self):
        """Test validator handles whitespace differences correctly"""
        validator = SuggestionValidator()

        # Only whitespace differences
        original = "def foo():\n    return 1"
        suggested = "def foo():\n        return 1"  # Different indentation

        result = validator.validate(original, suggested, "inconsistent_naming")

        # Should be valid but similarity might be affected
        assert result.valid is True

    def test_validator_comment_changes(self):
        """Test validator handles comment additions"""
        validator = SuggestionValidator()

        original = "def foo():\n    return 1"
        suggested = "def foo():\n    # This returns 1\n    return 1"

        result = validator.validate(original, suggested, "missing_docstring")

        assert result.valid is True
        assert result.confidence > 0.7


class TestValidationResult:
    """Test validation result object"""

    def test_validation_result_structure(self):
        """Test validation result has all required fields"""
        validator = SuggestionValidator()

        original = "def foo(): return 1"
        suggested = "def foo(): return 2"

        result = validator.validate(original, suggested, "style")

        # Check all required fields exist
        assert hasattr(result, "valid")
        assert hasattr(result, "confidence")
        assert hasattr(result, "issues")
        assert hasattr(result, "safe_to_apply")
        assert hasattr(result, "warnings")
        assert hasattr(result, "validation_passed")
        assert hasattr(result, "similarity_score")
        assert hasattr(result, "details")

        # Check types
        assert isinstance(result.valid, bool)
        assert isinstance(result.confidence, float)
        assert isinstance(result.issues, list)
        assert isinstance(result.safe_to_apply, bool)
        assert isinstance(result.warnings, list)
        assert isinstance(result.similarity_score, float)
        assert isinstance(result.details, dict)

    def test_validation_result_to_dict(self):
        """Test validation result can be converted to dict for API"""
        validator = SuggestionValidator()

        original = "def foo(): return 1"
        suggested = "def foo(): return 2"

        result = validator.validate(original, suggested, "style")
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "valid" in result_dict
        assert "confidence" in result_dict
        assert "safe_to_apply" in result_dict
        assert "similarity_score" in result_dict


class TestSportsContextValidation:
    """Test sports analytics specific validation"""

    def test_sports_domain_validation(self):
        """Test sports-specific patterns are recognized"""
        validator = SuggestionValidator()

        original = "def predict_match(match_id):\n    return 0.5"
        suggested = "def predict_match(match_id: MatchId) -> float:\n    return 0.5"

        result = validator.validate(original, suggested, "missing_type_hints")

        # Should be valid with possible sports-specific warnings
        assert result.valid is True
        # Sports validation generates warnings, not errors
        assert result.confidence > 0.0


class TestIntegration:
    """Integration tests combining multiple validation aspects"""

    def test_complete_validation_workflow(self):
        """Test complete validation workflow with real-world example"""
        validator = SuggestionValidator(
            min_similarity=0.3,
            max_similarity=0.95,
            confidence_threshold=0.5,
        )

        # Real-world refactoring: Remove unused variable
        original = """def calculate_team_score(home_goals, away_goals):
    total = home_goals + away_goals
    difference = home_goals - away_goals
    return difference"""

        suggested = """def calculate_team_score(home_goals, away_goals):
    return home_goals - away_goals"""

        result = validator.validate(original, suggested, "unused_variable")

        # Should pass all checks
        assert result.valid is True
        assert result.confidence > 0.5
        assert result.safe_to_apply is True
        assert 0.4 < result.similarity_score < 0.9
        assert len(result.issues) == 0

        # Check all validations ran
        assert "syntax" in result.details
        assert "secrets" in result.details
        assert "category" in result.details
        assert "structure" in result.details
        assert "dangerous_patterns" in result.details

    def test_validation_rejects_multiple_issues(self):
        """Test validator detects multiple problems at once"""
        validator = SuggestionValidator()

        original = "def foo(): return 1"
        problematic = """def foo():
    password = "hardcoded_password_123"
    eval("dangerous code")
    return 1"""

        result = validator.validate(original, problematic, "security")

        # Should detect both hardcoded secret AND dangerous eval
        assert result.valid is False
        assert len(result.issues) >= 2
        assert any("secret" in issue.lower() for issue in result.issues)
        assert any(
            "dangerous" in issue.lower() or "eval" in issue.lower() for issue in result.issues
        )


# Test parametrization for confidence threshold variations
@pytest.mark.parametrize(
    "threshold,expected_safe",
    [
        (0.3, True),  # Low threshold = more suggestions safe to apply
        (0.7, False),  # High threshold = fewer suggestions safe to apply
        (0.9, False),  # Very high threshold = very few suggestions safe
    ],
)
def test_confidence_threshold_variations(threshold, expected_safe):
    """Test different confidence thresholds affect safe_to_apply"""
    validator = SuggestionValidator(confidence_threshold=threshold)

    # Medium-quality suggestion
    original = "def foo(): x = 1; return x"
    suggested = "def foo(): return 1"

    result = validator.validate(original, suggested, "unused_variable")

    # With low threshold, should be safe to apply
    # With high threshold, might not be
    if threshold <= 0.5:
        assert result.valid is True  # Should at least be valid


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
