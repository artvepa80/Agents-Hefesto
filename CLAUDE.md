# HefestoAI — release truth engine for AI-generated code — Claude Code Guidelines
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

Internal work logs and handoffs are kept outside this public repository; do not add them here (the guard rejects `docs/worklog/`).

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
- [ ] Run repo verification (the CI `lint-and-test` steps in the same order, with `pip install -e ".[dev,lint]"`; the "Check Docs Emails" grep step of CI is left out here): `python scripts/guard_public_repo.py && ruff check && python -m mypy hefesto --ignore-missing-imports && python -m black --check hefesto tests && python -m isort --check-only hefesto tests && python -m flake8 hefesto tests && python scripts/verify_capabilities.py && python scripts/verify_readme.py && python scripts/verify_server_json.py && HEFESTO_TELEMETRY=0 python -m pytest -q -m "not integration and not slow"`
- [ ] The changed-file gate is `.github/workflows/dogfood.yml` (`dogfood-hefesto`), on pull requests against the base commit and on pushes to `main`. It runs `python -m ruff check --force-exclude` (no `--fix`) on changed `.py` files, so `[tool.ruff]` `extend-exclude` applies, then `HEFESTO_TELEMETRY=0 python -m hefesto analyze <changed files> --severity medium --fail-on critical --allow-no-files`. `python scripts/dogfood_changed.py --self-check` must pass: a planted CRITICAL fails, and `hefesto/` has no CRITICAL findings (the PostHog public key at `hefesto/telemetry/client.py:28` is reported as LOW, known public client key). There is no line-level suppression; do not drop `HARDCODED_SECRET` globally. Changed files matching `exclude` in `.hefesto.yaml` are not gated; the script applies that list itself with the engine's `path_is_excluded` (the CLI does not filter explicit paths). Patterns are whole path components, not globs. Without the file it falls back to `tests/fixtures/` and `.github/action-smoke/` (planted findings) and logs that. With those exclusions, one tracked file fails this gate when touched: `scripts/validate_aggregates_jsonl.py:48` (CRITICAL `VERY_HIGH_COMPLEXITY`, cyclomatic complexity 22) until that function is split.
- [ ] Commit with Conventional Commits format, then push the branch. Commits made with the maintainer's tooling use the maintainer's GitHub noreply address as author and carry only the trailer `Co-authored-by: HefestoAI <noreply@narapallc.com>`; no other tool or automation co-author trailers (CI checks the PR's commits with `python scripts/guard_public_repo.py --check-commits <base>..<head>`).
- [ ] Never run a destructive or irreversible operation without Arturo's explicit OK first, every time: moving or deleting tags; deleting or archiving repositories, branches, releases or tags; changing repository visibility. Do not request broader token scopes (e.g. `delete_repo`) to get around a refusal; stop and ask. For tags, the single exception is the tag `v4`, the floating alias of the 4.x line used as `artvepa80/Agents-Hefesto@v4`, which `release.yml` force-moves to each new v4.x.y release. No other tag moves: not exact version tags (`v4.15.1`, ...), and no other alias exists or may be created without explicit approval.
- [ ] PR head branches are deleted by the repository's auto-delete setting when a PR is merged; Arturo's merge OK covers that. Never delete a branch by hand without explicit OK.
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
- Publicación: push a `vX.Y.Z` tag; `release.yml` builds and publishes to PyPI with Trusted Publishing (OIDC) after the required review on the `pypi` environment. No `twine upload`, no API tokens.

### Estructura del Proyecto
- **Core**: `/hefesto/core/` (engine, scanner)
- **Analyzers**: `/hefesto/analyzers/` (complexity, duplicates, semantic)
- **Security**: `/hefesto/security/` (vulnerability scanning, masking)
- **LLM**: `/hefesto/llm/` (AI provider abstraction, Vertex/Claude/OpenAI)
- **API**: `hefesto/server.py` (REST API implementation)
- **CLI**: `/hefesto/cli/` (command-line interface)
- **OMEGA**: `/hefesto/omega/` (IRIS agent, correlation engine)
- **Licensing**: `/hefesto/licensing/` (3-tier validation)
- **Tests**: `/tests/` (unit, integration, empirical)

### URLs de Producción
- PyPI: https://pypi.org/project/hefesto-ai/
- Pricing / checkout: https://hefestoai.narapallc.com/#pricing (PRO $8/mo, OMEGA $19/mo)
- Stripe PRO: https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b
- Stripe OMEGA: https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c
- GitHub: https://github.com/artvepa80/Agents-Hefesto

### Estilo de Código
- Formatter: `black` (line-length: 100)
- Import sorting: `isort`
- Type checking: `python -m mypy hefesto --ignore-missing-imports` (what CI runs)
- Linting: `flake8`
- No emojis en código (solo en docs de marketing)

---

## 🎯 **Purpose & Mission**

These rules ensure Hefesto achieves enterprise-grade quality, maintainability, safety, and developer velocity for release-truth validation for AI-generated code.

**MUST** rules are enforced by CI/testing; **SHOULD** rules are strongly recommended.

**Mission**: Build the most trusted release truth engine for AI-generated code. We dogfood the gate against our own code on every push to main; gate-internals refactor history is documented in the private repo.

**CI scans of this repo:** `.github/workflows/hefesto.yml` (job `hefesto-scan`) scans the whole repo on push and PR to `main` with the Action `@v4` (`fail_on: CRITICAL`) and uploads SARIF to code scanning (category `hefesto`). It is non-blocking (`continue-on-error: true`) until the two known CRITICAL findings are fixed; the blocking gate on changed files is `dogfood.yml`. Excludes live only in the root `.hefesto.yaml` (`tests/fixtures/`, `.github/action-smoke/`). `exclude` entries are whole path segments, not globs (`tests/fixtures/**` matches nothing), and paths passed explicitly are not filtered.

**Current Status (v4.20.3)**:
- 3-tier licensing (FREE/PRO/OMEGA)
- 2 core REST endpoints (/health, /analyze) in hefesto/server.py. IRIS ingest sub-router (/v1/ingest/*) mounted conditionally when OMEGA tier is installed
- IRIS Agent production monitoring
- 507 tests passing (CI green)
- 22 language/format analyzers
- Self-validated (dogfooding successful)
- GitHub Release automation (hardened workflow)
- Anonymous PostHog usage events, on by default, with opt-out (`hefesto telemetry disable`, `HEFESTO_TELEMETRY=0`, `DO_NOT_TRACK=1`); `hefesto init`; PyPI newer-version notice
- CLI PRO/OMEGA notices (one stderr line; `HEFESTO_NO_UPSELL=1` hides them). `hefesto info` prints only the plans line

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
- **G-3 (MUST)** `python -m mypy hefesto --ignore-missing-imports` passes (the blocking mypy step of CI `lint-and-test`; `--strict` is not enforced)
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
- **GH-8 (MUST)** No same-day merge for runtime changes. A PR that changes runtime behaviour is not merged on the calendar day (America/Lima) it was opened. Runtime paths in this repo:
  - code under `hefesto/`;
  - `action.yml` and `scripts/action_entrypoint.sh` (the GitHub Action runs that script);
  - `Dockerfile.action` (it builds the Action image that `@v4` users can run);
  - the guards and verifiers that decide pass or fail: `scripts/guard_*.py` and `scripts/verify_*.py`;
  - dependency pins in `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, or any lockfile outside `tests/fixtures/`;
  - `.github/workflows/`.

  Exempt (may merge the day they are opened):
  - docs-only PRs;
  - test-only PRs (changes only under `tests/`);
  - CI-only scripts under `scripts/` that are not guards or verifiers (benchmarks, corpus and recall tools, `scripts/git-hooks/`, `run_checks.sh`, `prepush_gate.sh`);
  - version-bump-only PRs, only when the diff is version strings plus `CHANGELOG.md`. Anything else in the diff makes it a runtime PR.

  A PR that touches both an exempt path and a runtime path is a runtime PR. The only exception is Arturo's explicit OK for that PR, recorded in the PR body as:
  `Same-day merge exception: approved by Arturo on YYYY-MM-DD. Reason: <one line>.`
  A same-day merge of a runtime PR without that line is a violation, not an exception. The rule is checkable from GitHub data alone: the PR's `created_at` and `merged_at` converted to America/Lima, its changed files, and the exception line in its body.

### Ruleset incident procedure
If infrastructure (not the change under review) breaks a required check of the `main` ruleset (15985908) so that a fix cannot merge:
1. Get Arturo's explicit OK before touching the ruleset.
2. Set the ruleset enforcement to disabled.
3. Merge the fix PR (squash).
4. Re-enable the ruleset right away and confirm it is active with the same required checks.
5. Log it in the internal work log (kept outside this repository): time (Lima), reason, PR, who approved, and when enforcement was restored.

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

### 🔍 Dogfooding (Honest Account)

We run HefestoAI's strict gate against HefestoAI's own code on every push to main. As of 2026-04-29, the gate is GREEN — but it took us 6 weeks of refactor to get there.

When we initially activated the gate in strict mode, it flagged 12 complexity findings in our own gate-internals code. We considered three responses: silence the findings (rejected — that's exactly the drift we critique), accept the override permanently (rejected — same reason), or refactor at root cause (chosen — took 1 PR, 4 commits, 2 days, plus a declared-vs-real drift discovery in our own positioning doc that we logged for fix).

The full audit and refactor history are tracked internally in our private repo. The override mechanics and reversion criteria are documented; the gate-internals refactor reduced two CRITICAL functions from cyclomatic complexity 33 → 1 and 25 → 6 respectively, all helpers under 10.

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

### PRO Tier ($8/mo per user)
- SemanticAnalyzer (AI/ML)
- Advanced security scanning
- REST API (2 endpoints: `GET /health`, `POST /analyze`; see docs/rest-api.md)
- Duplicate detection

### OMEGA Guardian ($19/mo)
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
python -m mypy hefesto --ignore-missing-imports
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
    The workflow builds the sdist and wheel, runs `twine check`, then publishes
    with PyPI Trusted Publishing (OIDC): environment `testpypi`,
    `pypa/gh-action-pypi-publish` pinned to a release tag, repository
    `https://test.pypi.org/legacy/`. Authentication is the GitHub OIDC token
    for that environment; There is no `TEST_PYPI_API_TOKEN`.
    The GitHub environment `testpypi` must exist under repository Settings →
    Environments (the name registered on the TestPyPI pending publisher).
    Production publishes go through `release.yml` (item 2).

2.  **PyPI (Production)**
    ```bash
    # Update version in pyproject.toml FIRST
    # Push final tag (triggers release.yml)
    git tag v4.7.1
    git push origin v4.7.1
    ```
    The workflow builds the sdist and wheel, runs `twine check`, then publishes
    with PyPI Trusted Publishing (OIDC): environment `pypi`,
    `pypa/gh-action-pypi-publish` pinned to a release tag. The action's default
    repository is PyPI; attestations stay at the action default (PEP 740).
    Authentication is the GitHub OIDC token for that environment;
    there is no `PYPI_API_TOKEN`. The GitHub environment `pypi` (the name
    registered on the PyPI trusted publisher) has the maintainer as required
    reviewer, so every production publish waits for that approval.
    Release-candidate publishes go through `release-testpypi.yml` (item 1).

3.  **GitHub Release** (automatic)
    - `release.yml` creates the GitHub Release after the PyPI publish job succeeds.
    - Build artifacts (wheel + sdist) are attached to the release.
    - A failed publish fails the workflow. The GitHub Release is not created and
      the floating `v4` tag is not moved.

4.  **Tag `v4`, floating alias of the 4.x line** (automatic)
    - The last step of `release.yml` force-moves the lightweight tag `v4` to the commit of a
      new `v4.x.y` tag, only when it is the highest `v4.x.y` tag (an older patch never moves it
      back). Users write `uses: artvepa80/Agents-Hefesto@v4`.
    - `v4` is the ONLY tag that moves. Never retag or delete an exact version tag.
    - `v4` follows minors too, so `@v4` users get behaviour changes (e.g. exit codes) on the
      next release: open those release notes with the change.
    - `release.yml` does not run for `v4` itself (`!v4` filter).
    - Manual fallback if that step fails:
      `git tag -f v4 v4.X.Y^{commit} && git push -f origin refs/tags/v4`.

---

**Remember**: We're building the **most trusted release truth engine for AI-generated code** — enterprise-grade, profitable, and proven through dogfooding the gate against our own code.

---

*Copyright © 2025 Narapa LLC, Miami, Florida*
*Hefesto Enterprise Development Standards v1.0*
*Adapted from OMEGA Sports Analytics Claude Code Methodology*
