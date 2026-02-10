from typing import List

from ..finding_schema import CloudFinding


class ServerlessNoopAnalyzer:
    def __init__(self):
        self.name = "ServerlessNoopAnalyzer"
        self.description = "A no-operation analyzer for Serverless Framework."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        # This analyzer does nothing, just verifies registration
        return []


ANALYZERS = [ServerlessNoopAnalyzer()]
