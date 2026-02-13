# Hefesto - AI Code Quality Guardian - Claude Code Guidelines
## Enterprise Code Quality & Security Development Standards

---

## 0. Agent Procedural Workflow (MANDATORY)

### Session Start Checklist

On start of ANY task or session, the agent MUST read these files in order:

1. `CLAUDE.md` (this file — project rules and standards)
2. `docs/CLAUDE_HEFESTO.md` (Hefesto-specific development guidelines and architecture)
3. `MEMORY.md` (project status, pending blockers, credentials context)
4. `CHANGELOG.md` (recent changes, current version)
5. `README.md` (public-facing docs, version badge, feature table)
6. `task.md` and `walkthrough.md` (if present — task-specific context)

Do NOT skip this step. Do NOT guess project state from memory.

### Socratic-Adaptive Method (MSA)

**Principle:** Before acting, understand. Before proposing, diagnose.

**Phase 1 — Diagnosis (always)**
- Read the relevant code before proposing changes.
- Ask yourself: "What already exists that solves this partially or fully?"
- Document findings with concrete file paths and line numbers.
- If evidence contradicts the task, report it before proceeding.

**Phase 2 — Decision (max 2 questions to user)**
- Ask only if truly blocking (ambiguity, destructive action, 2+ valid approaches).
- If not blocking, proceed with **explicit safe assumptions**: "Assuming X (safe default). Proceeding."
- Never ask what you can resolve by reading the repo.

**Phase 3 — Execution (minimal diffs)**
- Reuse what exists before creating new modules.
- Every change must have evidence: "Changed X because Y (found in `file:line`)."
- If a plan requires >3 new files, question whether it can be done with fewer.

**Phase 4 — Verification (mandatory)**
- Run repo verifiers before declaring complete.
- Compare expected result vs actual result.
- If something fails, diagnose (Phase 1) before retrying.

**Anti-patterns to avoid:**
- Inventing command outputs that you did not execute.
- Proposing folder structures without checking what already exists.
- Responding with generic plans without reading the current code.
- Assuming a feature does not exist without searching first.

### Session End Checklist

After completing ANY non-trivial work:

- [ ] Update impacted docs (at minimum `CHANGELOG.md`; `README.md` if version/features changed).
- [ ] Run repo verification: `source venv/bin/activate && black --check hefesto/ tests/ && isort --check hefesto/ tests/ && flake8 hefesto/ tests/ && pytest tests/ -q`
- [ ] Commit with Conventional Commits format, then push the branch.
- [ ] Never move/delete tags without explicit user approval.
- [ ] Update `MEMORY.md` if project status changed (new blockers, resolved items, version bumps).

### PyPI Publishing Rule

- If `MEMORY.md` indicates PyPI auth or email verification is pending, treat PyPI publish as **DEFERRED**.
- Still prepare release readiness (docs parity, tag alignment, build check), but do NOT attempt upload.
- When the blocker is resolved, follow the re-publish steps documented in `MEMORY.md`.

## Instrucciones para Claude Code

### Entorno Virtual
- El entorno virtual está en `venv/` (si existe)
- Para activar: `source venv/bin/activate`
- Para instalar dependencias: activar primero, luego `pip install <package>`
- Después de instalar, actualizar: `pip freeze > requirements.txt`

### Deployment
- Paquete PyPI: `hefesto-ai`
- Comando de instalación: `pip install hefesto-ai[pro]` o `pip install hefesto-ai[omega]`
- Publicación: `python3 -m build && twine upload dist/*`

### Estructura del Proyecto
- **Core**: `/hefesto/core/` (engine, scanner)
- **Analyzers**: `/hefesto/analyzers/` (complexity, duplicates, semantic)
- **Security**: `/hefesto/security/` (vulnerability scanning, masking)
- **LLM**: `/hefesto/llm/` (AI provider abstraction, Vertex/Claude/OpenAI)
- **API**: `/hefesto/api/` (REST API endpoints)
- **CLI**: `/hefesto/cli/` (command-line interface)
- **OMEGA**: `/hefesto/omega/` (IRIS agent, correlation engine)
- **Licensing**: `/hefesto/licensing/` (3-tier validation)
- **Tests**: `/tests/` (unit, integration, empirical)

### URLs de Producción
- PyPI: https://pypi.org/project/hefesto-ai/
- Stripe PRO: https://buy.stripe.com/4gM00i6jE6gV3zE4gg
- Stripe OMEGA: https://buy.stripe.com/14A9AS23o20Fgmqb5Q
- GitHub: https://github.com/artvepa80/Agents-Hefesto

