"""
JSON Reporter

Generates machine-readable JSON output for programmatic consumption.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import json
from typing import Any, Dict

from hefesto.core.analysis_models import AnalysisReport


class JSONReporter:
    """Generates JSON reports."""

    def generate(self, report: AnalysisReport) -> str:
        """
        Generate JSON report.

        Args:
            report: AnalysisReport to format

        Returns:
            JSON string
        """
        return json.dumps(report.to_dict(), indent=2)

    def generate_dict(self, report: AnalysisReport) -> Dict[str, Any]:
        """
        Generate report as dictionary (for API responses).

        Args:
            report: AnalysisReport to format

        Returns:
            Dictionary representation
        """
        return report.to_dict()


__all__ = ["JSONReporter"]
