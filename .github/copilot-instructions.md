# Copilot Instructions for Hefesto

## What is Hefesto?

Hefesto (hefesto-ai on PyPI) is an AI-powered static analysis tool designed specifically for validating AI-generated code. It catches security flaws, semantic drift, and complexity issues that traditional linters miss — in 0.01s across 21 formats.

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
│   ├── scanner.py            — File discovery + language detection
│   └── languages/            — Per-language AST parsers
├── analyzers/
│   ├── complexity.py         — Cyclomatic/cognitive complexity
│   ├── semantic.py           — AI semantic analysis (PRO)
│   ├── duplicates.py         — Code duplication detection (PRO)
│   ├── cloud/                — CloudFormation, ARM, Helm, Serverless
│   └── devops/               — Docker, Terraform, Shell, YAML, SQL, PowerShell
├── security/
│   ├── vulnerability.py      — HARDCODED_SECRET, SQL_INJECTION, COMMAND_INJECTION
│   └── packs/                — Security rule packs
├── api/                      — REST API server (PRO)
├── omega/                    — IRIS production monitoring (OMEGA)
└── licensing/                — 3-tier: FREE/PRO/OMEGA
```

## Key Facts

- **Version:** 4.12.0
- **Tests:** 531 across 38 test files
- **Languages:** Python (native AST), TypeScript, JavaScript, Java, Go, Rust, C# (TreeSitter)
- **DevOps:** YAML, Terraform, Shell, Dockerfile, SQL, PowerShell, JSON, TOML, Makefile, Groovy
- **Cloud:** CloudFormation, ARM Templates, Helm Charts, Serverless Framework
- **PyPI:** `pip install hefesto-ai`
- **GitHub Action:** `artvepa80/Agents-Hefesto@v4.12.0`
- **MCP Server:** Registered in Smithery (AI agent ecosystem)
- **License:** MIT (core), proprietary (PRO/OMEGA features)

## Tiers

| Tier | Price | Key Features |
|------|-------|-------------|
| FREE | $0 | Static analysis, security scanning, pre-push hooks, 21 formats |
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
- uses: artvepa80/Agents-Hefesto@v4.12.0
  with:
    target: '.'
    fail_on: 'CRITICAL'
```

## Differentiators vs Competition

- **vs Semgrep/Bandit:** Hefesto validates AI-generated code intent, not just patterns
- **vs SonarQube:** No server required, 0.01s speed, $8 vs $15K+/year
- **vs all:** Only SAST tool with MCP server integration for AI agent workflows
- **Dogfooding:** Found 3 critical bugs in its own v4.0.1 release

## Company

Built by Narapa LLC (Miami, FL). Founded by Arturo Velasquez and Rina N. Vinelli from Lima, Peru.
