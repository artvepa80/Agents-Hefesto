from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover
    boto3 = None
    ClientError = Exception  # type: ignore


@dataclass(frozen=True)
class ResolveResult:
    resource_map: Dict[str, str]  # logical_id -> physical_id
    evidence: List[str]


class ResolverStrategy(Protocol):
    def resolve(self, template: Dict[str, Any], region: str, session: Any) -> ResolveResult: ...


class AwsSessionFactory:
    @staticmethod
    def get_session(region: str, credentials: Any) -> Optional[Any]:
        if credentials is not None:
            return credentials
        if boto3 is None:
            return None
        return boto3.Session(region_name=region)


class StackResolver:
    """
    If a stack name/id is provided via template Metadata or Parameters, resolve physical IDs
    via CloudFormation's describe_stack_resources.
    """

    def __init__(
        self, stack_name_key: str = "HefestoStackName", explicit_stack_name: Optional[str] = None
    ):
        self.stack_name_key = stack_name_key
        self.explicit_stack_name = explicit_stack_name

    def resolve(self, template: Dict[str, Any], region: str, session: Any) -> ResolveResult:
        stack_name = self._get_stack_name(template)
        if not stack_name:
            return ResolveResult(
                resource_map={},
                evidence=["StackResolver: no stack name found in template metadata"],
            )

        try:
            cfn = session.client("cloudformation", region_name=region)
            resp = cfn.describe_stack_resources(StackName=stack_name)
            mapping: Dict[str, str] = {}
            for r in resp.get("StackResources", []):
                logical = r.get("LogicalResourceId")
                physical = r.get("PhysicalResourceId")
                if logical and physical:
                    mapping[str(logical)] = str(physical)

            ev = [f"StackResolver: resolved {len(mapping)} resources from StackName={stack_name}"]
            return ResolveResult(resource_map=mapping, evidence=ev)
        except ClientError as e:
            return ResolveResult(resource_map={}, evidence=[f"StackResolver: ClientError {e}"])
        except Exception as e:
            return ResolveResult(resource_map={}, evidence=[f"StackResolver: error {e}"])

    def _get_stack_name(self, template: Dict[str, Any]) -> Optional[str]:
        if self.explicit_stack_name:
            return self.explicit_stack_name

        md = template.get("Metadata") or {}
        # Prefer explicit stack name in metadata
        if (
            isinstance(md, dict)
            and self.stack_name_key in md
            and isinstance(md[self.stack_name_key], str)
        ):
            return str(md[self.stack_name_key])

        # Optional: allow Parameters default
        params = template.get("Parameters") or {}
        if isinstance(params, dict) and self.stack_name_key in params:
            p = params[self.stack_name_key] or {}
            default = p.get("Default")
            if isinstance(default, str):
                return default
        return None


class TagResolver:
    """
    Uses Resource Groups Tagging API to find resources that carry CFN logical-id tags.
    Works only if those tags exist.
    """

    def __init__(self, explicit_tags: Optional[Dict[str, str]] = None):
        self.explicit_tags = explicit_tags

    def resolve(self, template: Dict[str, Any], region: str, session: Any) -> ResolveResult:
        try:
            tagging = session.client("resourcegroupstaggingapi", region_name=region)
        except Exception as e:
            return ResolveResult(
                resource_map={}, evidence=[f"TagResolver: cannot create tagging client: {e}"]
            )

        tag_filters = {}
        if self.explicit_tags:
            tag_filters = self.explicit_tags
        else:
            # Look for any tag hints provided by user in Metadata.HefestoTagFilters (dict)
            md = template.get("Metadata") or {}
            if isinstance(md, dict):
                raw = md.get("HefestoTagFilters")
                if isinstance(raw, dict):
                    tag_filters = {
                        str(k): str(v) for k, v in raw.items() if isinstance(v, (str, int, float))
                    }

        if not tag_filters:
            return ResolveResult(
                resource_map={}, evidence=["TagResolver: no Metadata.HefestoTagFilters present"]
            )

        # We will fetch all resources with those tags, then try to match to logical IDs.
        try:
            paginator = tagging.get_paginator("get_resources")
            pages = paginator.paginate(
                TagFilters=[{"Key": k, "Values": [v]} for k, v in tag_filters.items()]
            )
            mapping: Dict[str, str] = {}
            seen = 0
            for page in pages:
                for item in page.get("ResourceTagMappingList", []):
                    arn = item.get("ResourceARN")
                    tags = {
                        t.get("Key"): t.get("Value") for t in item.get("Tags", []) if t.get("Key")
                    }
                    seen += 1

                    # Standard CFN tags sometimes used:
                    logical = tags.get("aws:cloudformation:logical-id") or tags.get(
                        "cloudformation:logical-id"
                    )
                    physical = arn
                    if logical and physical:
                        mapping[str(logical)] = str(physical)

            ev = [
                f"TagResolver: scanned {seen} tagged resources; matched {len(mapping)} logical IDs"
            ]
            return ResolveResult(resource_map=mapping, evidence=ev)
        except ClientError as e:
            return ResolveResult(resource_map={}, evidence=[f"TagResolver: ClientError {e}"])
        except Exception as e:
            return ResolveResult(resource_map={}, evidence=[f"TagResolver: error {e}"])


