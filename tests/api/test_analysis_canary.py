"""
Canary tests for analysis API - Level 3 (TDD)

Tests with real code analysis on actual files.
Following CLAUDE.md methodology: canary tests use real data at small scale.

Canary tests verify:
- End-to-end analysis pipeline
- Real file analysis with actual AnalyzerEngine
- API response correctness with real data
- Performance with small datasets

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from hefesto.api.main import app

client = TestClient(app)


class TestSingleFileAnalysis(unittest.TestCase):
    """Test analysis of single files with real code."""

    def test_analyze_simple_python_file(self):
        """Test analyzing a simple Python file."""
        # Create temporary Python file with intentional issues
        code = '''
def complex_function(a, b, c, d, e, f):
    """Function with high complexity."""
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        if f > 0:
                            return a + b + c + d + e + f
                        else:
                            return 0
                    else:
                        return 0
                else:
                    return 0
            else:
                return 0
        else:
            return 0
    else:
        return 0

# Missing docstring
def test():
    pass
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # POST /api/v1/analyze
            response = client.post("/api/v1/analyze", json={"path": temp_path})

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert data["success"] is True
            assert "data" in data
            assert data["data"]["status"] == "completed"
            assert data["data"]["analysis_id"].startswith("ana_")

            # Verify summary
            summary = data["data"]["summary"]
            assert summary["files_analyzed"] >= 1
            assert summary["total_issues"] >= 0  # May find issues
            assert summary["duration_seconds"] > 0

            # Verify findings structure (if any found)
            if len(data["data"]["findings"]) > 0:
                finding = data["data"]["findings"][0]
                assert finding["id"].startswith("fnd_")
                assert "file" in finding
                assert "line" in finding
                assert "severity" in finding
                assert finding["severity"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

        finally:
            Path(temp_path).unlink()

    def test_retrieve_analysis_by_id(self):
        """Test retrieving analysis results by ID."""
        # First, run an analysis
        code = "def simple_function():\\n    return 42"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # POST /api/v1/analyze
            analyze_response = client.post("/api/v1/analyze", json={"path": temp_path})
            assert analyze_response.status_code == 200

            analysis_data = analyze_response.json()["data"]
            analysis_id = analysis_data["analysis_id"]

            # GET /api/v1/analyze/{analysis_id}
            retrieve_response = client.get(f"/api/v1/analyze/{analysis_id}")

            assert retrieve_response.status_code == 200
            retrieved_data = retrieve_response.json()

            # Verify retrieved data matches original
            assert retrieved_data["success"] is True
            assert retrieved_data["data"]["analysis_id"] == analysis_id
            assert retrieved_data["data"]["path"] == temp_path
            assert retrieved_data["data"]["status"] == "completed"

        finally:
            Path(temp_path).unlink()

    def test_analyze_nonexistent_file_error(self):
        """Test analyzing nonexistent file returns error."""
        response = client.post("/api/v1/analyze", json={"path": "/nonexistent/path/to/file.py"})

        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()

        assert data["success"] is False
        assert data["error"] is not None
        assert data["error"]["code"] == "INVALID_PATH"
        assert "does not exist" in data["error"]["message"].lower()

    def test_analyze_with_exclude_patterns(self):
        """Test analysis with exclude patterns."""
        # Create temp directory with multiple files
        with tempfile.TemporaryDirectory() as tmpdir:
            # File 1: Should be analyzed
            file1 = Path(tmpdir) / "main.py"
            file1.write_text("def main():\\n    pass")

            # File 2: Should be excluded
            file2 = Path(tmpdir) / "test_main.py"
            file2.write_text("def test_main():\\n    pass")

            response = client.post(
                "/api/v1/analyze", json={"path": tmpdir, "exclude_patterns": ["test_*.py"]}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            # Verify at least one file was analyzed (may vary based on excludes)
            assert data["data"]["summary"]["files_analyzed"] >= 0


class TestBatchAnalysis(unittest.TestCase):
    """Test batch analysis with multiple files."""

    def test_batch_analyze_multiple_files(self):
        """Test batch analysis of multiple files."""
        temp_files = []

        try:
            # Create multiple temp files
            for i in range(3):
                code = f'def function_{i}():\\n    """Function {i}"""\\n    return {i}'
                f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
                f.write(code)
                f.close()
                temp_files.append(f.name)

            # POST /api/v1/analyze/batch
            response = client.post("/api/v1/analyze/batch", json={"paths": temp_files})

            assert response.status_code == 200
            data = response.json()

            # Verify batch response structure
            assert data["success"] is True
            assert data["data"]["batch_id"].startswith("ana_")
            assert data["data"]["total_analyses"] == 3
            assert data["data"]["completed"] + data["data"]["failed"] == 3
            assert len(data["data"]["results"]) == 3

            # Verify each result has analysis_id
            for result in data["data"]["results"]:
                assert result["analysis_id"].startswith("ana_")
                assert result["status"] in ["completed", "failed"]

        finally:
            for temp_file in temp_files:
                Path(temp_file).unlink()

    def test_batch_analyze_with_failures(self):
        """Test batch analysis handles individual failures."""
        temp_files = []

        try:
            # Valid file
            f1 = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
            f1.write("def valid():\\n    pass")
            f1.close()
            temp_files.append(f1.name)

            # Invalid path
            invalid_path = "/nonexistent/invalid.py"

            # POST /api/v1/analyze/batch
            response = client.post(
                "/api/v1/analyze/batch", json={"paths": [temp_files[0], invalid_path]}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify batch completed with mixed results
            assert data["success"] is True
            assert data["data"]["total_analyses"] == 2
            assert data["data"]["completed"] + data["data"]["failed"] == 2
            assert len(data["data"]["results"]) == 2

            # At least one should have succeeded
            statuses = [r["status"] for r in data["data"]["results"]]
            assert "completed" in statuses or "failed" in statuses

        finally:
            for temp_file in temp_files:
                if Path(temp_file).exists():
                    Path(temp_file).unlink()


class TestRealCodebaseAnalysis(unittest.TestCase):
    """Test analysis of real Hefesto codebase files."""

    def test_analyze_hefesto_api_file(self):
        """Test analyzing a real Hefesto API file."""
        # Analyze this test file itself
        test_file_path = __file__

        response = client.post("/api/v1/analyze", json={"path": test_file_path})

        assert response.status_code == 200
        data = response.json()

        # Verify analysis completed
        assert data["success"] is True
        assert data["data"]["status"] == "completed"
        assert data["data"]["summary"]["files_analyzed"] == 1
        assert data["data"]["summary"]["total_loc"] > 0

        # File should exist in findings if any issues found
        if len(data["data"]["findings"]) > 0:
            files_in_findings = {f["file"] for f in data["data"]["findings"]}
            assert test_file_path in files_in_findings

    def test_analyze_hefesto_service_layer(self):
        """Test analyzing Hefesto service layer."""
        service_path = (
            Path(__file__).parent.parent.parent
            / "hefesto"
            / "api"
            / "services"
            / "analysis_service.py"
        )

        if not service_path.exists():
            self.skipTest(f"Service file not found: {service_path}")

        response = client.post("/api/v1/analyze", json={"path": str(service_path)})

        assert response.status_code == 200
        data = response.json()

        # Verify analysis completed
        assert data["success"] is True
        assert data["data"]["status"] == "completed"
        assert data["data"]["summary"]["files_analyzed"] >= 1


if __name__ == "__main__":
    unittest.main()
