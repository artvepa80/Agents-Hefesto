"""
HEFESTO v3.5 Phase 1 - Semantic Code Analyzer

Purpose: Provides semantic understanding of code using embeddings.
Location: llm/semantic_analyzer.py

Enables intelligent similarity detection beyond simple text matching.
Uses lightweight sentence-transformers model for fast code understanding.

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeEmbedding:
    """
    Semantic embedding of code snippet.

    Attributes:
        code_hash: Unique identifier for code (SHA256 hash)
        embedding: Vector representation of code semantics
        code_snippet: Preview of the code (first 200 chars)
        metadata: Additional information (language, length, etc.)
    """

    code_hash: str
    embedding: List[float]
    code_snippet: str
    metadata: Dict[str, Any]


class SemanticAnalyzer:
    """
    Analyzes code semantically using embeddings.

    Uses lightweight sentence-transformers model for code understanding.
    Can detect semantically similar code even with different syntax.

    Usage:
        >>> analyzer = SemanticAnalyzer()
        >>>
        >>> # Get embedding for code
        >>> embedding = analyzer.get_code_embedding(
        ...     code="def calculate_total(items): return sum(item.price for item in items)",
        ...     language="python"
        ... )
        >>>
        >>> # Check similarity between two code snippets
        >>> similarity = analyzer.calculate_similarity(code1, code2)
        >>> print(f"Similarity: {similarity:.2%}")
        >>>
        >>> # Find similar existing suggestions
        >>> similar = analyzer.find_similar_suggestions(
        ...     new_code="def total(items): return sum(i.price for i in items)",
        ...     threshold=0.85
        ... )
    """

    def __init__(self):
        """Initialize semantic analyzer with ML model."""
        self.model = None
        self.model_name = "all-MiniLM-L6-v2"
        self._load_model()

    def _load_model(self):
        """
        Load lightweight sentence-transformers model for code.

        Uses: 'sentence-transformers/all-MiniLM-L6-v2'
        - Fast inference (<100ms)
        - Good code understanding
        - Only 80MB model size
        - 384-dimensional embeddings
        """
        try:
            from sentence_transformers import SentenceTransformer

            # Use lightweight model optimized for semantic similarity
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"✅ Semantic analyzer model loaded: {self.model_name}")

        except ImportError:
            logger.warning(
                "⚠️ sentence-transformers not installed. "
                "Semantic analysis will use fallback method. "
                "Install with: pip install sentence-transformers"
            )
            self.model = None
        except Exception as e:
            logger.error(f"❌ Failed to load semantic model: {e}")
            self.model = None

    def get_code_embedding(
        self,
        code: str,
        language: str = "python",
        normalize: bool = True,
    ) -> Optional[CodeEmbedding]:
        """
        Get semantic embedding for code snippet.

        Converts code into a dense vector representation that captures
        semantic meaning, allowing similarity comparisons.

        Args:
            code: Code snippet to analyze
            language: Programming language (for context)
            normalize: Normalize embedding to unit vector (recommended)

        Returns:
            CodeEmbedding with vector representation, or None if failed

        Example:
            >>> analyzer = SemanticAnalyzer()
            >>> embedding = analyzer.get_code_embedding(
            ...     code="def add(a, b): return a + b",
            ...     language="python"
            ... )
            >>> print(f"Embedding dimension: {len(embedding.embedding)}")
            Embedding dimension: 384
        """
        if not self.model:
            logger.debug("Semantic model not available, using fallback")
            return self._fallback_embedding(code, language)

        try:
            # Preprocess code for better embeddings
            processed = self._preprocess_code(code, language)

            # Generate embedding
            embedding = self.model.encode(
                processed, normalize_embeddings=normalize, show_progress_bar=False
            )

            # Create hash for caching/deduplication
            code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]

            return CodeEmbedding(
                code_hash=code_hash,
                embedding=embedding.tolist(),
                code_snippet=code[:200],  # Store preview
                metadata={
                    "language": language,
                    "length": len(code),
                    "normalized": normalize,
                    "model": self.model_name,
                },
            )

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return self._fallback_embedding(code, language)

    def _preprocess_code(self, code: str, language: str) -> str:
        """
        Preprocess code for better embeddings.

        Preprocessing steps:
        - Remove comments (focus on logic)
        - Normalize whitespace
        - Add language context for better embedding

        Args:
            code: Raw code string
            language: Programming language

        Returns:
            Preprocessed code string ready for embedding
        """
        # Remove Python comments
        lines = [
            line.split("#")[0].strip()
            for line in code.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        clean_code = " ".join(lines)

        # Add language context for better embedding
        # This helps the model understand language-specific semantics
        return f"[{language.upper()}] {clean_code}"

    def _fallback_embedding(self, code: str, language: str = "python") -> CodeEmbedding:
        """
        Fallback embedding when ML model not available.

        Uses simple hash-based character frequency vector.
        Not as accurate as ML embeddings but allows system to function.

        Args:
            code: Code snippet
            language: Programming language

        Returns:
            CodeEmbedding with fallback vector
        """
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]

        # Simple fallback: character frequency vector
        # Dimension 384 to match model output
        embedding = [0.0] * 384
        for char in code:
            embedding[ord(char) % 384] += 1.0

        # Normalize
        total = sum(embedding)
        if total > 0:
            embedding = [x / total for x in embedding]

        return CodeEmbedding(
            code_hash=code_hash,
            embedding=embedding,
            code_snippet=code[:200],
            metadata={
                "fallback": True,
                "method": "character_frequency",
                "language": language,
                "length": len(code),
                "normalized": True,
            },
        )

    def calculate_similarity(
        self,
        code1: str,
        code2: str,
        language: str = "python",
    ) -> float:
        """
        Calculate semantic similarity between two code snippets.

        Uses cosine similarity between code embeddings to determine
        how semantically similar two pieces of code are.

        Args:
            code1: First code snippet
            code2: Second code snippet
            language: Programming language

        Returns:
            Similarity score 0.0-1.0 (higher = more similar)
            - 0.95-1.0: Nearly identical
            - 0.80-0.95: Very similar (likely duplicate)
            - 0.60-0.80: Somewhat similar (related functionality)
            - 0.0-0.60: Different

        Example:
            >>> analyzer = SemanticAnalyzer()
            >>>
            >>> # Identical code
            >>> sim1 = analyzer.calculate_similarity(
            ...     "def add(a, b): return a + b",
            ...     "def add(a, b): return a + b"
            ... )
            >>> print(f"Identical: {sim1:.2f}")  # ~1.0
            >>>
            >>> # Semantically similar (different variable names)
            >>> sim2 = analyzer.calculate_similarity(
            ...     "def add(a, b): return a + b",
            ...     "def sum_two(x, y): return x + y"
            ... )
            >>> print(f"Similar: {sim2:.2f}")  # ~0.85
        """
        embedding1 = self.get_code_embedding(code1, language)
        embedding2 = self.get_code_embedding(code2, language)

        if not embedding1 or not embedding2:
            logger.warning("Failed to get embeddings for similarity calculation")
            return 0.0

        # Cosine similarity
        try:
            import numpy as np

            vec1 = np.array(embedding1.embedding)
            vec2 = np.array(embedding2.embedding)

            # Cosine similarity formula
            similarity = np.dot(vec1, vec2) / (
                np.linalg.norm(vec1) * np.linalg.norm(vec2) + 1e-8  # Avoid division by zero
            )

            return float(max(0.0, min(1.0, similarity)))  # Clamp to [0, 1]

        except ImportError:
            logger.warning("numpy not available, using fallback similarity")
            # Fallback: simple dot product (works if normalized)
            similarity = sum(a * b for a, b in zip(embedding1.embedding, embedding2.embedding))
            return float(max(0.0, min(1.0, similarity)))
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0

    def find_similar_suggestions(
        self,
        new_code: str,
        language: str = "python",
        threshold: float = 0.80,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find similar suggestions in feedback history.

        Queries BigQuery suggestion_feedback table to find
        semantically similar suggestions that were already made.

        NOTE: This is a Phase 1 feature foundation. Full implementation
        requires storing code embeddings in BigQuery (future enhancement).

        Args:
            new_code: Code to check for similarity
            language: Programming language
            threshold: Minimum similarity (0.0-1.0)
            limit: Max results to return

        Returns:
            List of similar suggestions with similarity scores

        Example:
            >>> analyzer = SemanticAnalyzer()
            >>> similar = analyzer.find_similar_suggestions(
            ...     new_code="def add(x, y): return x + y",
            ...     threshold=0.85,
            ...     limit=5
            ... )
            >>>
            >>> for s in similar:
            ...     print(f"Found: {s['suggestion_id']} (similarity: {s['similarity']:.2%})")
        """
        try:
            from google.cloud import bigquery

            client = bigquery.Client(project="hefesto-project")

            # Get recent suggestions from last 30 days
            # NOTE: Phase 2 enhancement will include code_embedding column
            # for efficient vector similarity search in BigQuery
            query = """
            SELECT
                suggestion_id,
                file_path,
                issue_type,
                severity,
                user_accepted,
                similarity_score,
                created_at
            FROM `hefesto-project.omega_agent.suggestion_feedback`
            WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            ORDER BY created_at DESC
            LIMIT 100
            """

            results = list(client.query(query).result())

            logger.info(f"Found {len(results)} recent suggestions to compare against")

            # Calculate similarity for each
            # NOTE: In production, we would store embeddings in BigQuery
            # and use vector similarity search for efficiency
            similar = []
            new_embedding = self.get_code_embedding(new_code, language)

            if not new_embedding:
                logger.warning("Could not generate embedding for new code")
                return []

            # For Phase 1, return empty list
            # Full implementation would:
            # 1. Store code embeddings in suggestion_feedback table
            # 2. Use vector similarity search in BigQuery
            # 3. Return top-K most similar suggestions
            # 4. Include original code for comparison

            logger.info(
                "Semantic similarity search foundation ready. "
                "Full implementation requires embedding storage in BigQuery."
            )

            return similar

        except Exception as e:
            logger.error(f"Failed to find similar suggestions: {e}")
            return []


# Singleton instance
_semantic_analyzer: Optional[SemanticAnalyzer] = None


def get_semantic_analyzer() -> SemanticAnalyzer:
    """
    Get singleton SemanticAnalyzer instance.

    Creates analyzer on first call, returns same instance on subsequent calls.
    This ensures the ML model is only loaded once per application lifecycle.

    Returns:
        Singleton SemanticAnalyzer instance

    Example:
        >>> analyzer1 = get_semantic_analyzer()
        >>> analyzer2 = get_semantic_analyzer()
        >>> assert analyzer1 is analyzer2  # Same instance
    """
    global _semantic_analyzer
    if _semantic_analyzer is None:
        _semantic_analyzer = SemanticAnalyzer()
    return _semantic_analyzer


__all__ = [
    "SemanticAnalyzer",
    "CodeEmbedding",
    "get_semantic_analyzer",
]