### Estilo de Código
- Formatter: `black` (line-length: 100)
- Import sorting: `isort`
- Type checking: `mypy --strict`
- Linting: `flake8`
- No emojis en código (solo en docs de marketing)

---

## 🎯 **Purpose & Mission**

These rules ensure Hefesto achieves enterprise-grade quality, maintainability, safety, and developer velocity for AI-powered code quality validation.

**MUST** rules are enforced by CI/testing; **SHOULD** rules are strongly recommended.

**Mission**: Build the world's most trusted AI code quality guardian that catches critical bugs before production. Self-validated (dogfooding) to catch 3+ critical bugs in its own v4.0.1 release.

**Current Status (v4.8.5)**:
- 3-tier licensing (FREE/PRO/OMEGA)
- 8 REST API endpoints
- BigQuery integration
- IRIS Agent production monitoring
- 42 tests passing (CI green)
- 21 language/format analyzers
- Self-validated (dogfooding successful)
- GitHub Release automation (hardened workflow)

---

## 1️⃣ **BEFORE CODING - Code Quality Requirements**

### 🔍 **Discovery & Validation**
- **BP-1 (MUST)** Ask the user clarifying questions about code quality requirements
- **BP-2 (SHOULD)** Draft and confirm approach for complex analysis features
- **BP-3 (SHOULD)** If ≥ 2 approaches exist, list clear pros/cons with security considerations
- **BP-4 (MUST)** Validate business value: How does this feature help catch critical bugs?
- **BP-5 (MUST)** Confirm tier placement (FREE/PRO/OMEGA)

### 🛡️ **Security & Code Quality Domain Validation**
- **BP-6 (MUST)** Verify vulnerability detection accuracy requirements
- **BP-7 (MUST)** Confirm false positive rates are acceptable (<5% target)
- **BP-8 (MUST)** Validate real-time analysis performance (<100ms for small files)
- **BP-9 (MUST)** Check enterprise client expectations and SLA requirements

---

## 2️⃣ **WHILE CODING - Enterprise Code Quality Standards**

### 🧪 **Test-Driven Development (Security-Specific)**
- **C-1 (MUST)** Follow TDD: scaffold stub → write failing test → implement → validate
- **C-2 (MUST)** Every vulnerability detector needs accuracy benchmark tests
- **C-3 (MUST)** All analyzers must handle edge cases (malformed code, empty files, huge files)

### 🏗️ **Architecture & Naming**
- **C-4 (MUST)** Use domain vocabulary consistently (analyzer, validator, issue, severity, finding)
- **C-5 (SHOULD NOT)** Introduce classes when simple analysis functions suffice
- **C-6 (SHOULD)** Prefer composable, testable analysis functions
- **C-7 (MUST)** Use branded types for domain entities
- **C-8 (MUST)** Never use exec() or eval() without explicit validation (dogfooding caught this!)

### 📊 **Code Analysis & Performance**
- **C-9 (MUST)** All LLM integrations must include timeout and retry logic
- **C-10 (MUST)** Cache analysis results appropriately (file hash-based)
- **C-11 (MUST)** Log analysis metrics for every scan execution
- **C-12 (SHOULD NOT)** Add comments except for critical security caveats

### 🔒 **Memory & Resource Management**
- **C-13 (MUST)** All ML model operations must include memory cleanup
- **C-14 (MUST)** File analysis must stream large files (no full load into memory)
- **C-15 (MUST)** Monitor memory usage during batch analysis

---

## 3️⃣ **TESTING - Code Quality Validation**

### 🏆 **The 4-Level Testing Pyramid (MANDATORY)**

#### Level 1: Unit Tests
```python
def test_complexity_analyzer():
    code = "def simple(): return 42"
    result = ComplexityAnalyzer().analyze(code)
    assert result.cyclomatic_complexity == 1
    assert result.cognitive_complexity == 0

def test_hardcoded_secret_detector():
    code = 'password = "admin123"'
    issues = SecurityAnalyzer().scan(code)
    assert len(issues) == 1
    assert issues[0].type == "hardcoded_secret"
    assert issues[0].severity == "CRITICAL"
```

#### Level 2: Smoke Tests
```python
def test_hefesto_initialization():
    engine = HefestoEngine(api_key="test_key")
    assert engine.initialize() == True
    assert engine.logger is not None
    assert engine.cache is not None

def test_all_analyzers_load():
    analyzers = ['complexity', 'security', 'semantic', 'duplication']
    for analyzer_type in analyzers:
        analyzer = AnalyzerFactory.create(analyzer_type)
        assert analyzer is not None
```

