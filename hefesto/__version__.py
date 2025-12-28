"""
Hefesto version information.
"""

__version__ = "4.4.0"
__api_version__ = "v1"

# Version history
# 4.4.0 - DevOps Language Support (Ola 1)
#         - YAML analysis with internal YamlAnalyzer
#         - LanguageSpec + LanguageRegistry architecture
#         - ExternalProvider + ProviderRegistry for future external tools
#         - Enterprise fields: engine, rule_id, confidence, source
#         - Support for 12 languages total (7 code + 5 DevOps)
#         - python -m hefesto entrypoint
# 4.3.4 - CLI Improvements
#         - Multiple paths support: hefesto analyze src/ lib/ types/
#         - --fail-on option for CI exit codes (LOW|MEDIUM|HIGH|CRITICAL)
#         - --quiet mode for minimal output (summary only)
#         - --max-issues to limit displayed issues
#         - Removed emojis from CLI per coding guidelines
# 4.3.3 - TypeScript Analysis Fixes
#         - Fixed LONG_PARAMETER_LIST using AST formal_parameters
#         - Fixed function naming for arrow functions (variable_declarator)
#         - Added threshold values to all code smell messages
#         - Added line ranges to LONG_FUNCTION suggestions
# 4.3.2 - Multi-Language Support Complete
#         - Complete support for all 7 languages
#         - Fixed TreeSitter grammar loading
#         - Added Rust and C# parser support
# 4.3.1 - License validation fixes for OMEGA tier
# 4.3.0 - Multi-Language Support (TypeScript/JavaScript/Java/Go/Rust/C#)
# 4.2.1 - CRITICAL BUGFIX: Tier Hierarchy
# 4.2.0 - OMEGA Guardian Release
# 4.1.0 - Unified Package Architecture
# 4.0.1 - REST API release (8 endpoints)
# 4.0.0 - Initial PyPI release
