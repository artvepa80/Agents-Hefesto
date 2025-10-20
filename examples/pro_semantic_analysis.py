"""
Hefesto Pro Examples - Semantic Analysis

These examples require a Pro license (Phase 1).
Set environment variable: HEFESTO_LICENSE_KEY='hef_your_key'

Purchase: https://buy.stripe.com/hefesto-pro
"""

import os


def example_semantic_similarity():
    """Calculate semantic similarity between code snippets."""
    try:
        from hefesto.llm.semantic_analyzer import get_semantic_analyzer
    except ImportError as e:
        print("❌ Pro features not available")
        print("💡 Install: pip install hefesto[pro]")
        print("🔑 Set: export HEFESTO_LICENSE_KEY='hef_your_key'")
        print(f"🛒 Purchase: https://buy.stripe.com/hefesto-pro")
        return
    
    print("=" * 60)
    print("Example: Semantic Code Similarity (Pro)")
    print("=" * 60)
    
    # Check license
    license_key = os.getenv('HEFESTO_LICENSE_KEY')
    if not license_key:
        print("\n❌ Error: HEFESTO_LICENSE_KEY not set")
        print("🔑 Set your Pro license key:")
        print("   export HEFESTO_LICENSE_KEY='hef_your_key_here'")
        print("\n🛒 Don't have a key? Purchase at:")
        print("   https://buy.stripe.com/hefesto-pro")
        return
    
    analyzer = get_semantic_analyzer()
    
    # Example: Semantically similar code with different variable names
    code1 = "def add(a, b): return a + b"
    code2 = "def sum_two(x, y): return x + y"
    
    similarity = analyzer.calculate_similarity(code1, code2)
    
    print(f"\nCode 1: {code1}")
    print(f"Code 2: {code2}")
    print(f"\n🧠 Semantic Similarity: {similarity:.2%}")
    
    if similarity > 0.85:
        print("✅ High similarity - likely duplicate!")
    elif similarity > 0.60:
        print("⚠️  Moderate similarity - related functionality")
    else:
        print("✓ Different functionality")


def example_duplicate_detection():
    """Detect duplicate suggestions."""
    try:
        from hefesto.llm.semantic_analyzer import get_semantic_analyzer
    except ImportError:
        print("❌ Pro features require license. See pro_semantic_analysis.py")
        return
    
    print("\n" + "=" * 60)
    print("Example: Duplicate Suggestion Detection (Pro)")
    print("=" * 60)
    
    analyzer = get_semantic_analyzer()
    
    suggestions = [
        "def calculate_total(items): return sum(item.price for item in items)",
        "def get_total(products): return sum(p.price for p in products)",
        "def total_price(cart): return sum(x.price for x in cart)",
    ]
    
    print("\n🔍 Analyzing suggestions for duplicates...\n")
    
    for i, sug in enumerate(suggestions):
        print(f"Suggestion {i+1}: {sug}")
    
    print(f"\n📊 Similarity Matrix:")
    for i in range(len(suggestions)):
        for j in range(i+1, len(suggestions)):
            sim = analyzer.calculate_similarity(suggestions[i], suggestions[j])
            status = "🔴 DUPLICATE" if sim > 0.85 else "✅ UNIQUE"
            print(f"  [{i+1}↔{j+1}]: {sim:.2%} {status}")


def example_code_embeddings():
    """Generate code embeddings for analysis."""
    try:
        from hefesto.llm.semantic_analyzer import get_semantic_analyzer
    except ImportError:
        print("❌ Pro features require license. See pro_semantic_analysis.py")
        return
    
    print("\n" + "=" * 60)
    print("Example: Code Embeddings (Pro)")
    print("=" * 60)
    
    analyzer = get_semantic_analyzer()
    
    code = """
    def authenticate(username, password):
        if username == 'admin' and password == 'secret':
            return True
        return False
    """
    
    embedding = analyzer.get_code_embedding(code, language="python")
    
    if embedding:
        print(f"\n✅ Generated embedding:")
        print(f"  Hash: {embedding.code_hash}")
        print(f"  Dimension: {len(embedding.embedding)}")
        print(f"  Preview: {embedding.code_snippet[:80]}...")
        print(f"  Model: {embedding.metadata.get('model', 'N/A')}")
    else:
        print("\n❌ Failed to generate embedding")


if __name__ == '__main__':
    print("🌟 HEFESTO PRO - Semantic Analysis Examples\n")
    
    example_semantic_similarity()
    example_duplicate_detection()
    example_code_embeddings()
    
    print("\n" + "=" * 60)
    print("✅ Pro examples complete!")
    print("=" * 60)
    print("\n💡 More features:")
    print("   • CI/CD feedback automation")
    print("   • Advanced analytics dashboard")
    print("   • Custom validation rules")
    print("\n📚 Documentation: https://github.com/artvepa80/Agents-Hefesto")

