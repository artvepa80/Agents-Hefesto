# 🚀 Getting Started with Hefesto

**Goal:** Get Hefesto analyzing your code in 5 minutes.

---

## 1. Installation (30 seconds)

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Install Hefesto

```bash
# Install from PyPI
pip install hefesto-ai

# Verify installation
hefesto --version
```

**Expected output:**
```
Hefesto version 1.0.0
```

---

## 2. Your First Analysis (1 minute)

### Analyze a Single File

Create a test file with some intentional issues:

```python
# test_example.py
import os

API_KEY = "sk-proj-abc123def456"  # Hardcoded secret

def process_data(a, b, c, d, e, f, g, h):  # Too many parameters
    result = 0
    for i in range(100):
        if i > 50:
            if i < 75:
                if i % 2 == 0:
                    if i % 3 == 0:  # Deep nesting
                        result += i * 3.14159  # Magic number
    return result
```

Run Hefesto:

```bash
hefesto analyze test_example.py
```

### Analyze a Directory

```bash
# Analyze entire project
hefesto analyze .

# Analyze specific directory
hefesto analyze src/

# Filter by severity
hefesto analyze . --severity HIGH
```

---

## 3. Understanding the Output (2 minutes)

### Terminal Output Explained

```
🔨 HEFESTO ANALYSIS PIPELINE
==================================================
License: FREE
ML Enhancement: ❌ Disabled
==================================================

📁 Found 1 Python file(s)

🔍 Step 1/3: Running static analyzers...
   Found 5 potential issue(s)

✅ Step 2/3: Validation layer (Phase 0)...
   5 issue(s) validated

⏭️  Step 3/3: ML enhancement skipped (FREE tier)
   💡 Upgrade to PRO for ML-powered analysis

📊 Summary:
   Files analyzed: 1
   Issues found: 5
   Critical: 1
   High: 2
   Medium: 1
   Low: 1
```

### Issue Breakdown

**CRITICAL Issues** (🔥)
- Must be fixed immediately
- Will block pre-push hook
- Examples: Hardcoded secrets, SQL injection

**HIGH Issues** (⚠️)
- Should be fixed soon
- Will block pre-push hook
- Examples: High complexity (>20), eval() usage

**MEDIUM Issues** (💡)
- Should be addressed
- Won't block pre-push
- Examples: Long functions, too many parameters

**LOW Issues** (ℹ️)
- Nice to fix
- Won't block pre-push
- Examples: Missing docstrings, TODOs

### Detailed Issue Example

```
🔥 CRITICAL Issues (1):

  📄 test_example.py:4
  ├─ Issue: Hardcoded API key detected
  ├─ Severity: CRITICAL
  ├─ Type: Security
  └─ Suggestion: Move to environment variable:
     API_KEY = os.getenv('API_KEY')

     Never commit secrets to version control.
```

### Output Formats

**JSON** (for CI/CD integration):
```bash
hefesto analyze . --output json > report.json
```

**HTML** (interactive report):
```bash
hefesto analyze . --output html --save-html report.html
```

Then open `report.html` in your browser for:
- Executive summary with charts
- Filterable issue list
- Syntax-highlighted code
- Fix suggestions

---

## 4. Installing Pre-Push Hook (1 minute)

### What Does It Do?

The pre-push hook automatically validates your code **before** it reaches the remote repository.

**Every `git push` will run:**
1. ✅ Black formatting check
2. ✅ isort import sorting
3. ✅ flake8 linting
4. ✅ pytest unit tests
5. ✅ **Hefesto analysis** (blocks on CRITICAL/HIGH issues)

### Install the Hook

```bash
# One-time setup
hefesto install-hook

# Verify installation
ls -la .git/hooks/pre-push
```

### Testing the Hook

**Test 1: Push with Critical Issue**

```python
# bad_code.py
API_KEY = "sk-proj-secret123"  # CRITICAL issue
```

```bash
git add bad_code.py
git commit -m "Add bad code"
git push
```

**Expected result:** Push is **blocked** ❌

```
🔨 HEFESTO Pre-Push Validation
================================

3️⃣  Hefesto code analysis...
   Analyzing changed Python files with Hefesto...

🔥 CRITICAL Issues (1):
  📄 bad_code.py:1
  ├─ Issue: Hardcoded API key detected

❌ Hefesto analysis found CRITICAL issues!

Options:
  1. Fix the issues manually
  2. Run: hefesto analyze . --output html --save-html report.html
  3. Skip this check: git push --no-verify (not recommended)
```

**Test 2: Push with Clean Code**

```python
# good_code.py
import os
API_KEY = os.getenv("API_KEY")  # ✅ Good practice
```

```bash
git add good_code.py
git commit -m "Add good code"
git push
```

**Expected result:** Push succeeds ✅

```
✅ Hefesto code quality checks passed
================================
✅ All validations passed!
🚀 Pushing to remote...
```

### Bypassing the Hook (Emergency Only)

```bash
# Skip validation (use sparingly!)
git push --no-verify
```

⚠️ **Warning:** Only use `--no-verify` in emergencies. Your code quality will thank you for fixing issues before pushing.

---

## 5. Next Steps (30 seconds)

### 🎯 Recommended Actions

1. **Run First Analysis**
   ```bash
   hefesto analyze . --severity MEDIUM
   ```

2. **Fix Critical Issues**
   - Review CRITICAL and HIGH issues first
   - Use suggestions provided by Hefesto

3. **Install Pre-Push Hook**
   ```bash
   hefesto install-hook
   ```

4. **Configure Exclusions** (optional)
   ```bash
   # Exclude directories from analysis
   hefesto analyze . --exclude "tests/,docs/,build/"
   ```

5. **Explore PRO Features** (optional)
   - Try 14-day free trial: [https://buy.stripe.com/hefesto-pro-trial](https://buy.stripe.com/hefesto-pro-trial)
   - Get ML-powered semantic analysis
   - Duplicate code detection
   - BigQuery analytics

### 📚 Further Reading

- **[Analysis Rules](ANALYSIS_RULES.md)** - All 22+ checks explained with examples
- **[Integration Guide](INTEGRATION.md)** - Phase 0+1 architecture deep dive
- **[API Reference](API_REFERENCE.md)** - Complete SDK documentation
- **[CLI Reference](CLI_REFERENCE.md)** - All commands and options

### 💬 Get Help

- **Community:** [GitHub Discussions](https://github.com/artvepa80/Agents-Hefesto/discussions)
- **Issues:** [GitHub Issues](https://github.com/artvepa80/Agents-Hefesto/issues)
- **Email:** contact@narapallc.com

---

## 🎉 You're All Set!

Hefesto is now protecting your codebase from bad code. Every analysis helps you:

- ✅ Catch bugs before production
- ✅ Maintain consistent code quality
- ✅ Reduce technical debt
- ✅ Improve code review efficiency
- ✅ Learn best practices

**Start analyzing:** `hefesto analyze .`

---

<div align="center">

**Questions?** Check out the [FAQ](FAQ.md) or [open an issue](https://github.com/artvepa80/Agents-Hefesto/issues).

</div>
