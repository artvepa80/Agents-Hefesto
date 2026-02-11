from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple


@dataclass(frozen=True)
class GraphEdge:
    src: str
    dst: str
    kind: str  # "Ref" | "GetAtt" | "Other"


class CloudFormationGraphBuilder:
    """
    Builds an in-memory dependency graph from a parsed CloudFormation dict.
    Deterministic and safe: doesn't evaluate intrinsics, only discovers references.
    """

    def build(self, template: Dict[str, Any]) -> Tuple[Set[str], List[GraphEdge]]:
        resources = template.get("Resources", {}) or {}
        nodes: Set[str] = set(resources.keys())
        edges: List[GraphEdge] = []

        for logical_id, res in resources.items():
            props = (res or {}).get("Properties", {})
            for ref in self._extract_refs(props):
                # keep edges only to known resources
                if ref in nodes:
                    edges.append(GraphEdge(src=logical_id, dst=ref, kind="Ref"))
            for ga in self._extract_getatts(props):
                target = ga.split(".", 1)[0]
                if target in nodes:
                    edges.append(GraphEdge(src=logical_id, dst=target, kind="GetAtt"))

        # stable output ordering helps tests/repro
        edges.sort(key=lambda e: (e.src, e.dst, e.kind))
        return nodes, edges

    def _extract_refs(self, obj: Any) -> Set[str]:
        refs: Set[str] = set()
        self._walk(obj, refs, set())
        return refs

    def _extract_getatts(self, obj: Any) -> Set[str]:
        getatts: Set[str] = set()
        self._walk(obj, set(), getatts)
        return getatts

    def _walk(self, obj: Any, refs: Set[str], getatts: Set[str]) -> None:
        if isinstance(obj, dict):
            # Ref
            if "Ref" in obj and isinstance(obj["Ref"], str):
                refs.add(obj["Ref"])

            # Fn::GetAtt (list or string)
            if "Fn::GetAtt" in obj:
                ga = obj["Fn::GetAtt"]
                if (
                    isinstance(ga, list)
                    and len(ga) >= 2
                    and all(isinstance(x, str) for x in ga[:2])
                ):
                    getatts.add(f"{ga[0]}.{ga[1]}")
                elif isinstance(ga, str):
                    getatts.add(ga)

            for v in obj.values():
                self._walk(v, refs, getatts)

        elif isinstance(obj, list):
            for item in obj:
                self._walk(item, refs, getatts)
