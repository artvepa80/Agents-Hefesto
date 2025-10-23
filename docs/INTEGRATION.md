# 🏗️ Integration Architecture: Phase 0 + Phase 1

**Complete guide to Hefesto's multi-phase analysis pipeline.**

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 0: Validation Layer](#phase-0-validation-layer)
3. [Phase 1: ML Enhancement](#phase-1-ml-enhancement)
4. [License-Aware Architecture](#license-aware-architecture)
5. [Integration Flow](#integration-flow)
6. [SDK Usage](#sdk-usage)
7. [Architecture Decisions](#architecture-decisions)

---

## Overview

Hefesto uses a **3-phase analysis pipeline** to ensure high-quality, accurate code analysis:

```
┌─────────────────────────────────────────────────────────┐
│  INPUT: Python Files                                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  STEP 1: Static Analyzers (FREE)                        │
│  • Complexity Analysis (cyclomatic complexity)          │
│  • Code Smells (long functions, deep nesting, etc.)    │
│  • Security (hardcoded secrets, SQL injection, etc.)   │
│  • Best Practices (docstrings, naming, PEP 8)          │
│                                                         │
│  Output: Raw issues (may include false positives)      │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  STEP 2: Phase 0 - Validation Layer (FREE)              │
│  • False Positive Filtering                             │
│  • AST-Based Verification                               │
│  • Confidence Scoring                                   │
│  • Context-Aware Analysis                               │
│                                                         │
│  Output: Validated issues with confidence scores        │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  STEP 3: Phase 1 - ML Enhancement (PRO)                 │
│  • Semantic Code Analysis                               │
│  • Duplicate Detection (similar code patterns)          │
│  • Confidence Boosting (learn from codebase)           │
│  • BigQuery Analytics Integration                       │
│                                                         │
│  Output: Enhanced analysis with ML insights             │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  OUTPUT: Final Report                                   │
│  • Text (terminal with colors)                          │
│  • JSON (machine-readable)                              │
│  • HTML (interactive report)                            │
└─────────────────────────────────────────────────────────┘
```

### Why Multi-Phase?

1. **Accuracy**: Each phase refines results from previous phase
2. **Performance**: Static analysis is fast; ML is optional
3. **Gradual Enhancement**: FREE users get validation; PRO users get ML
4. **Transparency**: Verbose mode shows what each phase does

---

## Phase 0: Validation Layer

### Purpose

**Problem:** Static analyzers produce false positives that frustrate developers.

**Solution:** Phase 0 validates each issue using multiple techniques to filter false positives.

### Architecture

```python
# hefesto/llm/validators.py (Phase 0 module)

from hefesto.llm.validators import SuggestionValidator, get_validator

class SuggestionValidator:
    """Validates issues and suggestions from static analyzers."""

    def validate(
        self,
        original_code: str,
        suggested_code: str,
        issue_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Multi-layer validation of detected issues.

        Layers:
        1. AST Validation - Ensure code is syntactically valid
        2. Semantic Check - Verify issue actually exists
        3. Confidence Scoring - Rate likelihood of true positive
        4. Context Analysis - Check surrounding code

        Returns:
            ValidationResult with confidence score and safe_to_apply flag
        """
```

### Validation Techniques

#### 1. AST-Based Verification

```python
import ast

def validate_syntax(code: str) -> bool:
    """Verify code is syntactically valid."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False
```

**Use Cases:**
- Verify suggested fixes are valid Python
- Ensure original code parses correctly
- Detect incomplete code snippets

#### 2. False Positive Filtering

```python
# Example: Filter false positives for hardcoded secrets
def is_false_positive_secret(line: str, context: str) -> bool:
    """Check if detected 'secret' is actually a false positive."""

    # Filter test files
    if "test_" in context or "/tests/" in context:
        return True

    # Filter examples and documentation
    if "example" in line.lower() or "sample" in line.lower():
        return True

    # Filter placeholder values
    if "your_api_key_here" in line.lower():
        return True

    # Filter comments
    if line.strip().startswith("#"):
        return True

    return False
```

**Common False Positives Filtered:**
- Test fixtures with fake credentials
- Documentation examples
- Placeholder values in templates
- Comments discussing security

#### 3. Confidence Scoring

```python
def calculate_confidence(issue: AnalysisIssue, context: dict) -> float:
    """
    Calculate confidence score (0.0 - 1.0) for an issue.

    Factors:
    - Pattern match strength
    - Context appropriateness
    - Historical accuracy
    - Code location (test vs prod)
    """
    confidence = 0.5  # Start neutral

    # Increase confidence for strong indicators
    if issue.severity == "CRITICAL":
        confidence += 0.2

    if "eval(" in issue.message and not context.get("is_test"):
        confidence += 0.3

    # Decrease confidence for weak indicators
    if context.get("is_test"):
        confidence -= 0.2

    if "TODO" in context.get("surrounding_lines", ""):
        confidence -= 0.1

    return min(1.0, max(0.0, confidence))
```

**Confidence Levels:**
- **0.0 - 0.3:** Likely false positive (filtered out)
- **0.3 - 0.6:** Uncertain (show with warning)
- **0.6 - 0.8:** Likely valid (show normally)
- **0.8 - 1.0:** Highly confident (emphasize)

#### 4. Context-Aware Analysis

```python
def analyze_context(file_path: str, line_number: int) -> dict:
    """Gather context around an issue for better validation."""

    context = {
        "is_test": "test" in file_path.lower(),
        "is_example": "example" in file_path.lower(),
        "file_type": "test" if "/tests/" in file_path else "production",
    }

    # Read surrounding lines
    with open(file_path, "r") as f:
        lines = f.readlines()
        start = max(0, line_number - 3)
        end = min(len(lines), line_number + 3)
        context["surrounding_lines"] = "".join(lines[start:end])

    # Check for special markers
    if "# hefesto: ignore" in context["surrounding_lines"]:
        context["suppressed"] = True

    return context
```

**Context Factors:**
- File location (test vs production)
- Surrounding code patterns
- Comments and annotations
- Import statements

### Integration with Analyzer Engine

```python
# hefesto/core/analyzer_engine.py

class AnalyzerEngine:
    def __init__(self, enable_validation: bool = True):
        self.enable_validation = enable_validation

        if PHASE_0_AVAILABLE and enable_validation:
            from hefesto.llm.validators import get_validator
            self.validator = get_validator()

    def analyze_path(self, path: str):
        # STEP 1: Run static analyzers
        raw_issues = self._run_static_analyzers(path)

        if self.verbose:
            click.echo(f"   Found {len(raw_issues)} potential issue(s)")

        # STEP 2: Phase 0 validation
        validated_issues = []
        if self.enable_validation and self.validator:
            for issue in raw_issues:
                result = self.validator.validate(
                    original_code=self._get_code_snippet(issue),
                    suggested_code=issue.suggestion or "",
                    issue_type=issue.issue_type.value,
                    context=self._get_context(issue)
                )

                if result.confidence >= 0.3:  # Filter low-confidence
                    issue.confidence = result.confidence
                    validated_issues.append(issue)

        if self.verbose:
            click.echo(f"   {len(validated_issues)} issue(s) validated")

        return validated_issues
```

### Benefits of Phase 0

✅ **Reduced False Positives:** ~40% fewer incorrect warnings
✅ **Higher Trust:** Developers trust results more
✅ **Better Suggestions:** Only show actionable fixes
✅ **Context-Aware:** Understands test vs production code
✅ **Fast:** Pure Python, no external API calls

---

## Phase 1: ML Enhancement

### Purpose

**Problem:** Static analysis can't understand semantic meaning or code similarity.

**Solution:** Phase 1 uses ML models to provide deeper insights (PRO feature only).

### Architecture

```python
# iris/semantic_analyzer.py (Phase 1 module)

from iris.semantic_analyzer import SemanticAnalyzer

class SemanticAnalyzer:
    """ML-powered semantic code analysis (PRO feature)."""

    def __init__(self):
        # Load sentence transformer model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.bigquery_client = self._init_bigquery()

    def analyze_semantics(
        self,
        code_snippet: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SemanticAnalysisResult:
        """
        Analyze code semantics using ML.

        Capabilities:
        1. Code embedding generation
        2. Semantic duplicate detection
        3. Pattern learning from codebase
        4. Confidence boosting based on history
        """
```

### ML Capabilities

#### 1. Semantic Code Embeddings

```python
def generate_embedding(self, code: str) -> np.ndarray:
    """
    Convert code to semantic vector embedding.

    Uses sentence transformers to understand code meaning,
    not just syntax.
    """
    # Normalize code (remove comments, whitespace)
    normalized = self._normalize_code(code)

    # Generate embedding (384-dimensional vector)
    embedding = self.model.encode(normalized)

    return embedding
```

**Use Cases:**
- Find semantically similar code (duplicates)
- Understand code intent
- Compare fix suggestions
- Cluster related issues

**Example:**
```python
# These are semantically similar (different syntax, same meaning)
code1 = "if x > 10: return True else: return False"
code2 = "return x > 10"

# Embeddings will be very close in vector space
embedding1 = analyzer.generate_embedding(code1)
embedding2 = analyzer.generate_embedding(code2)

similarity = cosine_similarity(embedding1, embedding2)
# similarity ≈ 0.92 (very similar)
```

#### 2. Duplicate Detection

```python
def find_duplicates(
    self,
    codebase_embeddings: List[Tuple[str, np.ndarray]],
    threshold: float = 0.85
) -> List[DuplicateGroup]:
    """
    Find semantically similar code across codebase.

    Args:
        codebase_embeddings: List of (file_path, embedding) tuples
        threshold: Similarity threshold (0.85 = 85% similar)

    Returns:
        Groups of similar code blocks
    """
    duplicates = []

    for i, (file1, emb1) in enumerate(codebase_embeddings):
        for j, (file2, emb2) in enumerate(codebase_embeddings[i+1:]):
            similarity = cosine_similarity(emb1, emb2)

            if similarity >= threshold:
                duplicates.append(DuplicateGroup(
                    files=[file1, file2],
                    similarity=similarity,
                    suggestion="Consider extracting to shared function"
                ))

    return duplicates
```

**Output Example:**
```
🔍 ML Analysis: Duplicate Code Detected

  📄 src/user_service.py:45-60
  📄 src/order_service.py:120-135
  ├─ Similarity: 91%
  └─ Suggestion: Extract validation logic to shared validator

  Potential savings: 15 lines, improved maintainability
```

#### 3. Confidence Boosting

```python
def boost_confidence(
    self,
    issue: AnalysisIssue,
    codebase_history: List[AnalysisIssue]
) -> float:
    """
    Increase confidence based on codebase patterns.

    If similar issues were found and fixed before,
    increase confidence in new detection.
    """
    base_confidence = issue.confidence or 0.5

    # Find similar past issues
    issue_embedding = self.generate_embedding(issue.message)
    similar_issues = self._find_similar_issues(
        issue_embedding,
        codebase_history
    )

    # Boost confidence if pattern is consistent
    if len(similar_issues) >= 3:
        base_confidence += 0.15

    # Check if fixes were accepted (from git history)
    accepted_fixes = sum(1 for i in similar_issues if i.was_fixed)
    acceptance_rate = accepted_fixes / len(similar_issues)

    if acceptance_rate > 0.7:
        base_confidence += 0.10

    return min(1.0, base_confidence)
```

**Example:**
```
🧠 ML Enhancement: Confidence Boosted

  Original confidence: 65%
  → Similar issues found: 5 times
  → Previously accepted fixes: 4/5 (80%)
  → Boosted confidence: 90% ✨

  This pattern has been validated in your codebase.
```

#### 4. Pattern Learning

```python
def learn_patterns(
    self,
    codebase_path: str,
    upload_to_bigquery: bool = True
) -> PatternLibrary:
    """
    Learn common patterns from your codebase.

    Creates a fingerprint of your team's coding style,
    allowing more personalized analysis over time.
    """
    patterns = PatternLibrary()

    # Analyze all Python files
    for file_path in glob.glob(f"{codebase_path}/**/*.py", recursive=True):
        tree = ast.parse(open(file_path).read())

        # Extract patterns
        patterns.function_naming.update(self._extract_naming_patterns(tree))
        patterns.error_handling.update(self._extract_error_patterns(tree))
        patterns.architecture.update(self._extract_arch_patterns(tree))

    # Upload to BigQuery for analytics
    if upload_to_bigquery:
        self._upload_patterns(patterns)

    return patterns
```

**Learned Patterns:**
- Naming conventions (snake_case vs camelCase preferences)
- Error handling styles (try/except vs if/else)
- Import organization patterns
- Documentation styles
- Test patterns

#### 5. BigQuery Analytics Integration

```python
def upload_analysis_results(
    self,
    report: AnalysisReport,
    project_id: str
):
    """
    Upload analysis results to BigQuery for tracking.

    Enables:
    - Trend analysis over time
    - Team-wide metrics
    - Bottleneck identification
    - Quality score tracking
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)

    table_id = f"{project_id}.hefesto_analytics.analysis_results"

    rows_to_insert = [
        {
            "timestamp": datetime.now().isoformat(),
            "project": report.project_name,
            "files_analyzed": report.summary.files_analyzed,
            "total_issues": report.summary.total_issues,
            "critical_count": report.summary.critical_count,
            "high_count": report.summary.high_count,
            "medium_count": report.summary.medium_count,
            "low_count": report.summary.low_count,
            "avg_complexity": report.metrics.avg_complexity,
            "duplicate_blocks": report.metrics.duplicate_blocks,
        }
    ]

    errors = client.insert_rows_json(table_id, rows_to_insert)

    if errors:
        logger.error(f"BigQuery insert errors: {errors}")
```

**Analytics Dashboard (PRO):**
```
📊 Code Quality Trends (Last 30 Days)

  Critical Issues: 12 → 2 ✅ (-83%)
  Avg Complexity:  15 → 8 ✅ (-47%)
  Duplicates:      23 → 9 ✅ (-61%)

  🏆 Quality Score: 82/100 (+15 from last month)

  Top Issue Types:
  1. Long functions (28%)
  2. Missing docstrings (19%)
  3. Deep nesting (15%)
```

### Integration with Analyzer Engine

```python
# hefesto/core/analyzer_engine.py

class AnalyzerEngine:
    def __init__(self, enable_ml: bool = True):
        self.ml_enabled = False

        # Check for PRO license
        if PHASE_0_AVAILABLE:
            validator = get_license_validator()
            license_info = validator.get_info()
            self.has_pro_license = license_info.get("is_pro", False)

        # Load Phase 1 if PRO
        if enable_ml and self.has_pro_license and PHASE_1_AVAILABLE:
            from iris.semantic_analyzer import SemanticAnalyzer
            self.semantic_analyzer = SemanticAnalyzer()
            self.ml_enabled = True

    def analyze_path(self, path: str):
        # STEP 1: Static analyzers
        raw_issues = self._run_static_analyzers(path)

        # STEP 2: Phase 0 validation
        validated_issues = self._validate_issues(raw_issues)

        # STEP 3: Phase 1 ML enhancement (if PRO)
        if self.ml_enabled:
            enhanced_issues = []
            for issue in validated_issues:
                # Boost confidence using ML
                ml_confidence = self.semantic_analyzer.boost_confidence(
                    issue,
                    codebase_history=self._get_history()
                )
                issue.confidence = max(issue.confidence, ml_confidence)
                enhanced_issues.append(issue)

            # Find semantic duplicates
            duplicates = self.semantic_analyzer.find_duplicates(
                self._generate_codebase_embeddings(path)
            )

            # Add duplicate issues
            for dup in duplicates:
                enhanced_issues.append(self._create_duplicate_issue(dup))

            if self.verbose:
                click.echo(f"   ML enhancement added {len(duplicates)} duplicate(s)")

            return enhanced_issues
        else:
            if self.verbose:
                click.echo("   💡 Upgrade to PRO for ML-powered analysis")

            return validated_issues
```

### Benefits of Phase 1 (PRO)

✅ **Semantic Understanding:** Goes beyond syntax to meaning
✅ **Duplicate Detection:** Finds similar code across codebase
✅ **Learning Over Time:** Gets smarter with your patterns
✅ **Analytics Dashboard:** Track trends and improvements
✅ **Higher Confidence:** ML-boosted confidence scores

---

## License-Aware Architecture

### License Detection

```python
# hefesto/llm/validators.py

def get_license_validator():
    """Get license validator with automatic tier detection."""
    try:
        from hefesto.config.stripe_config import StripeConfig
        stripe_config = StripeConfig()

        # Check active subscription
        if stripe_config.has_active_subscription():
            return LicenseValidator(tier="PRO")

    except ImportError:
        pass

    return LicenseValidator(tier="FREE")

class LicenseValidator:
    def __init__(self, tier: str = "FREE"):
        self.tier = tier

    def get_info(self) -> dict:
        return {
            "tier": self.tier,
            "is_pro": self.tier == "PRO",
            "ml_enabled": self.tier == "PRO",
            "bigquery_enabled": self.tier == "PRO",
        }
```

### Feature Gating

```python
class AnalyzerEngine:
    def __init__(self):
        # Detect license tier
        license_info = self._detect_license()

        self.tier = license_info["tier"]
        self.has_pro = license_info["is_pro"]

        # Gate Phase 1 features behind PRO
        if self.has_pro:
            self._enable_ml_features()
        else:
            self._show_pro_upgrade_message()

    def _show_pro_upgrade_message(self):
        """Show upgrade message for FREE users."""
        if self.verbose:
            click.echo("")
            click.echo("⏭️  Step 3/3: ML enhancement skipped (FREE tier)")
            click.echo("   💡 Upgrade to PRO for:")
            click.echo("      • Semantic code analysis")
            click.echo("      • Duplicate detection")
            click.echo("      • BigQuery analytics")
            click.echo("      • Confidence boosting")
            click.echo("")
            click.echo("   Try 14-day free trial: https://buy.stripe.com/hefesto-pro-trial")
```

### Graceful Degradation

```python
# If Phase 0 or Phase 1 unavailable, system still works

try:
    from hefesto.llm.validators import get_validator
    PHASE_0_AVAILABLE = True
except ImportError:
    PHASE_0_AVAILABLE = False
    logger.warning("Phase 0 validation unavailable")

try:
    from iris.semantic_analyzer import SemanticAnalyzer
    PHASE_1_AVAILABLE = True
except ImportError:
    PHASE_1_AVAILABLE = False
    logger.warning("Phase 1 ML enhancement unavailable")

# System works with just static analyzers if needed
```

---

## Integration Flow

### Complete Flow Diagram

```
                    START
                      ↓
          ┌───────────────────────┐
          │  Detect License Tier  │
          └───────────────────────┘
                      ↓
         ┌─────────────────────────┐
         │    Load Analyzers       │
         │  • Complexity           │
         │  • Code Smells          │
         │  • Security             │
         │  • Best Practices       │
         └─────────────────────────┘
                      ↓
         ┌─────────────────────────┐
         │  STEP 1: Static Analysis│
         │  Run all analyzers      │
         │  Output: raw_issues     │
         └─────────────────────────┘
                      ↓
                Is Phase 0 available?
                 ↙ Yes        No ↘
    ┌─────────────────────┐    Skip to Step 3
    │ STEP 2: Validation  │
    │  • Filter FPs       │
    │  • Score confidence │
    │  • Add context      │
    └─────────────────────┘
                ↓
         Is PRO license?
         ↙ Yes      No ↘
┌──────────────────┐    Skip ML
│ STEP 3: ML Boost │
│  • Embeddings    │
│  • Duplicates    │
│  • Confidence+   │
│  • Analytics     │
└──────────────────┘
        ↓            ↓
   ┌─────────────────────────┐
   │  Generate Report        │
   │  • Text / JSON / HTML   │
   │  • Apply severity filter│
   │  • Sort by severity     │
   └─────────────────────────┘
                ↓
   ┌─────────────────────────┐
   │  Return Exit Code       │
   │  • 0 if no critical     │
   │  • 1 if critical found  │
   └─────────────────────────┘
                ↓
               END
```

---

## SDK Usage

### Basic Usage (FREE)

```python
from hefesto import get_validator
from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.analyzers import (
    ComplexityAnalyzer,
    SecurityAnalyzer,
    CodeSmellAnalyzer,
    BestPracticesAnalyzer
)

# Create analyzer with Phase 0 validation
engine = AnalyzerEngine(
    severity_threshold="MEDIUM",
    enable_validation=True,  # Phase 0
    enable_ml=False,         # No ML in FREE tier
    verbose=True
)

# Register analyzers
engine.register_analyzer(ComplexityAnalyzer())
engine.register_analyzer(SecurityAnalyzer())
engine.register_analyzer(CodeSmellAnalyzer())
engine.register_analyzer(BestPracticesAnalyzer())

# Run analysis
report = engine.analyze_path("src/")

# Access results
print(f"Total issues: {report.summary.total_issues}")
print(f"Critical: {report.summary.critical_count}")

for issue in report.issues:
    if issue.severity == "CRITICAL":
        print(f"  {issue.file_path}:{issue.line}")
        print(f"  {issue.message}")
```

### Advanced Usage (PRO)

```python
from hefesto.core.analyzer_engine import AnalyzerEngine

# Create analyzer with full ML features
engine = AnalyzerEngine(
    severity_threshold="LOW",
    enable_validation=True,  # Phase 0
    enable_ml=True,          # Phase 1 (PRO)
    verbose=True
)

# Register all analyzers
engine.register_all_analyzers()

# Run full analysis with ML
report = engine.analyze_path(
    "src/",
    exclude_patterns=["tests/", "docs/", "build/"]
)

# Access ML-enhanced results
print(f"ML confidence boost applied: {report.ml_stats.confidence_boosted}")
print(f"Duplicates found: {report.ml_stats.duplicates_found}")

# Upload to BigQuery for analytics
if engine.ml_enabled:
    engine.semantic_analyzer.upload_analysis_results(
        report,
        project_id="my-gcp-project"
    )
```

### Validation-Only Usage

```python
from hefesto import get_validator

# Get Phase 0 validator
validator = get_validator()

# Validate a single suggestion
result = validator.validate(
    original_code="x = eval(user_input)",
    suggested_code="x = json.loads(user_input)",
    issue_type="security",
    context={"file_path": "src/api.py", "is_test": False}
)

print(f"Confidence: {result.confidence:.0%}")
print(f"Safe to apply: {result.safe_to_apply}")
print(f"Explanation: {result.explanation}")
```

---

## Architecture Decisions

### Why Separate Phases?

**Decision:** Split validation (Phase 0) and ML (Phase 1) into separate phases.

**Rationale:**
- **Performance:** Static + validation is fast (~100ms/file); ML is slower (~500ms/file)
- **Cost:** ML requires API calls and compute; validation is free
- **Licensing:** Allows FREE tier with validation; PRO tier with ML
- **Transparency:** Users see what each phase contributes

**Trade-offs:**
- More complex codebase
- Requires license detection logic
- Need graceful degradation

### Why Not Full ML?

**Decision:** Use static analysis + validation as base; ML as enhancement.

**Rationale:**
- **Reliability:** Static analysis is deterministic and fast
- **Cost:** Running ML on every analysis is expensive
- **Offline:** Static analysis works without internet
- **Explainability:** Static rules are easier to understand

**Trade-offs:**
- ML insights only available to PRO users
- Duplicate detection limited to PRO

### Why BigQuery?

**Decision:** Use BigQuery for analytics storage.

**Rationale:**
- **Scalability:** Handles millions of analysis results
- **SQL Interface:** Easy querying for dashboards
- **Integration:** Works well with Google Cloud ecosystem
- **Cost:** Pay only for storage + queries used

**Trade-offs:**
- Requires GCP account
- Additional setup for users
- Data privacy considerations

### Why Sentence Transformers?

**Decision:** Use `all-MiniLM-L6-v2` model for code embeddings.

**Rationale:**
- **Size:** 80MB model, runs on CPU
- **Speed:** ~50ms per embedding
- **Quality:** Good semantic understanding
- **Offline:** No API calls needed

**Trade-offs:**
- Not specialized for code (generic sentence model)
- Could use code-specific models (CodeBERT, etc.)
- Limited to 384-dimensional embeddings

---

## 📚 Related Documentation

- **[Getting Started](GETTING_STARTED.md)** - Quick tutorial
- **[Analysis Rules](ANALYSIS_RULES.md)** - All 22+ checks explained
- **[CLI Reference](CLI_REFERENCE.md)** - Command-line usage
- **[API Reference](API_REFERENCE.md)** - Complete SDK docs

---

<div align="center">

**Questions?** Open an issue or check the [FAQ](FAQ.md).

**Built with ❤️ by [Narapa LLC](https://narapallc.com)**

Miami, Florida • Copyright © 2025

</div>
