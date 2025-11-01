# Hefesto – Claude Code Development Guidelines
## Adapted from OMEGA Sports Analytics Standards
## Enterprise Code Quality Development Standards

---

## Instrucciones para Claude Code

### Entorno de Desarrollo
- Usar entorno virtual apropiado (venv, virtualenv, etc.)
- Instalar dependencias: `pip install -e ".[dev]"`
- Mantener `requirements.txt` actualizado con `pip freeze > requirements.txt`

### Pre-Commit & Pre-Push Quality Gates (OBLIGATORIO)
**ANTES DE TODO COMMIT Y PUSH:**
1. **Ejecutar Omega Guardian**: `omega-guardian run`
2. **Ejecutar Agente Hefesto**: `hefesto analyze --project .`
3. **Bloquear si hay hallazgos críticos** - NO omitir estos pasos

Los git hooks instalados en `.git/hooks/pre-commit` y `.git/hooks/pre-push` **enforcement** automático de estas validaciones.

### Estructura del Proyecto
- Código fuente: `/hefesto/`
- Tests: `/tests/`
- Documentación: `/docs/`
- Configuración: `setup.py`, `requirements.txt`, `pyproject.toml`

### Estilo de Código
- Formato: Black (`black hefesto/ tests/`)
- Imports: isort (`isort hefesto/ tests/`)
- Type checking: mypy (`mypy hefesto/ --ignore-missing-imports`)
- Linting: flake8 (`flake8 hefesto/ tests/`)

---

## 🎯 **Purpose & Mission**

These rules ensure Hefesto achieves enterprise-grade quality, maintainability, safety, and developer velocity for AI-powered code analysis systems.

**MUST** rules are enforced by CI/testing; **SHOULD** rules are strongly recommended.

**Mission**: Transform code quality validation with AI-powered analysis that catches critical bugs before production.

**Current Status (v4.2.1)**: Sistema completo de análisis con ML, BigQuery integration, OMEGA Guardian monitoring, y tier-based licensing.

---

## 1️⃣ **BEFORE CODING - Requirements Analysis**

### 🔍 **Discovery & Validation**
- **BP-1 (MUST)** Ask clarifying questions about feature requirements
- **BP-2 (SHOULD)** Draft and confirm approach for complex features
- **BP-3 (SHOULD)** If ≥ 2 approaches exist, list clear pros/cons
- **BP-4 (MUST)** Validate business value and user impact
- **BP-5 (MUST)** Run Omega Guardian and Hefesto before ANY code changes

### 🔧 **Code Analysis Validation**
- **BP-6 (MUST)** Verify analysis accuracy requirements
- **BP-7 (MUST)** Confirm detection performance targets
- **BP-8 (MUST)** Validate security scanning effectiveness
- **BP-9 (MUST)** Test with real-world code samples

---

## 2️⃣ **WHILE CODING - Enterprise Standards**

### 🧪 **Test-Driven Development**
- **C-1 (MUST)** Follow TDD: scaffold stub → write failing test → implement → validate
- **C-2 (MUST)** Every analyzer function needs accuracy tests
- **C-3 (MUST)** All code processing must handle edge cases

### 🏗️ **Architecture & Naming**
- **C-4 (MUST)** Use clear domain vocabulary (analyzer, validator, detector, rule, finding)
- **C-5 (SHOULD NOT)** Introduce classes when simple functions suffice
- **C-6 (SHOULD)** Prefer composable, testable functions
- **C-7 (MUST)** Use typed data structures:
  ```python
  from dataclasses import dataclass
  from typing import NewType

  FindingId = NewType('FindingId', str)
  RuleId = NewType('RuleId', str)

  @dataclass
  class Finding:
      id: FindingId
      severity: str
      message: str
      file_path: str
      line_number: int
  ```

### 📊 **Performance & Memory**
- **C-8 (MUST)** All ML operations must include memory cleanup
- **C-9 (MUST)** Cache expensive computations appropriately
- **C-10 (MUST)** Log analysis metrics for every execution
- **C-11 (SHOULD NOT)** Add comments except for critical caveats

### 🔒 **Memory & Resource Management**
- **C-12 (MUST)** Monitor memory usage during ML inference
- **C-13 (MUST)** Use proven infrastructure components only
- **C-14 (MUST)** Implement proper cleanup in analyzers

---

## 3️⃣ **TESTING - Validation Standards**

### 🏆 **The 4-Level Testing Pyramid (MANDATORY)**

