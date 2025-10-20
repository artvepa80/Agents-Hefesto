# Changelog

All notable changes to Hefesto will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.5.0] - 2025-10-20

### Added - Phase 0 (Free)
- **Enhanced Validation Layer** (`suggestion_validator.py`)
  - AST-based code validation
  - Dangerous pattern detection (eval, exec, pickle, subprocess)
  - Similarity analysis (30-95% sweet spot)
  - Confidence scoring (0.0-1.0)
  - 28 comprehensive tests
  
- **Feedback Loop System** (`feedback_logger.py`)
  - Track suggestion acceptance/rejection
  - Log application success/failure
  - Query acceptance rates by type/severity
  - BigQuery integration
  - 30 comprehensive tests

- **Budget Control** (`budget_tracker.py`)
  - Real-time cost tracking
  - Daily/monthly budget limits
  - HTTP 429 on budget exceeded
  - Cost calculation per model
  - 38 comprehensive tests

- **CLI Interface**
  - `hefesto serve` - Start API server
  - `hefesto info` - Show configuration
  - `hefesto check` - Verify installation
  - `hefesto analyze` - Code analysis (coming soon)

### Added - Phase 1 (Pro)
- **Semantic Code Analyzer** (`semantic_analyzer.py`)
  - ML-based code embeddings (384D)
  - Semantic similarity detection
  - Duplicate suggestion detection (>85% threshold)
  - Lightweight model (80MB)
  - <100ms inference time
  - 21 comprehensive tests

- **License Validation** (`license_validator.py`)
  - Stripe license key validation
  - Feature gating for Pro features
  - Graceful degradation to Free tier

### Changed
- Converted from OMEGA monorepo to standalone package
- Removed OMEGA-specific dependencies
- Added dual licensing (MIT + Commercial)
- Converted to pip-installable package
- Added professional packaging (setup.py, pyproject.toml)

### Documentation
- Professional README for GitHub/PyPI
- Dual license files
- Installation guides
- API reference
- Quick start examples

### Testing
- 209 total tests (96% pass rate)
- Phase 0: 96 tests (100% passing)
- Phase 1: 21 tests (100% passing)
- Core: 92 tests (90% passing)

## [3.0.7] - 2025-10-01

### Added
- BigQuery observability with 5 analytical views
- 92 integration tests
- Complete LLM event tracking
- Iris-Hefesto integration for code findings

### Changed
- Enhanced documentation
- Improved test coverage to 90%

## [3.0.6] - 2025-10-01

### Added
- Gemini API direct integration (40% cost reduction vs Vertex AI)
- 6 successful Cloud Run deployments
- Complete abstract method implementation
- Security validation with real Gemini API

### Fixed
- 3 critical import errors
- Abstract method instantiation
- Masking function naming

## [2.0.0] - 2025-09-15

### Added
- Code Writer module with autonomous fixing
- Patch validator with 71% test coverage
- Git operations (branch, commit, push)
- Security module with PII masking

## [1.0.0] - 2025-08-01

### Added
- Initial release
- Basic code analysis
- Health monitoring
- Vertex AI integration (deprecated in v3.0.6)

---

## Upgrade Guide

### From OMEGA Internal to Standalone

1. **Install package**:
   ```bash
   pip uninstall omega-agents  # If installed
   pip install hefesto
   ```

2. **Update imports**:
   ```python
   # Old
   from Agentes.Hefesto.llm import SuggestionValidator
   
   # New
   from hefesto import SuggestionValidator
   ```

3. **Update configuration**:
   ```bash
   # Old
   export GCP_PROJECT_ID='eminent-carver-469323-q2'
   
   # New
   export GCP_PROJECT_ID='your-project-id'
   ```

---

## Support

For issues, feature requests, or questions:
- GitHub Issues: https://github.com/artvepa80/Agents-Hefesto/issues
- Email: support@narapallc.com
- Pro Support: sales@narapallc.com

