# Changelog

All notable changes to Hefesto will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.0] - 2025-01-23

### 🎉 Major Release: Complete Code Analysis System

This release implements the full **Hefesto Analyzer** - an AI-powered code quality guardian with integrated static analysis, ML-powered validation, and intelligent refactoring capabilities.

### Added - Static Analyzers (FREE)

#### **Complexity Analyzer** (`analyzers/complexity.py`)
- Cyclomatic complexity detection
- Function-level complexity scoring
- Severity levels: MEDIUM (6-10), HIGH (11-20), CRITICAL (21+)
- AST-based analysis with accurate control flow counting
- Detailed refactoring suggestions

#### **Security Analyzer** (`analyzers/security.py`)
- **6 Critical Security Checks**:
  1. Hardcoded secrets (API keys, passwords, tokens)
  2. SQL injection vulnerability detection
  3. Dangerous `eval()` and `exec()` usage
  4. Unsafe `pickle` deserialization
  5. Production `assert` statement detection
  6. Bare `except` clause detection
- Pattern-based detection with regex
- Context-aware false positive filtering

#### **Code Smell Analyzer** (`analyzers/code_smells.py`)
- **8 Code Smell Types**:
  1. Long functions (>50 lines)
  2. Long parameter lists (>5 params)
  3. Deep nesting (>4 levels)
  4. Magic numbers
  5. Duplicate code detection
  6. God classes (>500 lines)
  7. Incomplete TODOs/FIXMEs
  8. Commented-out code
- Comprehensive refactoring suggestions for each smell

#### **Best Practices Analyzer** (`analyzers/best_practices.py`)
- Missing docstrings for public functions/classes
- Poor variable naming (single-letter variables)
- PEP 8 style violations
- Naming convention checks

### Added - Analysis Pipeline

#### **AnalyzerEngine** (`core/analyzer_engine.py`)
- **3-Phase Pipeline Architecture**:
  - **STEP 1**: Static analyzers (4 modules, 22+ checks)
  - **STEP 2**: Phase 0 validation (false positive filtering)
  - **STEP 3**: Phase 1 ML enhancement (PRO feature)
- License-aware feature gating (FREE vs PRO)
- Verbose mode showing pipeline execution
- Graceful degradation if Phase 0/1 unavailable
- Severity threshold filtering
- File/directory exclusion patterns
- Exit code strategy (0 = pass, 1 = critical issues)

#### **Analysis Models** (`core/analysis_models.py`)
- `AnalysisIssue` - Issue representation with severity, location, suggestion
- `AnalysisSummary` - Aggregate statistics
- `AnalysisReport` - Complete report structure
- `AnalysisIssueType` - Type enumeration
- `AnalysisIssueSeverity` - Severity levels (CRITICAL, HIGH, MEDIUM, LOW)

### Added - Reporting System

#### **Text Reporter** (`reports/text_reporter.py`)
- Colorized terminal output with emoji indicators
- Severity-based color coding (RED=critical, YELLOW=high, BLUE=medium, GRAY=low)
- Hierarchical issue display with file grouping
- Summary statistics with breakdown
- Pipeline step visualization
- License tier display

#### **JSON Reporter** (`reports/json_reporter.py`)
- Machine-readable JSON output
- CI/CD integration friendly
- Complete issue metadata
- Structured severity levels

#### **HTML Reporter** (`reports/html_reporter.py`)
- Interactive web-based report
- Syntax-highlighted code snippets
- Filterable issue list
- Executive summary with charts
- Responsive design

### Added - CLI Commands

#### **`hefesto analyze`** (`cli/main.py`)
- Analyze single file or entire directory
- `--severity` filter (LOW, MEDIUM, HIGH, CRITICAL)
- `--output` format (text, json, html)
- `--save-html` for HTML report export
- `--exclude` patterns for directories
- `--verbose` mode for pipeline visibility
- Exit code 0 (no critical) or 1 (critical issues found)

