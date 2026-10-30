# Hefesto Quick Start Guide

Get up and running with Hefesto in 5 minutes.

## 1. Install Hefesto

```bash
pip install hefesto-ai

# For TypeScript, JavaScript, Java, Go, Rust, or C# analysis,
# also install the multilang extra:
pip install "hefesto-ai[multilang]"
```

No API key is needed. Hefesto does not bundle an LLM provider: the free
analyzers are deterministic and run locally. Optional AI enrichment is a PRO
feature where you bring the provider, a class that implements the PRO
`EnrichmentProvider` contract.

## 2. Analyze your code

```bash
# Analyze the current directory
hefesto analyze .

# Only HIGH and CRITICAL findings
hefesto analyze . --severity HIGH

# Machine-readable output
hefesto analyze . --output json
```

## 3. Use it as a gate

```bash
# Exit code 1 if any HIGH or CRITICAL finding is present
hefesto analyze . --fail-on HIGH
```

Leave out paths you do not want analyzed with `--exclude`, and keep
specific issue types from failing the gate with `--exclude-types`:

```bash
hefesto analyze . --fail-on HIGH --exclude tests/,docs/ --exclude-types LONG_FUNCTION
```

The same options can live in a `.hefesto.yaml` at the repository root:

```yaml
fail_on: HIGH
exclude:
  - tests/
  - docs/
exclude_types:
  - LONG_FUNCTION
```

## 4. Python integration

```python
from hefesto.analyzers import ComplexityAnalyzer, SecurityAnalyzer
from hefesto.core.analyzer_engine import AnalyzerEngine

engine = AnalyzerEngine(severity_threshold="MEDIUM", quiet=True)
engine.register_analyzer(ComplexityAnalyzer())
engine.register_analyzer(SecurityAnalyzer())

report = engine.analyze_path("src/")
print(report.summary.total_issues, "issues")
```

See [examples/basic_usage.py](../examples/basic_usage.py) for a runnable version.

## 5. Upgrade to Pro (Optional)

PRO adds duplicate-function detection (`DUPLICATE_CODE`) from local
`sentence-transformers` embeddings. It runs only with `hefesto-ai[pro]`
installed and `HEFESTO_TIER=professional` or `omega`.

```bash
# Purchase license
# Visit: https://hefestoai.narapallc.com/#pricing

pip install hefesto-ai[pro]
export HEFESTO_LICENSE_KEY=HFST-XXXX-XXXX-XXXX-XXXX-XXXX
```

## Common Use Cases

### Pre-Commit Hook

```bash
hefesto install-hooks
```

Or add the `hefesto-analyze` hook to `.pre-commit-config.yaml`.

### CI/CD Pipeline

```yaml
- name: Code Quality
  run: |
    pip install hefesto-ai
    hefesto analyze . --fail-on HIGH
```

## Next Steps

- Check [Examples](../examples/) for more usage

## Troubleshooting

**"No files were analyzed"**: for TypeScript, JavaScript, Java, Go, Rust or
C# install the parsers with `pip install "hefesto-ai[multilang]"`.

**Tests failing**:
```bash
# Skip tests of the optional BigQuery adapter
pytest -m "not bigquery"
```

---

**Need help?** support@narapallc.com