#### Level 3: Canary Tests
```python
def test_real_file_analysis():
    filepath = "tests/fixtures/sample_code.py"
    results = HefestoEngine().analyze_file(filepath)
    assert len(results.issues) > 0
    assert results.processing_time_ms < 1000

def test_known_vulnerability_detection():
    code = load_vulnerable_code_sample()
    issues = SecurityAnalyzer().scan(code)
    assert any(i.type == "sql_injection" for i in issues)
```

#### Level 4: Empirical Tests (Dogfooding)
```python
def test_self_validation_accuracy():
    # Run Hefesto on its own codebase
    results = HefestoEngine().analyze_directory("hefesto/")

    # Should catch known issues (from v4.0.1 dogfooding)
    critical_issues = [i for i in results.issues if i.severity == "CRITICAL"]
    assert len(critical_issues) == 0  # We fixed them all!

    # Should maintain quality standards
    assert results.overall_score > 85

def test_benchmark_against_known_bugs():
    test_cases = load_cve_test_cases()
    detection_rate = 0
    for test_case in test_cases:
        issues = SecurityAnalyzer().scan(test_case.code)
        if any(i.type == test_case.expected_type for i in issues):
            detection_rate += 1

    accuracy = detection_rate / len(test_cases)
    assert accuracy > 0.95  # >95% detection rate
```

### 📊 **Test Requirements**
- **T-1 (MUST)** Separate analyzer logic tests from LLM integration tests
- **T-2 (SHOULD)** Prefer integration tests with real code over heavy mocking
- **T-3 (MUST)** Test edge cases: empty files, malformed syntax, huge files, unicode
- **T-4 (MUST)** Use real vulnerable code samples, not synthetic test data
- **T-5 (MUST)** Test boundary conditions (0 issues, 1000+ issues)

---

## 4️⃣ **QUALITY GATES - Enterprise Standards**

### 🔧 **Automated Validation**
- **G-1 (MUST)** `pytest --cov=90` coverage minimum
- **G-2 (MUST)** `black --check` and `isort --check` formatting passes
- **G-3 (MUST)** `mypy --strict` type checking passes
- **G-4 (MUST)** `flake8` linting passes
- **G-5 (MUST)** Self-validation passes (run Hefesto on itself)
- **G-6 (MUST)** No `exec()` or `eval()` usage without explicit security review

### 📊 **Performance Gates**
- **G-7 (MUST)** Analysis latency <100ms for small files (<1KB)
- **G-8 (MUST)** LLM API calls must have <30s timeout
- **G-9 (MUST)** Memory usage <500MB for single file analysis
- **G-10 (MUST)** All analyzers must log performance metrics

---

## 5️⃣ **GIT & DEPLOYMENT**

### 📝 **Commit Standards**
```
feat(security): add XSS vulnerability detector
fix(api): handle timeout errors in batch analysis
test(analyzers): add empirical complexity validation
```

- **GH-1 (MUST)** Use Conventional Commits format
- **GH-2 (SHOULD NOT)** Refer to Claude/AI in commit messages
- **GH-3 (MUST)** Include domain context in commit scope

### 🚀 **Deployment Requirements**
- **GH-4 (MUST)** PyPI deployments require passing all quality gates
- **GH-5 (MUST)** Version bumps follow semver strictly
- **GH-6 (MUST)** Include changelog entry for every release
- **GH-7 (MUST)** Run dogfooding validation before publishing to PyPI

---

## 🛠️ **HEFESTO SHORTCUTS**

### **QNEW**
```
Understand all Hefesto best practices.
Your code MUST follow enterprise code quality standards.
Support 3 tiers: FREE, PRO ($8/mo), OMEGA Guardian ($19/mo).
Every feature must contribute to catching critical bugs before production.
```

### **QPLAN**
```
Analyze existing Hefesto codebase and ensure your plan:
- Leverages proven analyzer components
- Follows security domain patterns consistently
- Minimizes changes to battle-tested systems
- Includes performance benchmarking
```

### **QCODE**
```
Implement your code quality plan with mandatory testing:
1. Run all 4 test levels (Unit → Smoke → Canary → Empirical)
2. Validate vulnerability detection accuracy
3. Check memory usage (must stay <500MB per file)
4. Run formatting and type checking
5. Run dogfooding (Hefesto on itself)
```

### **QSEC** (Security-Specific)
```
Validate this security feature:
1. Does it improve vulnerability detection accuracy?
2. Does it handle malicious code safely (no exec/eval)?
3. Is false positive rate acceptable (<5%)?
4. Does it contribute to enterprise readiness?
5. Are security edge cases handled properly?
```

### **QDOG** (Dogfooding Validation)
```
Run Hefesto on itself:
1. Analysis accuracy vs known issues
2. Self-validation passes (no new critical issues)
3. Performance metrics acceptable
4. Memory usage within limits
5. All quality gates pass
```