- **T-1 (MUST)** **Unit Test**: Individual analyzer functions
  ```python
  def test_hardcoded_secret_detection():
      code = 'password = "admin123"'
      findings = detect_hardcoded_secrets(code)
      assert len(findings) == 1
      assert findings[0].severity == 'CRITICAL'
  ```

- **T-2 (MUST)** **Smoke Test**: Basic system functionality
  ```python
  def test_analyzer_initialization():
      analyzer = HefestoAnalyzer()
      assert analyzer.initialize() == True
      assert analyzer.rules is not None
  ```

- **T-3 (MUST)** **Canary Test**: Real code analysis (small dataset)
  ```python
  def test_real_code_analysis():
      code_sample = load_test_file('sample.py')
      findings = analyze_code(code_sample)
      assert len(findings) > 0
      assert all(f.severity in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] for f in findings)
  ```

- **T-4 (MUST)** **Empirical Test**: Production-like validation
  ```python
  def test_detection_accuracy_benchmark():
      test_suite = load_vulnerable_code_samples(100)
      results = [analyze_code(sample) for sample in test_suite]
      accuracy = calculate_detection_rate(results, test_suite)
      assert accuracy > 0.90  # 90%+ detection rate
  ```

### 📊 **Test Requirements**
- **T-5 (MUST)** Separate unit tests from integration tests
- **T-6 (SHOULD)** Prefer integration tests with real code over heavy mocking
- **T-7 (MUST)** Test edge cases:
  - Empty files
  - Large files (>10K LOC)
  - Binary files
  - Encoding issues
  - Syntax errors
- **T-8 (SHOULD)** Test entire analysis pipeline when possible

### 🎯 **Test Quality**
- **T-9 (MUST)** Use real code scenarios, not synthetic examples
- **T-10 (MUST)** Test descriptions must specify exact outcome being verified
- **T-11 (SHOULD)** Use property-based testing when practical
- **T-12 (MUST)** Test boundary conditions

---

## 4️⃣ **DATA MANAGEMENT**

### 🔧 **Database Standards**
- **D-1 (MUST)** All database connections must handle errors gracefully
- **D-2 (MUST)** Use type-safe data models with validation
- **D-3 (MUST)** Implement data versioning for model retraining
- **D-4 (SHOULD)** Cache expensive calculations

### 📦 **Models & Schemas**
- **D-5 (MUST)** Define clear entity relationships
- **D-6 (MUST)** Handle data inconsistencies gracefully
- **D-7 (MUST)** Validate data integrity before ML processing

---

## 5️⃣ **CODE ORGANIZATION**

### 📁 **Project Structure**
- **O-1 (MUST)** Place utilities in `utils/` only if used by ≥ 2 modules
- **O-2 (MUST)** Organize by domain: `analyzers/`, `validators/`, `detectors/`
- **O-3 (MUST)** Separate ML models from analysis logic
- **O-4 (MUST)** Keep business logic separate from infrastructure
- **O-5 (MUST)** Share common analysis logic across modules when applicable

---

## 6️⃣ **QUALITY GATES - Enterprise Standards**

### 🔧 **Automated Validation (MANDATORY)**
- **G-1 (MUST)** `pytest --cov=90` coverage minimum
- **G-2 (MUST)** `black --check` and `isort --check` formatting passes
- **G-3 (MUST)** `mypy` type checking passes with no errors
- **G-4 (MUST)** `omega-guardian run` passes before commit
- **G-5 (MUST)** `hefesto analyze .` passes before commit
- **G-6 (MUST)** Memory usage tests pass (< 2GB peak)

### 📊 **Performance Gates**
- **G-7 (MUST)** Analysis latency < 5s for files < 1000 LOC
- **G-8 (MUST)** All operations must have proper error handling
- **G-9 (MUST)** All analyzers must log execution metrics

---

## 7️⃣ **GIT & DEPLOYMENT - Workflow**

### 📝 **Commit Standards (Conventional Commits)**
- **GH-1 (MUST)** Use Conventional Commits format:
  ```
  feat(analyzer): add SQL injection detection
  fix(ml): handle memory cleanup in semantic analyzer
  test(validation): add empirical accuracy tests
  docs(readme): update installation instructions
  ```
- **GH-2 (SHOULD NOT)** Refer to Claude/AI in commit messages
- **GH-3 (MUST)** Include domain context in commit scope

### 🚀 **Deployment Requirements**
- **GH-4 (MUST)** All releases require full test suite passing
- **GH-5 (MUST)** Production deployments need rollback plan
- **GH-6 (MUST)** Include performance metrics in deployment validation