**Examples**:
```bash
# Basic analysis
hefesto analyze myfile.py

# Analyze directory with severity filter
hefesto analyze src/ --severity HIGH

# Generate HTML report
hefesto analyze . --output html --save-html report.html

# Exclude directories
hefesto analyze . --exclude "tests/,docs/,build/"

# Verbose mode
hefesto analyze . --verbose
```

#### **`hefesto install-hook`**
- Install pre-push git hook
- Validates code before every push
- Runs: Black → isort → flake8 → pytest → Hefesto
- Blocks push on CRITICAL/HIGH issues
- Shows actionable fix suggestions

### Added - Pre-Push Hook Integration

#### **Git Pre-Push Hook** (`.git/hooks/pre-push`)
- Automatic code quality validation
- Analyzes only changed Python files
- Uses HIGH severity threshold
- Blocks push if critical issues found
- Clear error messages with fix suggestions
- Filters runtime warnings for clean output
- Bypass option: `git push --no-verify`

**Validation Steps**:
1. Black formatting check
2. isort import sorting
3. flake8 linting
4. pytest unit tests
5. **Hefesto analysis** (blocks on CRITICAL/HIGH)

### Enhanced - Phase 0 Integration

- **Automatic Integration**: AnalyzerEngine automatically uses Phase 0 if available
- **False Positive Filtering**: Validates each issue before reporting
- **Confidence Scoring**: Each issue includes confidence level (0.0-1.0)
- **Context Analysis**: Understands test vs production code
- **Budget Tracking**: Monitors validation costs

### Enhanced - Phase 1 Integration (PRO)

- **Semantic Analysis**: ML-powered code understanding
- **Duplicate Detection**: Find similar code across codebase
- **Confidence Boosting**: Learn from codebase patterns
- **BigQuery Analytics**: Track quality trends over time
- **Pattern Learning**: Personalized analysis based on team style

### Documentation

#### **Professional README** (`README.md`)
- Landing page style introduction
- Feature comparison (FREE vs PRO)
- Quick start guide (30 seconds)
- Usage examples (CLI, SDK, API)
- Architecture diagram
- Pricing table
- Example outputs
- Stats and tech stack

#### **Getting Started Guide** (`docs/GETTING_STARTED.md`)
- 5-minute tutorial
- Installation steps
- First analysis walkthrough
- Output explanation
- Pre-push hook setup
- Testing guide

#### **Analysis Rules Reference** (`docs/ANALYSIS_RULES.md`)
- All 22+ checks documented
- Detailed examples (BAD vs GOOD)
- Severity guidelines
- Decision tree for severity
- Refactoring strategies
- Quick reference table

#### **Integration Architecture** (`docs/INTEGRATION.md`)
- Phase 0+1 architecture deep dive
- License-aware feature gating
- Integration flow diagrams
- SDK usage examples
- Architecture decisions explained

### Changed

- **CLI**: `hefesto analyze` command now fully functional (was placeholder)
- **Pre-Push Hook**: Now runs actual analysis (was showing placeholder message)
- **AnalyzerEngine**: Complete rewrite with Phase 0+1 integration
- **Exit Codes**: Properly returns 1 for critical issues (blocks CI/CD)

### Testing

- Tested with intentional issue files (security, complexity, code smells)
- Verified JSON output format
- Validated HTML report generation
- Tested pre-push hook blocking behavior
- Confirmed exit code strategy works correctly

### Performance

- **Static Analysis**: ~100ms per file
- **Phase 0 Validation**: ~50ms overhead
- **Phase 1 ML**: ~500ms per file (PRO only)
- **Memory**: <200MB for typical projects

### Breaking Changes

- `hefesto analyze` now exits with code 1 for critical issues (breaking for CI/CD)
- Pre-push hook now blocks on HIGH issues (was not blocking before)

---

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
   export GCP_PROJECT_ID='${GCP_PROJECT_ID}'

   # New
   export GCP_PROJECT_ID='your-project-id'
   ```

---

## Support

For issues, feature requests, or questions:
- GitHub Issues: https://github.com/artvepa80/Agents-Hefesto/issues
- Email: support@narapallc.com
- Pro Support: sales@narapallc.com

