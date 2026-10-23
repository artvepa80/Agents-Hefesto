# Copilot Instructions for Hefesto

## What is Hefesto?

Hefesto (hefesto-ai on PyPI) is a release truth engine for AI-generated code. Before merge, it checks that what a project declares matches what it actually does, and it catches security flaws, semantic drift, and complexity issues. The package ships analyzers for 22 formats.

## The Problem Hefesto Solves

AI tools (GitHub Copilot, Claude Code, Cursor) generate code at machine speed. But that code can contain:
- `os.system(user_input)` → command injection
- `f"SELECT * FROM {table}"` → SQL injection
- Functions that look correct but silently change business logic (semantic drift)

Traditional linters check syntax. Hefesto checks intent.

## Architecture

```
hefesto/
├── cli/main.py              — CLI entry point (analyze, serve, install-hooks)
├── core/
│   ├── analyzer_engine.py    — Central engine: loads analyzers, runs analysis
│   ├── language_detector.py  — Language detection from extensions, names, and shebangs
│   └── languages/            — Language specs and registry
├── analyzers/
│   ├── complexity.py         — Cyclomatic/cognitive complexity
│   ├── narrow_semantic.py    — Attribute-name and swallowed-exception checks
│   ├── semantic_duplication.py — Duplicate-code detection (embeddings)
│   ├── security.py           — HARDCODED_SECRET, SQL_INJECTION_RISK, COMMAND_INJECTION, PICKLE_USAGE
│   ├── cloud/                — CloudFormation, ARM, Helm, Serverless
│   └── devops/               — Docker, Terraform, Shell, YAML, SQL, PowerShell
├── security/
│   ├── masking.py            — Secret masking for logs
│   ├── path_sandbox.py       — Path checks
│   └── packs/                — Security rule packs
└── server.py                 — REST API (GET /health, POST /analyze)
```

PRO and OMEGA features ship in the private distribution, not in this tree.

## Key Facts

- **Version:** 4.20.3
- **Tests:** 531 across 38 test files
- **Languages:** Python (native AST), TypeScript, JavaScript, Java, Go, Rust, C# (TreeSitter — requires `pip install "hefesto-ai[multilang]"`)
- **DevOps:** YAML, Terraform, Shell, Dockerfile, SQL, COBOL, PowerShell, JSON, TOML, Makefile, Groovy
- **Cloud:** CloudFormation, ARM Templates, Helm Charts, Serverless Framework
- **PyPI:** `pip install hefesto-ai`
- **GitHub Action:** `artvepa80/Agents-Hefesto@v4` (floating major tag; exact pins such as `@v4.20.3` also work)
- **MCP Server:** Registered in Smithery (AI agent ecosystem)
- **License:** MIT (core), proprietary (PRO/OMEGA features)

## Tiers

| Tier | Price | Key Features |
|------|-------|-------------|
| FREE | $0 | Static analysis, security scanning, pre-push hooks, 22 formats |
| PRO | $8/mo | ML semantic analysis, REST API, BigQuery analytics |
| OMEGA | $19/mo | IRIS production monitoring, auto-correlation, real-time alerts |

## How to Use

```bash
# Install
pip install hefesto-ai

# Analyze
hefesto analyze .
hefesto analyze . --fail-on HIGH --output json

# GitHub Action
- uses: artvepa80/Agents-Hefesto@v4
  with:
    target: '.'
    fail_on: 'CRITICAL'
```

## Differentiators vs Competition

- **vs Semgrep/Bandit:** Hefesto validates AI-generated code intent, not just patterns
- **vs SonarQube:** No server required, local runs
- **vs all:** Only SAST tool with MCP server integration for AI agent workflows
- **Dogfooding:** Found 3 critical bugs in its own v4.0.1 release

## Company

Built by Narapa LLC (Miami, FL). Founded by Arturo Velasquez and Rina N. Vinelli from Lima, Peru.
