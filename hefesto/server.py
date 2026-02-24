"""
Hefesto API Server — minimal FastAPI application.

Routes:
    GET  /health       — liveness probe
    POST /analyze      — analyze code (accepts file content or path)

Hardening (CORS, auth, rate-limit) is applied externally by
``hefesto_pro.api_hardening.apply_hardening`` when PRO is installed.

Analysis logic delegates to the same engine used by ``hefesto analyze`` CLI
(``hefesto.cli.main._setup_analyzer_engine`` / ``_run_analysis_loop``),
avoiding duplication.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from hefesto.__version__ import __version__


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""

    paths: List[str]
    severity: str = "MEDIUM"
    exclude: Optional[str] = None
    fail_on: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """Response body for /analyze endpoint."""

    summary: Dict[str, Any]
    file_results: List[Dict[str, Any]]
    meta: Dict[str, Any] = {}


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Hefesto API",
        version=__version__,
        description="AI-Powered Code Quality Guardian",
    )

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/analyze", response_model=AnalyzeResponse)
    def analyze_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
        import os

        # NOTE: These are CLI-private helpers. If they are ever refactored,
        # update server.py accordingly.
        # Long-term: move to hefesto/core/analysis_runner.py
        from hefesto.cli.main import _run_analysis_loop, _setup_analyzer_engine

        # Validate paths exist
        for p in request.paths:
            if not os.path.exists(p):
                raise HTTPException(status_code=404, detail=f"Path not found: {p}")

        exclude_patterns = []
        if request.exclude:
            exclude_patterns = [e.strip() for e in request.exclude.split(",") if e.strip()]

        engine = _setup_analyzer_engine(severity=request.severity, quiet=True, json_mode=True)
        if not engine:
            raise HTTPException(status_code=500, detail="Failed to initialize analysis engine")

        t0 = time.monotonic()
        all_file_results, total_loc, total_duration, source_cache = _run_analysis_loop(
            engine, list(request.paths), exclude_patterns
        )
        duration = time.monotonic() - t0

        # Serialize results
        all_issues = []
        serialized_results = []
        for fr in all_file_results:
            all_issues.extend(fr.issues)
            serialized_results.append(
                {
                    "file_path": str(fr.file_path),
                    "issues": [
                        {
                            "message": i.message,
                            "severity": i.severity.value,
                            "issue_type": i.issue_type.value,
                            "line": i.line,
                            "suggestion": i.suggestion,
                        }
                        for i in fr.issues
                    ],
                }
            )

        summary = {
            "files_analyzed": len(all_file_results),
            "total_issues": len(all_issues),
            "critical_issues": sum(1 for i in all_issues if i.severity.value == "CRITICAL"),
            "high_issues": sum(1 for i in all_issues if i.severity.value == "HIGH"),
            "medium_issues": sum(1 for i in all_issues if i.severity.value == "MEDIUM"),
            "low_issues": sum(1 for i in all_issues if i.severity.value == "LOW"),
            "total_loc": total_loc,
            "duration_seconds": round(duration, 3),
        }

        # Gate check
        gate_blocked = False
        if request.fail_on:
            severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            threshold_idx = severity_order.index(request.fail_on.upper())
            for issue in all_issues:
                if severity_order.index(issue.severity.value) >= threshold_idx:
                    gate_blocked = True
                    break

        return AnalyzeResponse(
            summary=summary,
            file_results=serialized_results,
            meta={"gate_blocked": gate_blocked, "version": __version__},
        )

    return app
