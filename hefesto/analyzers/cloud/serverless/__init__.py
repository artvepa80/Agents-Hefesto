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
        filename = os.path.basename(file_path)

        if filename not in ("serverless.yml", "serverless.yaml"):
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
                    self._scan_env_vars(
                        env_vars, file_path, findings, f"functions.{func_name}.environment"
                    )

        # Check IAM Roles
        self._scan_iam_roles(config, file_path, findings)

        return findings

    def _scan_env_vars(
        self, env_vars: Dict[str, Any], file_path: str, findings: List[CloudFinding], context: str
    ):
        if not isinstance(env_vars, dict):
            return

        for key, value in env_vars.items():
            if isinstance(value, str):
                # Deduplication logic: CRITICAL overrides HIGH
                critical_matches = SecretDetector.check_value(value)

                if critical_matches:
                    for match in critical_matches:
                        findings.append(
                            CloudFinding(
                                format="serverless",
                                rule_id="SLS_S001",
                                severity="CRITICAL",
                                evidence=f"Critical secret pattern found in '{context}': {match}",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Revoke secret. Use SSM/Secrets Manager.",
                            )
                        )
                    continue

                if SecretDetector.is_suspicious_key(key):
                    if SecretDetector.is_hardcoded_value(value) and len(value) > 0:
                        findings.append(
                            CloudFinding(
                                format="serverless",
                                rule_id="SLS_S001",
                                severity="HIGH",
                                evidence=f"Possible hardcoded secret in '{context}' (key: {key}).",
                                location=CloudLocation(path=file_path),
                                confidence="MEDIUM",
                                remediation="Use SSM parameters or environment variable references (${env:...}).",
                            )
                        )

    def _scan_iam_roles(self, data: Dict[str, Any], file_path: str, findings: List[CloudFinding]):
        """Scan provider.iam.role.statements and functions.*.iamRoleStatements"""
        # 1. Provider-wide IAM
        provider = data.get("provider", {})
        if isinstance(provider, dict):
            iam = provider.get("iam", {})
            if isinstance(iam, dict):
                role = iam.get("role", {})
                if isinstance(role, dict):
                    statements = role.get("statements", [])
                    self._check_iam_statements(
                        statements, file_path, findings, "provider.iam.role.statements"
                    )

        # 2. Per-function IAM (Serverless Framework)
        functions = data.get("functions", {})
        if isinstance(functions, dict):
            for func_name, func_def in functions.items():
                if isinstance(func_def, dict):
                    statements = func_def.get("iamRoleStatements", [])
                    self._check_iam_statements(
                        statements, file_path, findings, f"functions.{func_name}.iamRoleStatements"
                    )

    def _check_iam_statements(
        self,
        statements: List[Dict[str, Any]],
        file_path: str,
        findings: List[CloudFinding],
        context: str,
    ):
        from ..detectors_insecure_defaults import InsecureDefaultsDetector

        if not isinstance(statements, list):
            return

        for idx, stmt in enumerate(statements):
            if not isinstance(stmt, dict):
                continue

            effect = stmt.get("Effect")
            if effect == "Allow":
                action = stmt.get("Action")
                resource = stmt.get("Resource")

                if InsecureDefaultsDetector.is_wildcard_permission(action, resource):
                    findings.append(
                        CloudFinding(
                            format="serverless",
                            rule_id="SLS_I001",
                            severity="CRITICAL",
                            evidence=f"IAM Statement at '{context}[{idx}]' allows Action:* on Resource:*.",
                            location=CloudLocation(path=file_path),
                            confidence="HIGH",
                            remediation="Least privilege: restrict Action and Resource.",
                        )
                    )


ANALYZERS = [ServerlessAnalyzer()]
