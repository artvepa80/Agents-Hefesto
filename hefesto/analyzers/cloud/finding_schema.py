from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CloudLocation:
    path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None


@dataclass(frozen=True)
class CloudFinding:
    format: str  # e.g., "CloudFormation", "Helm", "ARM", "Serverless"
    rule_id: str  # e.g., "CFN001", "HELM002"
    severity: str  # "INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"
    evidence: str  # Fragment of code or description justifying the finding
    location: CloudLocation
    confidence: str  # "LOW", "MEDIUM", "HIGH"
    remediation: str  # Guide or suggestion to fix
    metadata: Optional[Dict[str, Any]] = None  # For additional info
