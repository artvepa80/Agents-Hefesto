"""
Semantic Duplication Analyzer — ML-powered duplicate code detection.

Uses SemanticAnalyzer (sentence-transformers) to compare function embeddings
and detect functionally similar code across files.

Optimized: batch encoding + numpy cosine similarity matrix.
(DeepSeek: architecture, MiniMax: performance optimization)

Part of OMEGA Guardian Phase 1: ML Enhancement.

Copyright 2025 Narapa LLC, Miami, Florida
"""

import logging
import os
import time
from typing import Dict, List, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
    FileAnalysisResult,
)

logger = logging.getLogger(__name__)

MIN_FUNCTION_LINES = 3
SIMILARITY_THRESHOLD = 0.85
MAX_FUNCTIONS = 200


def _get_model():
    """Lazy-load sentence-transformers model. Returns None if unavailable."""
    tier = os.environ.get("HEFESTO_TIER", "")
    if tier not in ("professional", "omega"):
        return None
    try:
        from hefesto_pro import get_semantic_analyzer

        sa = get_semantic_analyzer()
        return sa.model if sa.model is not None else None
    except (ImportError, Exception) as e:
        logger.debug("ML model not available: %s", e)
        return None


def find_semantic_duplicates(
    file_results: List[FileAnalysisResult],
    source_files: Dict[str, str],
) -> Tuple[List[AnalysisIssue], Dict]:
    """
    Analyze functions across files for semantic duplication.

    Returns:
        Tuple of (issues list, stats dict)
    """
    stats: dict = {"functions": 0, "pairs": 0, "duration_ms": 0.0}
    t0 = time.time()

    model = _get_model()
    if model is None:
        return [], stats

    functions = _extract_functions(file_results, source_files)
    stats["functions"] = len(functions)

    if len(functions) < 2:
        return [], stats

    if len(functions) > MAX_FUNCTIONS:
        functions.sort(key=lambda f: -len(f["text"]))
        functions = functions[:MAX_FUNCTIONS]
        stats["functions"] = MAX_FUNCTIONS

    # Batch encode all functions at once (MiniMax optimization: 200 encodes vs 39800)
    texts = [f["text"] for f in functions]
    try:
        import numpy as np

        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    except Exception as e:
        logger.error("Batch encoding failed: %s", e)
        return [], stats

    # Compute cosine similarity matrix (MiniMax optimization: vectorized)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = embeddings / norms
    sim_matrix = np.dot(normalized, normalized.T)

    # Extract pairs above threshold (upper triangle only)
    issues = []
    seen_pairs = set()
    n = len(functions)

    for i in range(n):
        for j in range(i + 1, n):
            sim = float(sim_matrix[i, j])
            if sim < SIMILARITY_THRESHOLD:
                continue

            fa, fb = functions[i], functions[j]

            # Skip same-file same-function
            if fa["file"] == fb["file"] and fa["name"] == fb["name"]:
                continue

            pair_key = tuple(sorted([(fa["file"], fa["name"]), (fb["file"], fb["name"])]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            if sim >= 0.95:
                severity = AnalysisIssueSeverity.HIGH
            elif sim >= 0.90:
                severity = AnalysisIssueSeverity.MEDIUM
            else:
                severity = AnalysisIssueSeverity.LOW

            other_file = os.path.basename(fb["file"])
            msg = (
                "Function '{}' is semantically similar to " "'{}' in {}:{} (similarity: {:.0%})"
            ).format(fa["name"], fb["name"], other_file, fb["line"], sim)

            issues.append(
                AnalysisIssue(
                    file_path=fa["file"],
                    line=fa["line"],
                    column=0,
                    issue_type=AnalysisIssueType.DUPLICATE_CODE,
                    severity=severity,
                    message=msg,
                    function_name=fa["name"],
                    suggestion=(
                        "Consider extracting shared logic into a common helper "
                        "function to reduce duplication."
                    ),
                    engine="ml:semantic_duplication",
                    confidence=sim,
                    metadata={
                        "similar_to": fb["name"],
                        "similar_file": fb["file"],
                        "similar_line": fb["line"],
                        "similarity": round(sim, 4),
                    },
                )
            )

    issues.sort(key=lambda x: -(x.confidence or 0))
    stats["pairs"] = len(issues)
    stats["duration_ms"] = round((time.time() - t0) * 1000, 1)

    logger.info(
        "ML duplication: %d functions, %d duplicates found in %.1fms",
        stats["functions"],
        stats["pairs"],
        stats["duration_ms"],
    )
    return issues, stats


def _extract_functions(
    file_results: List[FileAnalysisResult],
    source_files: Dict[str, str],
) -> list:
    """Extract function bodies from analyzed files using Hefesto parser."""
    from hefesto.core.language_detector import Language, LanguageDetector
    from hefesto.core.parsers.parser_factory import ParserFactory

    functions = []
    for fr in file_results:
        fp = fr.file_path
        code = source_files.get(fp)
        if not code:
            continue

        try:
            from pathlib import Path

            lang = LanguageDetector.detect(Path(fp), code)
        except Exception:
            continue

        if lang in (
            Language.UNKNOWN,
            Language.YAML,
            Language.SHELL,
            Language.DOCKERFILE,
            Language.TERRAFORM,
            Language.SQL,
        ):
            continue

        try:
            parser = ParserFactory.get_parser(lang)
            tree = parser.parse(code, fp)
        except Exception:
            continue

        code_lines = code.split("\n")
        for func in tree.get_functions():
            line_start = getattr(func, "line_start", 0)
            line_end = getattr(func, "line_end", 0)
            if line_end - line_start < MIN_FUNCTION_LINES:
                continue
            # Extract function body from source using line numbers
            text = "\n".join(code_lines[line_start - 1 : line_end])
            if not text.strip():
                continue
            functions.append(
                {
                    "file": fp,
                    "name": func.name,
                    "line": line_start,
                    "text": text,
                    "language": lang.value,
                }
            )

    return functions
