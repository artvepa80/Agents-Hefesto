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
        self.name = "CloudFormationAnalyzer"  # type: ignore
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
                return []
        except Exception:
            return []

        if not isinstance(template, dict):
            return []

        findings.extend(self._check_secrets(template, file_path))
        findings.extend(self._check_insecure_defaults(template, file_path))
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
                                format="cloudformation",
                                rule_id="CFN_S001",
                                severity="HIGH",
                                evidence=f"Parameter '{param_name}' has hardcoded default value.",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation=(
                                    "Remove default value or use NoEcho: true."
                                ),  # noqa: E501
                            )
                        )

                # Check NoEcho usage
                # Only signal if suspicious AND (has default OR is explicitly typed as String/sensitive)  # noqa: E501
                # User guidance: "param is suspicious and (it has a Default or Type indicates it’s secret-like)"  # noqa: E501
                is_no_echo = config.get("NoEcho")
                if str(is_no_echo).lower() == "true":
                    continue

                if SecretDetector.is_suspicious_key(param_name):
                    # refine: ensure we don't flag harmless params unless they really look like secrets  # noqa: E501
                    # For CFN, Type: String is common. We rely on the name + context.
                    # If it has a Default, it's definitely risky if it's a password.
                    # If it doesn't have a default, but is named "DBPassword", it should be NoEcho.

                    findings.append(
                        CloudFinding(
                            format="cloudformation",
                            rule_id="CFN_S001",
                            severity="MEDIUM",
                            evidence=f"Sensitive parameter '{param_name}' missing NoEcho: true.",
                            location=CloudLocation(path=file_path),
                            confidence="MEDIUM",
                            remediation="Add 'NoEcho: true' to parameter definition.",
                        )
                    )

        # 2. Check Resources (recursive)
        resources = template.get("Resources", {})
        if isinstance(resources, dict):
            for res_name, res_def in resources.items():
                if not isinstance(res_def, dict):
                    continue

                # Recursive walk of the resource definition
                self._scan_resource_recursive(res_def, file_path, findings, f"Resources.{res_name}")

        return findings

    def _scan_resource_recursive(
        self, data: Any, file_path: str, findings: List[CloudFinding], current_path: str
    ):
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{current_path}.{key}"
                if isinstance(value, str):
                    # Check value
                    if SecretDetector.is_suspicious_key(key) and SecretDetector.is_hardcoded_value(
                        value
                    ):
                        findings.append(
                            CloudFinding(
                                format="cloudformation",
                                rule_id="CFN_S001",
                                severity="CRITICAL",
                                evidence=f"Resource property '{new_path}' has hardcoded value.",
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation=(
                                    "Use dynamic reference ({{resolve:secretsmanager:...}}) "
                                    "or Ref to parameter."
                                ),
                            )
                        )

                    # Also check for critical patterns in value regardless of key
                    critical_matches = SecretDetector.check_value(value)
                    if critical_matches:
                        for match in critical_matches:
                            findings.append(
                                CloudFinding(
                                    format="cloudformation",
                                    rule_id="CFN_S001",
                                    severity="CRITICAL",
                                    evidence=(
                                        f"Critical secret pattern found in '{new_path}': {match}"
                                    ),
                                    location=CloudLocation(path=file_path),
                                    confidence="HIGH",
                                    remediation="Revoke and rotate secret immediately.",
                                )
                            )
                else:
                    self._scan_resource_recursive(value, file_path, findings, new_path)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._scan_resource_recursive(item, file_path, findings, f"{current_path}[{i}]")

    def _check_insecure_defaults(
        self, template: Dict[str, Any], file_path: str
    ) -> List[CloudFinding]:
        findings: List[CloudFinding] = []

        resources = template.get("Resources", {})
        if not isinstance(resources, dict):
            return findings

        from ..detectors_insecure_defaults import InsecureDefaultsDetector

        for res_name, res_def in resources.items():
            if not isinstance(res_def, dict):
                continue

            res_type = res_def.get("Type")
            props = res_def.get("Properties", {})
            if not isinstance(props, dict):
                continue

            if res_type == "AWS::EC2::SecurityGroup":
                self._check_security_group(
                    res_name, props, file_path, findings, InsecureDefaultsDetector
                )
            elif res_type == "AWS::EC2::SecurityGroupIngress":
                self._check_security_group_ingress(
                    res_name, props, file_path, findings, InsecureDefaultsDetector
                )
            elif res_type == "AWS::S3::Bucket":
                self._check_s3_bucket(res_name, props, file_path, findings)
            elif res_type in ("AWS::IAM::Policy", "AWS::IAM::ManagedPolicy"):
                self._check_iam_policy(res_name, props, file_path, findings)

        return findings

    def _check_security_group(
        self,
        res_name: str,
        props: Dict[str, Any],
        file_path: str,
        findings: List[CloudFinding],
        detector,
    ):
        ingress = props.get("SecurityGroupIngress", [])
        if isinstance(ingress, list):
            for idx, rule in enumerate(ingress):
                if not isinstance(rule, dict):
                    continue
                self._check_ingress_rule(
                    rule,
                    file_path,
                    findings,
                    detector,
                    f"Resources.{res_name}.Properties.SecurityGroupIngress[{idx}]",
                )

    def _check_security_group_ingress(
        self,
        res_name: str,
        props: Dict[str, Any],
        file_path: str,
        findings: List[CloudFinding],
        detector,
    ):
        # Standalone ingress rule is a flat dictionary of properties
        self._check_ingress_rule(
            props, file_path, findings, detector, f"Resources.{res_name}.Properties"
        )

    def _check_ingress_rule(
        self,
        rule: Dict[str, Any],
        file_path: str,
        findings: List[CloudFinding],
        detector,
        location_desc: str,
    ):
        cidr = rule.get("CidrIp") or rule.get("CidrIpv6")
        ip_protocol = rule.get("IpProtocol")
        from_port = rule.get("FromPort")
        to_port = rule.get("ToPort")

        if isinstance(cidr, str) and detector.is_public_cidr(cidr):
            sensitive = False
            # "-1" means all protocols
            if str(ip_protocol) == "-1":
                sensitive = True
            else:
                if detector.is_sensitive_port(from_port) or detector.is_sensitive_port(to_port):
                    sensitive = True

            if sensitive:
                findings.append(
                    CloudFinding(
                        format="cloudformation",
                        rule_id="CFN_I001",
                        severity="CRITICAL",
                        evidence=(
                            f"Public SG ingress on sensitive port(s) at {location_desc} ({cidr})."
                        ),
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation=(
                            "Restrict CIDR ranges and avoid exposing sensitive "
                            "ports to the internet."
                        ),
                    )
                )

    def _check_s3_bucket(
        self, res_name: str, props: Dict[str, Any], file_path: str, findings: List[CloudFinding]
    ):
        pab = props.get("PublicAccessBlockConfiguration")
        # If missing, or any required block is false -> risky
        if not isinstance(pab, dict):
            findings.append(
                CloudFinding(
                    format="cloudformation",
                    rule_id="CFN_I001",
                    severity="HIGH",
                    evidence=(
                        f"S3 Bucket missing PublicAccessBlockConfiguration at Resources.{res_name}.Properties."  # noqa: E501
                    ),
                    location=CloudLocation(path=file_path),
                    confidence="MEDIUM",
                    remediation=(
                        "Add PublicAccessBlockConfiguration and ensure "
                        "public ACLs/policies are blocked."
                    ),  # noqa: E501
                )
            )
        else:
            required = [
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            ]
            for k in required:
                v = pab.get(k)
                if str(v).lower() != "true":
                    findings.append(
                        CloudFinding(
                            format="cloudformation",
                            rule_id="CFN_I001",
                            severity="HIGH",
                            evidence=(
                                f"S3 PublicAccessBlockConfiguration '{k}' is not true at "
                                f"Resources.{res_name}.Properties.PublicAccessBlockConfiguration."
                            ),
                            location=CloudLocation(path=file_path),
                            confidence="MEDIUM",
                            remediation=("Set all PublicAccessBlockConfiguration flags to true."),
                        )
                    )
                    break

    def _check_iam_policy(
        self, res_name: str, props: Dict[str, Any], file_path: str, findings: List[CloudFinding]
    ):
        policy_doc = props.get("PolicyDocument")
        if isinstance(policy_doc, dict):
            stmts = policy_doc.get("Statement", [])
            if isinstance(stmts, dict):
                stmts = [stmts]
            if isinstance(stmts, list):
                for idx, st in enumerate(stmts):
                    if not isinstance(st, dict):
                        continue
                    actions = st.get("Action")
                    resources_ = st.get("Resource")

                    if self._has_star(actions) and self._has_star(resources_):
                        findings.append(
                            CloudFinding(
                                format="cloudformation",
                                rule_id="CFN_I001",
                                severity="CRITICAL",
                                evidence=(
                                    f"IAM policy allows Action:* and Resource:* at "
                                    f"Resources.{res_name}.Properties.PolicyDocument."
                                    f"Statement[{idx}]."
                                ),
                                location=CloudLocation(path=file_path),
                                confidence="HIGH",
                                remediation=(
                                    "Scope IAM permissions to least privilege "
                                    "(specific actions/resources)."
                                ),
                            )
                        )

    def _has_star(self, x: Any) -> bool:
        if x == "*" or x == ["*"]:
            return True
        if isinstance(x, list):
            return any(a == "*" for a in x)
        return False


ANALYZERS = [CloudFormationAnalyzer()]
