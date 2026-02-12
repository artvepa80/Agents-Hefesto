from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class SandboxConfig:
    workspace_root: Path
    # Which query/body keys can contain filesystem paths that must be sandboxed.
    # Keep tight; expand only if you actually accept these inputs.
    path_keys: tuple[str, ...] = ("path", "file", "filepath", "project_root", "root")


def _is_within(child: Path, root: Path) -> bool:
    try:
        child_resolved = child.resolve()
        root_resolved = root.resolve()
        child_resolved.relative_to(root_resolved)
        return True
    except Exception:
        return False


def _collect_candidate_paths(req: Request, keys: Iterable[str]) -> list[str]:
    vals: list[str] = []

    # Query params
    for k in keys:
        v = req.query_params.get(k)
        if v:
            vals.append(v)

    # Headers (optional) - usually not needed, but safe if you ever pass paths there.
    for k in keys:
        v = req.headers.get(k)
        if v:
            vals.append(v)

    return vals


class PathSandboxMiddleware(BaseHTTPMiddleware):
    """
    Restricts any user-provided path-like inputs to a workspace root.
    This middleware does NOT attempt to rewrite paths; it rejects traversal/out-of-root.
    """

    def __init__(self, app, config: SandboxConfig):
        super().__init__(app)
        self.cfg = config

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only enforce on endpoints that might touch filesystem.
        # If you want global enforcement, remove the method/path check.
        # Safe baseline: enforce for non-GET too.
        if request.method in ("POST", "PUT", "PATCH", "DELETE") or "path" in request.url.path:
            candidates = _collect_candidate_paths(request, self.cfg.path_keys)

            # Body JSON keys (best-effort; do not break on non-JSON)
            try:
                if request.headers.get("content-type", "").lower().startswith("application/json"):
                    body = await request.json()
                    if isinstance(body, dict):
                        for k in self.cfg.path_keys:
                            v = body.get(k)
                            if isinstance(v, str) and v.strip():
                                candidates.append(v)
            except Exception:
                # Best-effort: ignore body parse errors
                pass

            for raw in candidates:
                # Normalize -> absolute relative to workspace if relative
                p = Path(raw)
                if not p.is_absolute():
                    p = self.cfg.workspace_root / p

                if not _is_within(p, self.cfg.workspace_root):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "path_outside_workspace",
                            "detail": "Requested path is outside HEFESTO_WORKSPACE_ROOT.",
                        },
                    )

        return await call_next(request)  # type: ignore
