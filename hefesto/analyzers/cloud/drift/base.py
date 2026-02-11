from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..finding_schema import CloudFinding


@dataclass
class DriftContext:
    """Context for drift detection, holding credentials and target scope."""

    region: str
    template_path: str = "unknown"
    account_id: Optional[str] = None
    credentials: Optional[Any] = None  # e.g. boto3 session
    # For PoC, we might pass a simple dict of resource_id_mapping
    # e.g. {"MySG": "sg-12345678"}
    resource_map: Optional[Dict[str, str]] = None
    stack_name: Optional[str] = None
    tags: Optional[Dict[str, str]] = None

    # NEW: optional resolver (Patch K)
    resolver: Optional[Any] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = {}
        if self.resource_map is None:
            self.resource_map = {}


class DriftAnalyzer(ABC):
    """Abstract base class for cloud drift analyzers."""

    @abstractmethod
    def detect_drift(self, template: Dict[str, Any], context: DriftContext) -> List[CloudFinding]:
        """
        Detect discrepancies between the IaC template and live cloud resources.

        Args:
            template: The parsed IaC template (e.g. CloudFormation dict)
            context: Execution context containing credentials and scope

        Returns:
            List of findings describing drift (Missing, Unexpected, Mismatch)
        """
        pass
