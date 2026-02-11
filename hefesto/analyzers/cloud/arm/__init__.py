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

                # Check for sensitive defaults (HIGH)
                default_val = config.get("defaultValue")
                if default_val and isinstance(default_val, str):
                    if SecretDetector.is_suspicious_key(param_name):
                        findings.append(
                            CloudFinding(
                                format="arm",
                                rule_id="ARM_S001",
                                severity="HIGH",
                                evidence=f"Parameter '{param_name}' has hardcoded defaultValue.",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Remove defaultValue. Use Key Vault reference.",
                            )
                        )

                # Check for secureString usage (MEDIUM)
                if SecretDetector.is_suspicious_key(param_name) and param_type == "string":
                    findings.append(
                        CloudFinding(
                            format="arm",
                            rule_id="ARM_S001",
                            severity="MEDIUM",
                            evidence=f"Sensitive parameter '{param_name}' uses type 'string' instead of 'secureString'.",  # noqa: E501
                            location=CloudLocation(path=file_path),
                            confidence="MEDIUM",
                            remediation="Change type to 'secureString'.",
                        )
                    )

        # Check Resources (recursive scan or just top level properties?)
        resources = template.get("resources", [])
        if isinstance(resources, list):
            self._scan_resources(resources, file_path, findings)
            self._check_insecure_defaults(resources, file_path, findings)

        return findings

    def _check_insecure_defaults(
        self, resources: List[Dict[str, Any]], file_path: str, findings: List[CloudFinding]
    ):

        for res in resources:
            if not isinstance(res, dict):
                continue

            res_type = res.get("type", "")
            props = res.get("properties", {})

            # Recursive check for sub-resources
            sub_resources = res.get("resources", [])
            if isinstance(sub_resources, list):
                self._check_insecure_defaults(sub_resources, file_path, findings)

            # 1. Network Security Groups
            if res_type == "Microsoft.Network/networkSecurityGroups":
                security_rules = props.get("securityRules", [])
                for rule in security_rules:
                    self._check_nsg_rule(rule, file_path, findings, res.get("name", "nsg"))

            # 2. Storage Accounts
            elif res_type == "Microsoft.Storage/storageAccounts":
                # Check allowBlobPublicAccess (default is null/true in older API versions, modern is false)  # noqa: E501
                # But if explicitly true -> HIGH
                # Also check publicNetworkAccess (Enabled/Disabled)

                allow_blob = props.get("allowBlobPublicAccess")
                if allow_blob is True:  # Explicitly true
                    findings.append(
                        CloudFinding(
                            format="arm",
                            rule_id="ARM_I001",
                            severity="HIGH",
                            evidence=f"Storage Account '{res.get('name')}' has allowBlobPublicAccess set to true.",  # noqa: E501
                            location=CloudLocation(path=file_path),
                            confidence="HIGH",
                            remediation="Set allowBlobPublicAccess to false.",
                        )
                    )

                # Check publicNetworkAccess (if 'Enabled' and no firewall rules -> risky), simplified for v1  # noqa: E501
                network_acls = props.get("networkAcls", {})
                default_action = network_acls.get("defaultAction")
                if default_action == "Allow":
                    findings.append(
                        CloudFinding(
                            format="arm",
                            rule_id="ARM_I001",
                            severity="MEDIUM",
                            evidence=f"Storage Account '{res.get('name')}' allows default public access (networkAcls.defaultAction: Allow).",  # noqa: E501
                            location=CloudLocation(path=file_path),
                            confidence="MEDIUM",
                            remediation="Set defaultAction to Deny and use VNet rules.",
                        )
                    )

    def _check_nsg_rule(
        self,
        rule_wrapper: Dict[str, Any],
        file_path: str,
        findings: List[CloudFinding],
        nsg_name: str,
    ):
        # NSG rules are often wrapped in properties
        props = rule_wrapper.get("properties", {})
        name = rule_wrapper.get("name", "unknown")

        from ..detectors_insecure_defaults import InsecureDefaultsDetector

        access = props.get("access")
        direction = props.get("direction")

        if access == "Allow" and direction == "Inbound":
            source = props.get("sourceAddressPrefix")
            dest_port = props.get("destinationPortRange")  # Could be "*" or "22" or "80-81"

            if InsecureDefaultsDetector.is_public_cidr(source):
                if InsecureDefaultsDetector.is_sensitive_port(dest_port):
                    findings.append(
                        CloudFinding(
                            format="arm",
                            rule_id="ARM_I001",
                            severity="CRITICAL",
                            evidence=f"NSG Rule '{nsg_name}/{name}' allows public access ({source}) to sensitive port ({dest_port}).",  # noqa: E501
                            location=CloudLocation(path=file_path),
                            confidence="HIGH",
                            remediation="Restrict sourceAddressPrefix.",
                        )
                    )

    def _scan_resources(
        self, resources: List[Dict[str, Any]], file_path: str, findings: List[CloudFinding]
    ):
        for res in resources:
            if not isinstance(res, dict):
                continue

            sub_resources = res.get("resources", [])
            if isinstance(sub_resources, list):
                self._scan_resources(sub_resources, file_path, findings)

            props = res.get("properties", {})
            self._scan_dict(props, file_path, findings, prefix=res.get("name", "unknown"))

    def _scan_dict(
        self, data: Dict[str, Any], file_path: str, findings: List[CloudFinding], prefix=""
    ):
        for key, value in data.items():
            current_path = f"{prefix}.{key}"

            if isinstance(value, dict):
                self._scan_dict(value, file_path, findings, current_path)
            elif isinstance(value, str):
                # Deduplication: check critical pattern first
                critical_matches = SecretDetector.check_value(value)
                if critical_matches:
                    for match in critical_matches:
                        findings.append(
                            CloudFinding(
                                format="arm",
                                rule_id="ARM_S001",
                                severity="CRITICAL",
                                evidence=f"Critical secret pattern found in '{current_path}': {match}",  # noqa: E501
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Revoke secret. Use Key Vault.",
                            )
                        )
                    continue

                if SecretDetector.is_suspicious_key(key):
                    if SecretDetector.is_hardcoded_value(value):
                        findings.append(
                            CloudFinding(
                                format="arm",
                                rule_id="ARM_S001",
                                severity="CRITICAL",
                                evidence=f"Hardcoded secret in resource property '{current_path}'.",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation="Use Key Vault reference or parameters.",
                            )
                        )


ANALYZERS = [ArmAnalyzer()]
