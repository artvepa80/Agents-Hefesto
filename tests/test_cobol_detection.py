"""
Unit tests for COBOL language detection.

Tests that COBOL files (.cbl, .cob, .cpy, .pco) are correctly detected
and registered as Language.COBOL.

Copyright 2025 Narapa LLC, Miami, Florida
"""

from pathlib import Path

from hefesto.core.language_detector import LanguageDetector
from hefesto.core.languages.specs import Language


class TestCobolDetection:
    """Tests for COBOL file detection."""

    def test_cbl_extension_detected(self):
        """Files with .cbl extension should be detected as COBOL."""
        file_path = Path("test_program.cbl")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang == Language.COBOL

    def test_cob_extension_detected(self):
        """Files with .cob extension should be detected as COBOL."""
        file_path = Path("test_program.cob")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang == Language.COBOL

    def test_cpy_extension_detected(self):
        """Files with .cpy extension (copybook) should be detected as COBOL."""
        file_path = Path("CUST-RECORD.cpy")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang == Language.COBOL

    def test_pco_extension_detected(self):
        """Files with .pco extension (precompiled) should be detected as COBOL."""
        file_path = Path("test_program.pco")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang == Language.COBOL

    def test_uppercase_cbl_extension_detected(self):
        """Files with .CBL (uppercase) extension should be detected as COBOL."""
        file_path = Path("LEGACY-PROG.CBL")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang == Language.COBOL

    def test_uppercase_cob_extension_detected(self):
        """Files with .COB (uppercase) extension should be detected as COBOL."""
        file_path = Path("LEGACY-PROG.COB")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang == Language.COBOL

    def test_uppercase_cpy_extension_detected(self):
        """Files with .CPY (uppercase) extension should be detected as COBOL."""
        file_path = Path("LEGACY-COPYBOOK.CPY")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang == Language.COBOL

    def test_python_file_not_detected_as_cobol(self):
        """Python files should NOT be detected as COBOL (negative test)."""
        file_path = Path("test_script.py")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang != Language.COBOL
        assert detected_lang == Language.PYTHON

    def test_javascript_file_not_detected_as_cobol(self):
        """JavaScript files should NOT be detected as COBOL (negative test)."""
        file_path = Path("app.js")
        detected_lang = LanguageDetector.detect(file_path)
        assert detected_lang != Language.COBOL
        assert detected_lang == Language.JAVASCRIPT

    def test_cobol_is_supported(self):
        """COBOL should be in the list of supported languages."""
        supported = LanguageDetector.get_supported_languages()
        assert "cobol" in supported
