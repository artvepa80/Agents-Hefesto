# HefestoAI — Claude Code Skill Reference

HefestoAI is a pre-commit code quality guardian that detects semantic drift,
security vulnerabilities, and reliability anti-patterns in AI-generated code.

Package: `hefesto-ai` (PyPI) | Version: 4.9.3 | License: MIT
Requires: Python >= 3.10

## When to Load These Docs

- User asks about code quality analysis or pre-commit hooks
- User wants to detect issues in AI-generated code
- User needs to set up CI/CD quality gates
- User mentions semantic drift, code smells, or security scanning
- User wants to integrate HefestoAI with Claude Code or Cursor

## Document Index

| File | Contents |
|------|----------|
| [issue_types.md](issue_types.md) | All 73 issue types with severities and descriptions |
| [commands.md](commands.md) | CLI commands, flags, workflows, and exit codes |
| [semantic_drift.md](semantic_drift.md) | What semantic drift is and how HefestoAI detects it |
| [reliability_drift.md](reliability_drift.md) | 5 RELIABILITY_* rules for long-running services |
| [integration.md](integration.md) | Pre-commit hooks, CI/CD, MCP server setup |

## Quick Start

```bash
pip install hefesto-ai
hefesto analyze .
hefesto install-hooks
```

## Architecture Overview

HefestoAI runs a two-phase pipeline:

**Phase 0 — Static Analysis** (always enabled):
5 analyzers run deterministically on every file:
1. ComplexityAnalyzer — cyclomatic and cognitive complexity
2. CodeSmellAnalyzer — long functions, deep nesting, dead code, etc.
3. SecurityAnalyzer — hardcoded secrets, injection risks, eval/pickle
4. BestPracticesAnalyzer — naming, docstrings, style
5. ResourceSafetyAnalyzer — reliability drift (EPIC 4)

DevOps analyzers run on non-Python files:
YAML, Shell, Dockerfile, Terraform, SQL — each with dedicated analyzer.

**Phase 1 — ML Semantic Analysis** (PRO/OMEGA only):
Detects semantic duplication across functions using embeddings.
Enabled when HEFESTO_TIER=professional or HEFESTO_TIER=omega.

## Supported Languages

Python, JavaScript, TypeScript, Java, Go, Rust, C, C++,
YAML, Shell/Bash, Dockerfile, Terraform/HCL, SQL, PowerShell.

## MCP Server

Registry: `io.github.artvepa80/hefestoai`
Protocol: JSON-RPC 2.0 (streamable-http)
Endpoint: `https://hefestoai.narapallc.com/api/mcp-protocol`

```bash
npx @smithery/cli@latest mcp add artvepa80/hefestoai
```
