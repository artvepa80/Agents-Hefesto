"""
Hefesto PRO example: semantic similarity with local embeddings.

The PRO semantic analyzer uses a local ``sentence-transformers`` model; no
code is sent to any AI service. ``hefesto analyze`` uses it for the
DUPLICATE_CODE check only when ``hefesto-ai[pro]`` is installed and
``HEFESTO_TIER`` is ``professional`` or ``omega``
(see hefesto/analyzers/semantic_duplication.py).

Requires:
    pip install hefesto-ai[pro]
    export HEFESTO_LICENSE_KEY='hef_your_key'

Purchase: https://hefestoai.narapallc.com/#pricing
"""

import sys


def main() -> int:
    try:
        from hefesto_pro import get_semantic_analyzer
    except ImportError as exc:
        print(f"PRO is not available ({exc}).")
        print("Install: pip install hefesto-ai[pro]")
        print("Set:     export HEFESTO_LICENSE_KEY='hef_your_key'")
        return 0

    analyzer = get_semantic_analyzer()
    if analyzer.model is None:
        print("The local embedding model is not available (sentence-transformers missing).")
        return 0

    code1 = "def add(a, b): return a + b"
    code2 = "def sum_two(x, y): return x + y"
    similarity = analyzer.calculate_similarity(code1, code2)

    print(f"Code 1: {code1}")
    print(f"Code 2: {code2}")
    print(f"Semantic similarity: {similarity:.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
