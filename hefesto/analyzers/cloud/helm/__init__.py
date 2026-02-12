import os
from typing import Any, List

try:
    import yaml
except ImportError:
    yaml = None

from ..detectors import SecretDetector
from ..finding_schema import CloudFinding, CloudLocation


class HelmAnalyzer:
    def __init__(self):
        self.name = "HelmAnalyzer"  # type: ignore
        self.description = "Analyzes Helm charts for secrets and best practices."

    def analyze(self, file_content: str, file_path: str) -> List[CloudFinding]:
        findings: List[Any] = []
        filename = os.path.basename(file_path)

        # Target values.yaml and variants (yml/yaml)
        if not (
            filename == "values.yaml"
            or filename == "values.yml"
            or (
                filename.startswith("values-")
                and (filename.endswith(".yaml") or filename.endswith(".yml"))
            )
        ):
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

        self._scan_recursive(values, file_path, findings)
        self._check_insecure_defaults(values, file_path, findings)
        return findings

    def _scan_recursive(self, data: Any, file_path: str, findings: List[CloudFinding], prefix=""):
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{prefix}.{key}" if prefix else key
                # Check Key + Value (HIGH) vs Value Pattern (CRITICAL)
                if isinstance(value, str):
                    self._check_value(key, value, current_path, file_path, findings)
                else:
                    self._scan_recursive(value, file_path, findings, current_path)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{prefix}[{i}]"
                self._scan_recursive(item, file_path, findings, current_path)

    def _check_value(
        self, key: str, value: str, path_str: str, file_path: str, findings: List[CloudFinding]
    ):
        # Strategy: CRITICAL overrides HIGH
        # If value matches critical pattern -> CRITICAL finding only.
        # Else if key is suspicious -> HIGH finding.

        critical_matches = SecretDetector.check_value(value)
        if critical_matches:
            for match in critical_matches:
                findings.append(
                    CloudFinding(
                        format="helm",
                        rule_id="HELM_S001",
                        severity="CRITICAL",
                        evidence=f"Critical secret pattern found in '{path_str}': {match}",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Revoke and rotate secret immediately.",
                    )
                )
            # Stop here to avoid double finding for the same value
            return

        if SecretDetector.is_suspicious_key(key):
            if SecretDetector.is_hardcoded_value(value) and len(value) > 0:
                findings.append(
                    CloudFinding(
                        format="helm",
                        rule_id="HELM_S001",
                        severity="HIGH",
                        evidence=f"Possible hardcoded secret in '{path_str}' (key: {key}).",
                        location=CloudLocation(path=file_path),
                        confidence="MEDIUM",
                        remediation=(
                            "Use secrets management (e.g. external-secrets) or value references."
                        ),
                    )
                )

    def _check_insecure_defaults(
        self, data: Any, file_path: str, findings: List[CloudFinding], current_path: str = ""
    ):
        from ..detectors_insecure_defaults import InsecureDefaultsDetector

        if isinstance(data, dict):
            # 1. Host Namespaces
            if data.get("hostPID") is True:
                findings.append(
                    CloudFinding(
                        format="helm",
                        rule_id="HELM_I001",
                        severity="HIGH",
                        evidence=f"hostPID: true found at '{current_path}.hostPID'",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Set hostPID to false.",
                    )
                )
            if data.get("hostIPC") is True:
                findings.append(
                    CloudFinding(
                        format="helm",
                        rule_id="HELM_I001",
                        severity="HIGH",
                        evidence=f"hostIPC: true found at '{current_path}.hostIPC'",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Set hostIPC to false.",
                    )
                )
            if data.get("hostNetwork") is True:
                findings.append(
                    CloudFinding(
                        format="helm",
                        rule_id="HELM_I001",
                        severity="HIGH",
                        evidence=f"hostNetwork: true found at '{current_path}.hostNetwork'",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Set hostNetwork to false.",
                    )
                )

            # 2. Security Context & Container Security
            # Check keys regardless of nesting (PodSecurityContext or SecurityContext)
            if data.get("privileged") is True:
                findings.append(
                    CloudFinding(
                        format="helm",
                        rule_id="HELM_I001",
                        severity="CRITICAL",
                        evidence=f"privileged: true found at '{current_path}.privileged'",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Remove privileged flag.",
                    )
                )

            if data.get("allowPrivilegeEscalation") is True:
                findings.append(
                    CloudFinding(
                        format="helm",
                        rule_id="HELM_I001",
                        severity="MEDIUM",
                        evidence=(
                            f"allowPrivilegeEscalation: true found at "
                            f"'{current_path}.allowPrivilegeEscalation'"
                        ),
                        location=CloudLocation(path=file_path),
                        confidence="MEDIUM",
                        remediation="Set allowPrivilegeEscalation to false.",
                    )
                )

            run_as_user = data.get("runAsUser")
            if isinstance(run_as_user, int) and run_as_user == 0:
                findings.append(
                    CloudFinding(
                        format="helm",
                        rule_id="HELM_I001",
                        severity="HIGH",
                        evidence=f"runAsUser: 0 (root) found at '{current_path}.runAsUser'",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Run as non-root user.",
                    )
                )

            # 3. LoadBalancer Source Ranges
            # ... (Resource checking - Service)
            svc_type = data.get("type")
            if svc_type == "LoadBalancer":
                # Check directly in current dict (if it is a Service spec)
                ranges = data.get("loadBalancerSourceRanges", [])
                if ranges:
                    for r in ranges:
                        if InsecureDefaultsDetector.is_public_cidr(r):
                            findings.append(
                                CloudFinding(
                                    format="helm",
                                    rule_id="HELM_I001",
                                    severity="HIGH",
                                    evidence=f"LoadBalancer allows public access: {r}",
                                    location=CloudLocation(path=file_path),
                                    confidence="HIGH",
                                    remediation="Restrict loadBalancerSourceRanges.",
                                )
                            )

            # Recurse
            for key, value in data.items():
                self._check_insecure_defaults(value, file_path, findings, f"{current_path}.{key}")

        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._check_insecure_defaults(item, file_path, findings, f"{current_path}[{i}]")


ANALYZERS = [HelmAnalyzer()]
