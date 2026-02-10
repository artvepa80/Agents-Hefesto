from typing import List

from ..finding_schema import CloudFinding


class HelmNoopAnalyzer:
    def __init__(self):
        self.name = "HelmNoopAnalyzer"
        self.description = "A no-operation analyzer for Helm charts."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        # This analyzer does nothing, just verifies registration
        return []


ANALYZERS = [HelmNoopAnalyzer()]
