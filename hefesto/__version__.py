"""
Hefesto version information.
"""

__version__ = "4.3.0"
__api_version__ = "v1"

# Version history
# 4.0.0 - Initial PyPI release (CLI only)
# 4.0.1 - REST API release (Phases 1-4 complete)
#         - 8 endpoints operational
#         - BigQuery integration
#         - IRIS correlation foundation
#         - 118+ tests passing
# 4.1.0 - Unified Package Architecture
#         - PRO features merged with license gates
#         - Real SemanticAnalyzer (ML) implementation
#         - OMEGA Guardian features included
#         - Complete licensing system integrated
# 4.2.0 - OMEGA Guardian Release
#         - IRIS Agent integration (production monitoring)
#         - HefestoEnricher (auto-correlation)
#         - 3-tier licensing (FREE/PRO/OMEGA)
#         - HFST- license format for OMEGA
#         - pip install hefesto-ai[omega]
# 4.2.1 - CRITICAL BUGFIX: Tier Hierarchy
#         - Fixed OMEGA users blocked from PRO features
#         - Implemented proper tier hierarchy (OMEGA >= PRO >= FREE)
#         - Added 17 tests for tier hierarchy
#         - Verified with real OMEGA license
# 4.3.0 - Multi-Language Support (TypeScript/JavaScript)
#         - Added TypeScript/JavaScript analysis support via TreeSitter
#         - Created GenericAST abstraction for language-agnostic analysis
#         - Refactored all analyzers to work with multi-language AST
#         - Market coverage: 30% → 80% (added web developers)
#         - Maintained backward compatibility with Python-only projects
