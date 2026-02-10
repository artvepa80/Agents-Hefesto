import json
from typing import Any, Dict, List

from ..detectors import SecretDetector
from ..finding_schema import CloudFinding, CloudLocation


class ArmAnalyzer:
    def __init__(self):
        self.name = "ArmAnalyzer"
        self.description = "Analyzes Azure Resource Manager (ARM) templates."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        findings = []
        try:
            if not file_path.endswith(".json"):
                 return []
            template = json.loads(file_content)
        except Exception:
            return []

        if not isinstance(template, dict):
            return []

        # Check Parameters
        parameters = template.get("parameters", {})
        if isinstance(parameters, dict):
            for param_name, config in parameters.items():
                if not isinstance(config, dict):
                    continue
                
                param_type = config.get("type", "").lower()
                
                # Check for sensitive defaults
                default_val = config.get("defaultValue")
                if default_val and isinstance(default_val, str):
                    if SecretDetector.is_suspicious_key(param_name):
                        findings.append(
                            CloudFinding(
                                format="ARM",
                                rule_id="ARM_S001",
                                severity="HIGH",
                                evidence=f"Parameter '{param_name}' has hardcoded defaultValue.",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Remove defaultValue. Use Key Vault reference."
                            )
                        )

                # Check for secureString usage
                if SecretDetector.is_suspicious_key(param_name) and param_type == "string":
                     findings.append(
                        CloudFinding(
                            format="ARM",
                            rule_id="ARM_S001",
                            severity="MEDIUM",
                            evidence=f"Sensitive parameter '{param_name}' uses type 'string' instead of 'secureString'.",
                            location=CloudLocation(path=file_path),
                            confidence="MEDIUM",
                            remediation="Change type to 'secureString'."
                        )
                    )

        # Check Resources (recursive scan or just top level properties?)
        # ARM resources are lists.
        resources = template.get("resources", [])
        if isinstance(resources, list):
            self._scan_resources(resources, file_path, findings)

        return findings

    def _scan_resources(self, resources: List[Dict[str, Any]], file_path: str, findings: List[CloudFinding]):
        for res in resources:
            if not isinstance(res, dict):
                continue
            
            # recursive scan of sub-resources
            sub_resources = res.get("resources", [])
            if isinstance(sub_resources, list):
                self._scan_resources(sub_resources, file_path, findings)
            
            # scan properties
            props = res.get("properties", {})
            self._scan_dict(props, file_path, findings, prefix=res.get("name", "unknown"))

    def _scan_dict(self, data: Dict[str, Any], file_path: str, findings: List[CloudFinding], prefix=""):
        for key, value in data.items():
            current_path = f"{prefix}.{key}"
            
            if isinstance(value, dict):
                self._scan_dict(value, file_path, findings, current_path)
            elif isinstance(value, str):
                if SecretDetector.is_suspicious_key(key):
                    if SecretDetector.is_hardcoded_value(value):
                        findings.append(
                            CloudFinding(
                                format="ARM",
                                rule_id="ARM_S001",
                                severity="CRITICAL",
                                evidence=f"Hardcoded secret in resource property '{current_path}'.",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Use Key Vault reference or parameters."
                            )
                        )


ANALYZERS = [ArmAnalyzer()]
