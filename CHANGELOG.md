# Changelog

All notable changes to Hefesto will be documented in this file.

## [4.5.0] - 2025-12-29 — Ola 2 DevOps Analyzers

### Added
- **PowerShellAnalyzer (P6)**: PS001–PS006 security rules (+30 tests)
  - Invoke-Expression, download+execute, secrets, execution policy bypass, TLS bypass
- **JsonAnalyzer (P7)**: J001, J002, J004, J005 security rules (+20 tests)
  - Hardcoded secrets, insecure URLs, Docker credentials, dangerous flags
- **TomlAnalyzer (P7.2)**: T001–T003 security rules (+18 tests)
  - Secrets, dangerous flags, insecure URLs
  - Compatible with tomllib (3.11+) / tomli (3.10) + regex fallback
- **MakefileAnalyzer (P8)**: MF001–MF005 security rules (+20 tests)
  - Shell injection, curl|sh, sudo usage, TLS bypass, dangerous deletes
- **GroovyJenkinsAnalyzer (P9)**: GJ001–GJ005 security rules (+21 tests)
  - sh/bat interpolation, download+execute, credential exposure, TLS bypass, evaluate patterns

### Infrastructure
- New cross-language issue types:
  - `INSECURE_COMMUNICATION`
  - `SECURITY_MISCONFIGURATION`
- PowerShell-specific issue types: `PS_INVOKE_EXPRESSION`, `PS_REMOTE_CODE_EXECUTION`, etc.
- GitHub Actions CI workflow with Python 3.10/3.11/3.12 matrix
- Improved pre-push hook with timeout support and skip option

### Stats
- **23 new security rules** across 5 analyzers
- **109 new tests** for Ola 2 analyzers
- Total DevOps analyzers: 10 (Ola 1 + Ola 2)

---

## [4.4.0] - 2025-12 — Ola 1 DevOps Analyzers

### Added
- YamlAnalyzer: YAML security and best practices
- TerraformAnalyzer: HCL/Terraform security
- ShellAnalyzer: Bash/Shell script security
- DockerfileAnalyzer: Dockerfile best practices
- SqlAnalyzer: SQL injection and dangerous operations (P3/P4 hardening)
