import os
from typing import Any, Dict, List

try:
    import yaml
except ImportError:
    yaml = None

from ..detectors import SecretDetector
from ..finding_schema import CloudFinding, CloudLocation


class HelmAnalyzer:
    def __init__(self):
        self.name = "HelmAnalyzer"
        self.description = "Analyzes Helm charts for secrets and best practices."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        findings = []
        filename = os.path.basename(file_path)

        # Target values.yaml and similar variants
        if not (filename == "values.yaml" or filename.startswith("values-") and filename.endswith(".yaml")):
            return []

        try:
            if yaml:
                values = yaml.safe_load(file_content)
            else:
                return []
        except Exception:
            return []

        if not isinstance(values, dict):
            return []

        self._scan_dict(values, file_path, findings)
        return findings

    def _scan_dict(self, data: Dict[str, Any], file_path: str, findings: List[CloudFinding], prefix=""):
        for key, value in data.items():
            current_path = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                self._scan_dict(value, file_path, findings, current_path)
            elif isinstance(value, str):
                if SecretDetector.is_suspicious_key(key):
                    if SecretDetector.is_hardcoded_value(value) and len(value) > 0:
                        findings.append(
                            CloudFinding(
                                format="Helm",
                                rule_id="HELM_S001",
                                severity="HIGH",
                                evidence=f"Possible hardcoded secret in '{current_path}' (key: {key}).",
                                location=CloudLocation(path=file_path),
                                confidence="MEDIUM",
                                remediation="Use secrets management (e.g. external-secrets) or value references."
                            )
                        )
                
                # Also check value content for critical patterns regardless of key name
                critical_matches = SecretDetector.check_value(value)
                if critical_matches:
                    for match in critical_matches:
                        findings.append(
                            CloudFinding(
                                format="Helm",
                                rule_id="HELM_S001",
                                severity="CRITICAL",
                                evidence=f"Critical secret pattern found in '{current_path}': {match}",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Revoke and rotate secret immediately."
                            )
                        )


ANALYZERS = [HelmAnalyzer()]
