"""
Hefesto version information.

The version is now read dynamically from package metadata to ensure
CLI, API, and package metadata stay in sync.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hefesto-ai")
except PackageNotFoundError:
    # Fallback for development/editable installs
    __version__ = "dev"

__api_version__ = "v1"

# Version history
# 4.5.3 - Version Fix
#         - Dynamic version reading from package metadata
#         - Fixes CLI/API version mismatch
# 4.5.2 - Extras[all] Complete
#         - Added tree-sitter and flake8 to [all] extras
# 4.5.1 - CI/CD Hotfixes
#         - tree-sitter dependency fix
#         - Portable pre-push hook
#         - CI scope corrections
# 4.5.0 - Ola 2 DevOps Analyzers + P5 Release Hardening
#         - PowerShellAnalyzer (PS001-PS006)
#         - JsonAnalyzer (J001-J005)
#         - TomlAnalyzer (T001-T003)
#        - MakefileAnalyzer (MF001-MF005)
#         - GroovyJenkinsAnalyzer (GJ001-GJ005)
#         - GitHub Actions CI workflow
#         - Improved pre-push hook
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
