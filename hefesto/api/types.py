"""
Branded types for Hefesto API.

Provides type-safe wrappers for domain entities following CLAUDE.md standards.
Branded types prevent mixing different string types and catch bugs at compile time.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from typing import NewType

# Analysis identifiers
AnalysisId = NewType("AnalysisId", str)
"""Unique identifier for analysis runs (format: ana_*)"""

FindingId = NewType("FindingId", str)
"""Unique identifier for individual findings (format: fnd_*)"""

# File and path types
FilePathStr = NewType("FilePathStr", str)
"""Validated file system path"""

AnalyzerName = NewType("AnalyzerName", str)
"""Name of code analyzer (complexity, security, code_smells, best_practices)"""

# Configuration types
ExcludePattern = NewType("ExcludePattern", str)
"""File exclusion pattern (glob format)"""

# BigQuery types (Phase 3)
ProjectId = NewType("ProjectId", str)
"""GCP project ID for BigQuery (format: lowercase with hyphens)"""

DatasetId = NewType("DatasetId", str)
"""BigQuery dataset identifier (format: lowercase_with_underscores)"""

TableId = NewType("TableId", str)
"""BigQuery table identifier (format: lowercase_with_underscores)"""

FindingStatus = NewType("FindingStatus", str)
"""Finding status (new, in_progress, resolved, ignored, false_positive)"""

HistoryId = NewType("HistoryId", str)
"""Unique identifier for finding history entries (format: his_*)"""


__all__ = [
    "AnalysisId",
    "FindingId",
    "FilePathStr",
    "AnalyzerName",
    "ExcludePattern",
    "ProjectId",
    "DatasetId",
    "TableId",
    "FindingStatus",
    "HistoryId",
]
