from typing import List

from ..finding_schema import CloudFinding


class CloudFormationNoopAnalyzer:
    def __init__(self):
        self.name = "CloudFormationNoopAnalyzer"
        self.description = "A no-operation analyzer for CloudFormation templates."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        # This analyzer does nothing, just verifies registration
        return []


ANALYZERS = [CloudFormationNoopAnalyzer()]
