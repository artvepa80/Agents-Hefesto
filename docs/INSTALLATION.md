# Hefesto Installation Guide

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

No AI provider or API key is needed. Hefesto does not bundle an LLM
provider; see [AI providers](#ai-providers-none-bundled) below.

## Installation Methods

### Method 1: PyPI (Recommended)

```bash
# Free version (Phase 0)
pip install hefesto-ai

# Pro version (Phase 1)
pip install hefesto-ai[pro]
```

### Multi-language Support (TS / JS / Java / Go / Rust / C#)

Analysis of TypeScript, JavaScript, Java, Go, Rust, and C# requires
the `[multilang]` extra. Without it, files in these languages are
skipped at parse time and Hefesto emits a `parser_unavailable` warning
to stderr at the end of the run (also exposed as
`report.meta.parser_failures` in JSON output).

```bash
pip install "hefesto-ai[multilang]"
```

This installs `tree-sitter-language-pack` (165+ pre-built grammars).
Python (`.py`) analysis works without this extra.

### Method 2: From Source

```bash
# Clone repository
git clone https://github.com/artvepa80/Agents-Hefesto.git
cd Agents-Hefesto

# Install in development mode
pip install -e .

# Or with Pro features
pip install -e ".[pro]"
```

### Method 3: Docker

```bash
# Pull image
docker pull ghcr.io/artvepa80/hefesto:latest

# Run server
docker run -p 8080:8080 ghcr.io/artvepa80/hefesto:latest
```

## Configuration

### 1. AI providers (none bundled)

Hefesto does not bundle an LLM provider and needs no AI API key. The free
analyzers are deterministic and run locally.

Optional AI enrichment of findings is a PRO feature, and you bring the
provider: it is a class you write (or install) that implements the PRO
`EnrichmentProvider` contract. Hefesto ships no provider and sends nothing to
any AI service unless you configure one.

The PRO duplicate-function check (`DUPLICATE_CODE`) is not an external
provider: it uses local `sentence-transformers` embeddings and runs only
with `hefesto-ai[pro]` installed and `HEFESTO_TIER=professional` or `omega`.

### 2. Telemetry storage (OMEGA, optional)

IRIS telemetry storage is provider-agnostic: you choose where the data lives. Today's adapters are in-memory, file (JSONL) and BigQuery (optional); more are planned.

### 3. Pro License (Phase 1)

```bash
# After purchasing Pro license
export HEFESTO_LICENSE_KEY=HFST-XXXX-XXXX-XXXX-XXXX-XXXX
```

## Verify Installation

```bash
# Check version
hefesto --version

# Check installation
hefesto check
```

## Quick Test

```bash
# Analyze the current directory
hefesto analyze . --severity MEDIUM
```

## Troubleshooting

### ImportError: No module named 'hefesto'

**Solution**:
```bash
pip install --upgrade hefesto-ai
```

### Pro features not working

**Solution**:
```bash
# Install Pro dependencies
pip install hefesto-ai[pro]

# Set license key
export HEFESTO_LICENSE_KEY=HFST-XXXX-XXXX-XXXX-XXXX-XXXX

# Verify: both lines must say installed / set
hefesto status
# Pro package:  installed
# License key:  set (HFST-XXXX-...)

# Duplicate-function detection also needs the tier variable
export HEFESTO_TIER=professional   # or omega
```

### BigQuery permission errors (optional BigQuery adapter only)

Only relevant if you chose the BigQuery adapter: give its credentials
(`GOOGLE_APPLICATION_CREDENTIALS`) read/write access to the dataset. The default
adapters (in-memory, file/JSONL) need no cloud credentials.

## Uninstallation

```bash
pip uninstall hefesto-ai
```

## Next Steps

- Read [Quick Start Guide](QUICK_START.md)
- View live API schema (OpenAPI/Swagger) at `/docs` when running `hefesto serve` — generated automatically from code
- Check [Examples](../examples/)
- Get a [PRO or OMEGA license](https://hefestoai.narapallc.com/#pricing) for advanced features

---

**Support**: support@narapallc.com

