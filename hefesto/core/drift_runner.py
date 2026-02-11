from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from hefesto.analyzers.cloud.drift.aws_sg import AwsSgDriftDetector
from hefesto.analyzers.cloud.drift.base import DriftContext
from hefesto.analyzers.cloud.finding_schema import CloudFinding
from hefesto.analyzers.cloud.graph.resolver import (
    NameResolver,
    ResourceResolver,
    StackResolver,
    TagResolver,
)


@dataclass(frozen=True)
class DriftRunResult:
    findings: List[CloudFinding]
    summary: Dict[str, Any]


class DriftRunner:
    """
    Runtime drift runner. Loads IaC template, configures resolver strategies with CLI args,
    initializes DriftContext, and runs detection.
    """

    def run(
        self,
        template_path: str,
        *,
        region: str,
        stack_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        autoresolve: bool = True,
    ) -> DriftRunResult:
        template = self._load_template(template_path)

        # Configure strategies
        strategies = []
        if autoresolve:
            strategies.append(StackResolver(explicit_stack_name=stack_name))
            strategies.append(TagResolver(explicit_tags=tags))
            strategies.append(NameResolver())

        resolver = ResourceResolver(strategies=strategies) if autoresolve else None

        resource_map = {}
        if resolver:
            # Resolve physical IDs
            # Note: We pass None for session/credentials here to let resolver/factory handle it (e.g. env vars)
            # But ResourceResolver.resolve needs explicit credentials or relies on boto3 default
            res_result = resolver.resolve(template=template, region=region, credentials=None)
            resource_map = res_result.resource_map

        # Build Context
        ctx = DriftContext(
            region=region,
            template_path=template_path,
            resource_map=resource_map,
            stack_name=stack_name,
            tags=tags or {},
            resolver=resolver,
        )

        # Detector
        detector = AwsSgDriftDetector()  # credentials loaded from env via context
        findings = detector.detect_drift(template=template, context=ctx)

        # Resolve stats
        resolved_count = len(ctx.resource_map) if ctx.resource_map else 0

        summary = {
            "region": region,
            "stack_name": stack_name,
            "autoresolve": autoresolve,
            "resolved_resources": resolved_count,
            "findings": len(findings),
        }
        return DriftRunResult(findings=findings, summary=summary)

    def _load_template(self, path: str) -> Dict[str, Any]:
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Template not found: {path}")

        raw = p.read_text(encoding="utf-8")
        suffix = p.suffix.lower()

        # JSON
        if suffix == ".json":
            return json.loads(raw)

        # YAML
        if suffix in (".yml", ".yaml"):
            data = yaml.safe_load(raw)
            if not isinstance(data, dict):
                raise ValueError("Template must parse to a dict/object at root level.")
            return data

        # Fallback
        try:
            data = yaml.safe_load(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        try:
            return json.loads(raw)
        except Exception as e:
            raise ValueError("Unsupported template format. Use .yml/.yaml/.json") from e
