import os
from typing import Any, Dict, List

try:
    import yaml
except ImportError:
    yaml = None

from ..detectors import SecretDetector
from ..finding_schema import CloudFinding, CloudLocation


class ServerlessAnalyzer:
    def __init__(self):
        self.name = "ServerlessAnalyzer"
        self.description = "Analyzes Serverless Framework configurations."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        findings = []
        if not file_path.endswith("serverless.yml") and not file_path.endswith("serverless.yaml"):
            return []

        try:
            if yaml:
                config = yaml.safe_load(file_content)
            else:
                return []
        except Exception:
            return []

        if not isinstance(config, dict):
            return []

        # Check provider.environment
        provider = config.get("provider", {})
        if isinstance(provider, dict):
            env_vars = provider.get("environment", {})
            self._scan_env_vars(env_vars, file_path, findings, "provider.environment")

        # Check functions.*.environment
        functions = config.get("functions", {})
        if isinstance(functions, dict):
            for func_name, func_def in functions.items():
                if isinstance(func_def, dict):
                    env_vars = func_def.get("environment", {})
                    self._scan_env_vars(env_vars, file_path, findings, f"functions.{func_name}.environment")

        return findings

    def _scan_env_vars(self, env_vars: Dict[str, Any], file_path: str, findings: List[CloudFinding], context: str):
        if not isinstance(env_vars, dict):
            return

        for key, value in env_vars.items():
            if isinstance(value, str):
                if SecretDetector.is_suspicious_key(key):
                    if SecretDetector.is_hardcoded_value(value) and len(value) > 0:
                        findings.append(
                            CloudFinding(
                                format="Serverless",
                                rule_id="SLS_S001",
                                severity="HIGH",
                                evidence=f"Possible hardcoded secret in '{context}' (key: {key}).",
                                location=CloudLocation(path=file_path),
                                confidence="MEDIUM",
                                remediation="Use SSM parameters or environment variable references (${env:...})."
                            )
                        )
                
                # Check for critical patterns in value
                critical_matches = SecretDetector.check_value(value)
                if critical_matches:
                    for match in critical_matches:
                         findings.append(
                            CloudFinding(
                                format="Serverless",
                                rule_id="SLS_S001",
                                severity="CRITICAL",
                                evidence=f"Critical secret pattern found in '{context}': {match}",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Revoke secret. Use SSM/Secrets Manager."
                            )
                        )


ANALYZERS = [ServerlessAnalyzer()]
