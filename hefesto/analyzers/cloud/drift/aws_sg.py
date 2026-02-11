from typing import Any, Dict, List, Set, Tuple

from ..detectors_insecure_defaults import InsecureDefaultsDetector
from ..finding_schema import CloudFinding, CloudLocation
from .aws_client import AwsClient
from .base import DriftAnalyzer, DriftContext


class AwsSgDriftDetector(DriftAnalyzer):
    """
    Detects drift for AWS::EC2::SecurityGroup resources.
    """

    def detect_drift(self, template: Dict[str, Any], context: DriftContext) -> List[CloudFinding]:
        findings = []

        # 1. Parse Expected Rules from Template
        file_path = context.template_path or "unknown"

        expected_sgs, partial_errors = self._parse_template(template)

        if partial_errors:
            for err in partial_errors:
                findings.append(
                    CloudFinding(
                        format="cloud_drift",
                        rule_id="DRIFT_AWS_SG_PARTIAL",
                        severity="MEDIUM",
                        evidence=f"Drift check partial: {err}",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Simplify template to remove intrinsic functions for drift checking.",
                    )
                )

        if not expected_sgs:
            return findings

        # 2. Check Context credentials/mapping
        if not context.credentials:
            findings.append(
                CloudFinding(
                    format="cloud_drift",
                    rule_id="DRIFT_AWS_AUTH_SKIPPED",
                    severity="MEDIUM",
                    evidence="Drift check skipped: missing AWS credentials/session.",
                    location=CloudLocation(path=file_path),
                    confidence="HIGH",
                    remediation="Provide AWS credentials/session (boto3 Session) to enable live drift checks.",
                )
            )
            return findings

        if not context.resource_map:
            # Patch K: try auto-resolve if resolver exists
            if context.resolver is not None:
                rr = context.resolver.resolve(
                    template=template, region=context.region, credentials=context.credentials
                )
                if rr.resource_map:
                    context.resource_map = rr.resource_map  # populate and continue
                else:
                    findings.append(
                        CloudFinding(
                            format="cloud_drift",
                            rule_id="DRIFT_AWS_MAP_SKIPPED",
                            severity="MEDIUM",
                            evidence="Drift check skipped: missing resource_map and resolver could not resolve.",
                            location=CloudLocation(path=file_path),
                            confidence="HIGH",
                            remediation="Provide resource_map or configure resolver (stack name / tags / name heuristics).",
                        )
                    )
                    return findings
            else:
                findings.append(
                    CloudFinding(
                        format="cloud_drift",
                        rule_id="DRIFT_AWS_MAP_SKIPPED",
                        severity="MEDIUM",
                        evidence="Drift check skipped: missing resource_map.",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Provide a resource mapping or enable auto-resolution.",
                    )
                )
                return findings

        client = AwsClient(region=context.region, credentials=context.credentials)

        target_sg_ids = list(context.resource_map.values())
        actual_sgs_raw = client.get_security_groups(group_ids=target_sg_ids)

        # Map physical ID -> actual rules
        actual_sgs_map = {}
        for sg in actual_sgs_raw:
            sg_id = sg.get("GroupId")
            if sg_id:
                actual_sgs_map[sg_id] = self._normalize_aws_rules(sg.get("IpPermissions", []))

        # 3. Compare

        for logical_id, expected_rules in expected_sgs.items():
            physical_id = context.resource_map.get(logical_id)
            if not physical_id:
                continue

            if physical_id not in actual_sgs_map:
                # Resource missing in cloud?
                findings.append(
                    CloudFinding(
                        format="cloud_drift",
                        rule_id="DRIFT_AWS_SG_NOT_FOUND",
                        severity="HIGH",
                        evidence=f"[{logical_id}] Resource mapped to {physical_id} not found in AWS.",
                        location=CloudLocation(path=file_path),
                        confidence="HIGH",
                        remediation="Verify resource exists in region.",
                    )
                )
                continue

            actual_rules = actual_sgs_map[physical_id]
            self._compare_rules(
                logical_id,
                physical_id,
                expected_rules,
                actual_rules,
                findings,
                InsecureDefaultsDetector,
                file_path,
            )

        return findings

    def _parse_template(self, template: Dict[str, Any]) -> Tuple[Dict[str, Set[Tuple]], List[str]]:
        """
        Parses CFN template. Returns (LogicalID->Rules, list of error strings)
        """
        resources = template.get("Resources", {})
        results = {}
        errors = []

        for res_name, res_def in resources.items():
            if res_def.get("Type") == "AWS::EC2::SecurityGroup":
                props = res_def.get("Properties", {})
                ingress = props.get("SecurityGroupIngress", [])

                try:
                    results[res_name] = self._normalize_cfn_rules(ingress)
                except ValueError as e:
                    errors.append(f"Resource {res_name}: {str(e)}")

        return results, errors

    def _normalize_cfn_rules(self, rules: List[Dict[str, Any]]) -> Set[Tuple]:
        normalized = set()
        for rule in rules:
            if not isinstance(rule, dict):
                raise ValueError("Ingress rule is not a dict (intrinsics not supported)")

            # Naive check for intrinsics
            for k, v in rule.items():
                if k.startswith("Fn::") or k == "Ref":
                    raise ValueError("Intrinsic functions in Ingress not supported")
                if isinstance(v, dict):
                    raise ValueError(
                        f"Intrinsic functions in Ingress value for '{k}' not supported"
                    )

            proto = str(rule.get("IpProtocol", "-1"))
            from_p = rule.get("FromPort", -1)
            to_p = rule.get("ToPort", -1)
            cidr4 = rule.get("CidrIp")
            cidr6 = rule.get("CidrIpv6")
            src_sg = rule.get("SourceSecurityGroupId")

            if proto == "-1":
                from_p = -1
                to_p = -1

            entry = (proto, from_p, to_p, cidr4, cidr6, src_sg)
            normalized.add(entry)

        return normalized

    def _normalize_aws_rules(self, ip_permissions: List[Dict[str, Any]]) -> Set[Tuple]:
        normalized = set()
        for perm in ip_permissions:
            proto = perm.get("IpProtocol", "-1")
            from_p = perm.get("FromPort", -1)
            to_p = perm.get("ToPort", -1)

            # Helper to safely cast ports to int if they come as string
            try:
                from_p = int(from_p) if from_p is not None else -1
            except:
                from_p = -1
            try:
                to_p = int(to_p) if to_p is not None else -1
            except:
                to_p = -1

            if proto == "-1":
                from_p = -1
                to_p = -1

            # IPv4 ranges
            for rng in perm.get("IpRanges", []):
                cidr = rng.get("CidrIp")
                entry = (proto, from_p, to_p, cidr, None, None)
                normalized.add(entry)

            # IPv6 ranges
            for rng in perm.get("Ipv6Ranges", []):
                cidr = rng.get("CidrIpv6")
                entry = (proto, from_p, to_p, None, cidr, None)
                normalized.add(entry)

            # User Id Group Pairs (Source SGs)
            for pair in perm.get("UserIdGroupPairs", []):
                grp_id = pair.get("GroupId")
                entry = (proto, from_p, to_p, None, None, grp_id)
                normalized.add(entry)

        return normalized

    def _compare_rules(
        self,
        logical_id: str,
        physical_id: str,
        expected: Set[Tuple],
        actual: Set[Tuple],
        findings: List[CloudFinding],
        detector_cls,
        file_path: str,
    ):
        # Missing
        missing = expected - actual
        for m in missing:
            findings.append(
                CloudFinding(
                    format="cloud_drift",
                    rule_id="DRIFT_AWS_SG_MISSING",
                    severity="HIGH",
                    evidence=f"[{logical_id}] Expected rule {m} missing in live SG {physical_id}.",
                    location=CloudLocation(path=file_path),
                    confidence="HIGH",
                    remediation="Apply the CloudFormation template to restore the rule.",
                )
            )

        # Unexpected
        unexpected = actual - expected
        for u in unexpected:
            # u is (proto, from, to, cidr4, cidr6, src_sg)
            proto, fp, tp, cidr4, cidr6, src_sg = u

            severity = detector_cls.classify_sg_unexpected_severity(proto, fp, tp, cidr4, cidr6)

            findings.append(
                CloudFinding(
                    format="cloud_drift",
                    rule_id="DRIFT_AWS_SG_UNEXPECTED",
                    severity=severity,
                    evidence=f"[{logical_id}] Unexpected rule {u} found in live SG {physical_id}.",
                    location=CloudLocation(path=file_path),
                    confidence="HIGH",
                    remediation="Remove the manual change from the cloud resource.",
                )
            )
