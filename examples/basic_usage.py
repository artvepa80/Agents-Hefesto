"""
Basic Hefesto usage (free tier).

Runs the same analyzer engine that ``hefesto analyze`` uses, on a small
sample file written to a temporary directory. No API key or AI provider
is needed: these analyzers are deterministic and run locally.

Run:
    python examples/basic_usage.py
"""

import tempfile
from pathlib import Path

from hefesto.analyzers import (
    BestPracticesAnalyzer,
    CodeSmellAnalyzer,
    ComplexityAnalyzer,
    SecurityAnalyzer,
)
from hefesto.core.analyzer_engine import AnalyzerEngine

SAMPLE = """\
import subprocess

PASSWORD = "hardcoded-password-123"


def run(cmd):
    try:
        return subprocess.call(cmd, shell=True)
    except:
        return None
"""


def main() -> None:
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    engine.register_analyzer(ComplexityAnalyzer())
    engine.register_analyzer(CodeSmellAnalyzer())
    engine.register_analyzer(SecurityAnalyzer())
    engine.register_analyzer(BestPracticesAnalyzer())

    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "sample.py"
        sample.write_text(SAMPLE, encoding="utf-8")
        report = engine.analyze_path(tmp)

    summary = report.summary
    print(f"Files analyzed: {summary.files_analyzed}")
    print(
        f"Issues: {summary.total_issues} "
        f"(critical {summary.critical_issues}, high {summary.high_issues}, "
        f"medium {summary.medium_issues}, low {summary.low_issues})"
    )
    for file_result in report.file_results:
        for issue in file_result.issues:
            print(
                f"  [{issue.severity.value}] {issue.issue_type.value} "
                f"line {issue.line}: {issue.message}"
            )

    print("\nSame analysis from the CLI: hefesto analyze <path> --severity LOW")


if __name__ == "__main__":
    main()