---

## 🏆 **SUCCESS FRAMEWORK**

### 📈 **Development Process**
1. **Start**: `qnew` → understand enterprise standards
2. **Plan**: `qsec` → validate security requirements
3. **Code**: `qcode` → implement with 4-level testing
4. **Validate**: `qdog` → run dogfooding validation
5. **Deploy**: Professional deployment to PyPI

### 🎯 **Success Metrics**
- **Detection Accuracy**: >95% for known vulnerabilities
- **False Positive Rate**: <5%
- **Performance**: <100ms per file, <500MB memory
- **Code Quality**: >90% test coverage
- **Dogfooding**: Hefesto validates itself successfully

---

## ⚠️ **CRITICAL SUCCESS FACTORS**

### 🔍 **Dogfooding Story (v4.0.1)**

Hefesto caught in its own codebase:
1. **Hardcoded password** in test fixtures → CRITICAL → FIXED
2. **Dangerous exec() call** in dynamic loader → HIGH → FIXED
3. **155 other issues** → FIXED

This proves Hefesto works. Use this as marketing.

### 🛡️ **Security Requirements**

**Never Log Secrets**
- **S-1 (MUST)** Use `security.masking` module for all logging
- **S-2 (MUST)** Never store actual secret values
- **S-3 (MUST)** Mask secrets in error messages

**Safe Code Handling**
- **S-4 (MUST)** Never use exec() or eval() on user code
- **S-5 (MUST)** Use AST parsing for code analysis
- **S-6 (MUST)** Sandbox all LLM-generated code suggestions
- **S-7 (MUST)** Validate file paths (prevent path traversal)

---

## 📋 **TIER-SPECIFIC FEATURES**

### FREE Tier
- Basic static analysis
- Basic security scanning
- CLI commands
- Pre-push hooks

### PRO Tier ($8/month)
- SemanticAnalyzer (AI/ML)
- Advanced security scanning
- REST API (8 endpoints)
- BigQuery integration
- Duplicate detection

### OMEGA Guardian ($19/month)
- Everything in PRO
- IRIS Agent (production monitoring)
- HefestoEnricher (auto-correlation)
- Real-time alerts
- Production incident tracking

---

## 🌐 **LLM PROVIDER SUPPORT**

Supported providers:
1. **Vertex AI** (Gemini) - Default, production-ready
2. **Claude** (Anthropic) - Premium option
3. **OpenAI** - Future support planned

**Provider Requirements**
- **LP-1 (MUST)** All providers must implement LLMProvider interface
- **LP-2 (MUST)** All providers must handle rate limiting
- **LP-3 (MUST)** All providers must mask sensitive data in prompts
- **LP-4 (MUST)** All providers must log usage metrics

---

## 📦 **QUICK REFERENCE**

### Installation
```bash
# FREE tier
pip install hefesto-ai

# PRO tier
pip install hefesto-ai[pro]
export HEFESTO_LICENSE_KEY="HFST-XXXX-XXXX-XXXX-XXXX"

# OMEGA Guardian
pip install hefesto-ai[omega]
export HEFESTO_LICENSE_KEY="HFST-XXXX-XXXX-XXXX-XXXX"
```

### Testing
```bash
# Run all tests
pytest tests/ --cov=hefesto --cov-report=html

# Quality gates
black --check hefesto/ tests/
isort --check hefesto/ tests/
mypy hefesto/ --strict
flake8 hefesto/ tests/

# Dogfooding
hefesto analyze . --severity MEDIUM
```

### Deployment (Automated)

Releases are automated via GitHub Actions:

1.  **TestPyPI (Release Candidate)**
    ```bash
    # Push RC tag (triggers release-testpypi.yml)
    git tag v4.7.1-rc.1
    git push origin v4.7.1-rc.1
    ```

2.  **PyPI (Production)**
    ```bash
    # Update version in pyproject.toml FIRST
    # Push final tag (triggers release.yml + Cloud Run Prod)
    git tag v4.7.1
    git push origin v4.7.1
    ```

3.  **GitHub Release** (automatic)
    - The hardened `release.yml` now creates GitHub Releases automatically on tag push.
    - Build artifacts (wheel + sdist) are attached to the release.
    - If PyPI publish fails (e.g., email verification pending), the release is still created.

---

**Remember**: We're building the **world's most trusted AI code quality guardian** - enterprise-grade, profitable, and proven through dogfooding.

---

*Copyright © 2025 Narapa LLC, Miami, Florida*
*Hefesto Enterprise Development Standards v1.0*
*Adapted from OMEGA Sports Analytics Claude Code Methodology*