---

## 🛠️ **HEFESTO DEVELOPMENT SHORTCUTS**

### **QNEW**
```
Understand all Hefesto best practices.
Your code MUST follow enterprise standards.
Every feature must improve code quality analysis.
Always run Omega Guardian + Hefesto before commit/push.
```

### **QPLAN**
```
Analyze existing Hefesto codebase and ensure your plan:
- Leverages proven infrastructure components
- Follows domain patterns consistently
- Minimizes changes to battle-tested systems
- Includes performance benchmarking
```

### **QCODE**
```
Implement your plan with mandatory testing:
1. Run all 4 test levels (Unit → Smoke → Canary → Empirical)
2. Validate detection accuracy benchmarks
3. Check memory usage (must stay < 2GB peak)
4. Run formatting and type checking (black, isort, mypy)
5. Run Omega Guardian and Hefesto analysis
```

### **QCHECK**
```
You are a SENIOR SOFTWARE ENGINEER.
Review all major changes using Hefesto checklists:
1. Best practices compliance
2. Enterprise testing standards met
3. Performance benchmarks achieved
4. Business value contribution validated
5. Omega Guardian + Hefesto validation passed
```

### **QVALIDATE** (Hefesto-Specific)
```
Validate this code quality feature:
1. Does it improve detection accuracy?
2. Does it handle real-world code correctly?
3. Is it enterprise-ready for production use?
4. Are edge cases handled properly?
5. Did Omega Guardian and Hefesto pass?
```

### **QBENCH** (Performance Validation)
```
Run benchmarks:
1. Detection accuracy vs industry standards (>90%)
2. Analysis latency (<5s per file)
3. Memory usage (<2GB peak)
4. Processing speed (files/second)
5. Concurrent analysis load testing
```

### **QGIT**
```
Commit changes:
- Use conventional commits format
- Include performance metrics in commit message
- Reference improvements/fixes
- Never mention AI tools in commit messages
- Ensure Omega Guardian + Hefesto passed
```

---

## 🏆 **HEFESTO SUCCESS FRAMEWORK**

### 📈 **Development Process**
1. **Start**: `qnew` → understand enterprise standards
2. **Plan**: `qplan` → validate requirements and approach
3. **Code**: `qcode` → implement with 4-level testing
4. **Validate**: `qvalidate` + `qbench` → confirm targets
5. **Review**: `qcheck` → enterprise quality validation
6. **Deploy**: `qgit` → professional deployment

### 🎯 **Success Metrics**
- **Detection Accuracy**: >90% for all vulnerability types
- **System Performance**: <5s per file, <2GB memory
- **Code Quality**: >90% test coverage, zero critical bugs
- **User Impact**: Clear value for developers

### 🚀 **Enterprise Readiness**
Every Hefesto feature must be:
- ✅ **Production-Grade**: Teams can rely on it
- ✅ **Scalable**: Handles large codebases
- ✅ **Maintainable**: Future developers can extend it
- ✅ **Validated**: Omega Guardian + Hefesto approved

---

## ⚠️ **CRITICAL SUCCESS FACTORS**

### 🔍 **Development Oversight**
- **Never accept first draft code** - always iterate
- **Actively monitor edits** - stop if going wrong direction
- **Question every decision** - ensure it adds value
- **Test extensively** - use real code samples
- **Validate assumptions** - don't trust synthetic examples

### 🛡️ **Quality Enforcement (MANDATORY)**

**BEFORE EVERY COMMIT:**
```bash
# 1. Run Omega Guardian
omega-guardian run || exit 1

# 2. Run Hefesto Analysis
hefesto analyze --project . --severity HIGH || exit 1

# 3. Run Tests
pytest tests/ --cov=hefesto --cov-report=term-missing || exit 1

# 4. Run Formatters
black hefesto/ tests/ || exit 1
isort hefesto/ tests/ || exit 1

# 5. Type Checking
mypy hefesto/ --ignore-missing-imports || exit 1
```

**Git hooks enforce these automatically** - DO NOT bypass them.

---

## 📞 **Contact & Support**

- **Support:** support@narapallc.com
- **General inquiries:** contact@narapallc.com

---

**Remember**: We're building the **AI-Powered Code Quality Guardian** - enterprise-grade, reliable, and trusted by development teams worldwide.

---

*Copyright © 2025 Narapa LLC, Miami, Florida*
*Hefesto Enterprise Development Standards v1.0*
*Adapted from OMEGA Sports Analytics Standards*
