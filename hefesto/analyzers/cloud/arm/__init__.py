from typing import List

from ..finding_schema import CloudFinding


class ArmNoopAnalyzer:
    def __init__(self):
        self.name = "ArmNoopAnalyzer"
        self.description = "A no-operation analyzer for ARM templates."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        # This analyzer does nothing, just verifies registration
        return []


ANALYZERS = [ArmNoopAnalyzer()]
