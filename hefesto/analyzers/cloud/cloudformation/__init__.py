import json
from typing import Any, Dict, List

try:
    import yaml
except ImportError:
    yaml = None

from ..detectors import SecretDetector
from ..finding_schema import CloudFinding, CloudLocation


class CloudFormationAnalyzer:
    def __init__(self):
        self.name = "CloudFormationAnalyzer"
        self.description = "Analyzes CloudFormation templates for secrets and misconfigurations."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        findings = []
        try:
            # Parse template (YAML or JSON)
            if file_path.endswith(".json"):
                template = json.loads(file_content)
            elif yaml:
                template = yaml.safe_load(file_content)
            else:
                # If no yaml parser, try simple json or skip
                return []
        except Exception:
            # Skip invalid templates for now
            return []

        if not isinstance(template, dict):
            return []

        findings.extend(self._check_secrets(template, file_path))
        return findings

    def _check_secrets(self, template: Dict[str, Any], file_path: str) -> List[CloudFinding]:
        findings = []
        
        # 1. Check Parameters
        parameters = template.get("Parameters", {})
        if isinstance(parameters, dict):
            for param_name, config in parameters.items():
                if not isinstance(config, dict):
                    continue
                
                # Check for sensitive defaults
                default_val = config.get("Default")
                if default_val and isinstance(default_val, str):
                    if SecretDetector.is_suspicious_key(param_name):
                        findings.append(
                            CloudFinding(
                                format="CloudFormation",
                                rule_id="CFN_S001",
                                severity="HIGH",
                                evidence=f"Parameter '{param_name}' has hardcoded default value.",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Remove default value or use NoEcho: true."
                            )
                        )

                # Check NoEcho usage
                is_no_echo = config.get("NoEcho")
                if str(is_no_echo).lower() == "true":
                    continue
                
                if SecretDetector.is_suspicious_key(param_name):
                     findings.append(
                        CloudFinding(
                            format="CloudFormation",
                            rule_id="CFN_S001",
                            severity="MEDIUM",
                            evidence=f"Sensitive parameter '{param_name}' missing NoEcho: true.",
                            location=CloudLocation(path=file_path),
                            confidence="MEDIUM",
                            remediation="Add 'NoEcho: true' to parameter definition."
                        )
                    )

        # 2. Check Resources properties (recursive or shallow?)
        # For sprint 1: Shallow check of Resource Properties values
        resources = template.get("Resources", {})
        if isinstance(resources, dict):
            for res_name, res_def in resources.items():
                if not isinstance(res_def, dict):
                    continue
                props = res_def.get("Properties", {})
                if not isinstance(props, dict):
                    continue
                
                for key, value in props.items():
                    if isinstance(value, str):
                        # Use detector
                        if SecretDetector.is_suspicious_key(key) and SecretDetector.is_hardcoded_value(value):
                             findings.append(
                                CloudFinding(
                                    format="CloudFormation",
                                    rule_id="CFN_S001",
                                    severity="CRITICAL",
                                    evidence=f"Resource '{res_name}' property '{key}' has hardcoded value.",
                                    location=CloudLocation(path=file_path),
                                    confidence="HIGH",
                                    remediation="Use dynamic reference ({{resolve:secretsmanager:...}}) or Ref to parameter."
                                )
                            )

        return findings


ANALYZERS = [CloudFormationAnalyzer()]