class NameResolver:
    """
    Heuristic fallback resolver.
    For AWS::EC2::SecurityGroup: tries describe_security_groups(GroupNames=[logical_id])
    or GroupName from Properties.GroupName.
    """

    def resolve(self, template: Dict[str, Any], region: str, session: Any) -> ResolveResult:
        resources = template.get("Resources", {}) or {}
        sg_candidates: List[Tuple[str, str]] = []  # (logical_id, desired_group_name)

        for logical_id, res in resources.items():
            if (res or {}).get("Type") != "AWS::EC2::SecurityGroup":
                continue
            props = (res or {}).get("Properties", {}) or {}
            group_name = props.get("GroupName")
            if isinstance(group_name, str) and group_name.strip():
                sg_candidates.append((str(logical_id), group_name.strip()))
            else:
                # last resort: logical_id itself
                sg_candidates.append((str(logical_id), str(logical_id)))

        if not sg_candidates:
            return ResolveResult(
                resource_map={}, evidence=["NameResolver: no SG candidates in template"]
            )

        try:
            ec2 = session.client("ec2", region_name=region)
        except Exception as e:
            return ResolveResult(
                resource_map={}, evidence=[f"NameResolver: cannot create ec2 client: {e}"]
            )

        mapping: Dict[str, str] = {}
        evidence: List[str] = []
        for logical_id, group_name in sg_candidates:
            try:
                resp = ec2.describe_security_groups(
                    Filters=[{"Name": "group-name", "Values": [group_name]}]
                )
                sgs = resp.get("SecurityGroups", [])
                if len(sgs) == 1 and sgs[0].get("GroupId"):
                    mapping[logical_id] = str(sgs[0]["GroupId"])
            except ClientError:
                continue
            except Exception:
                continue

        evidence.append(
            f"NameResolver: matched {len(mapping)}/{len(sg_candidates)} SGs by group-name heuristic"
        )
        return ResolveResult(resource_map=mapping, evidence=evidence)


class ResourceResolver:
    """
    Runs resolution strategies in order, merges mappings with precedence:
    earlier strategies win; later strategies only fill gaps.
    """

    def __init__(self, strategies: Optional[List[ResolverStrategy]] = None):
        self.strategies = strategies or [StackResolver(), TagResolver(), NameResolver()]

    def resolve(self, template: Dict[str, Any], region: str, credentials: Any) -> ResolveResult:
        session = AwsSessionFactory.get_session(region=region, credentials=credentials)
        if session is None:
            return ResolveResult(
                resource_map={}, evidence=["ResourceResolver: boto3/session unavailable"]
            )

        merged: Dict[str, str] = {}
        evidence: List[str] = []

        for strat in self.strategies:
            res = strat.resolve(template=template, region=region, session=session)
            evidence.extend(res.evidence)

            # fill gaps only
            for k, v in res.resource_map.items():
                if k not in merged:
                    merged[k] = v

        evidence.append(f"ResourceResolver: final resolved {len(merged)} logical IDs")
        return ResolveResult(resource_map=merged, evidence=evidence)
