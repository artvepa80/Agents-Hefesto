# HefestoAI Issue Types Reference

Source: `hefesto/core/analysis_models.py` — `AnalysisIssueType` enum.

## Severity Levels

| Level | Meaning |
|-------|---------|
| CRITICAL | Must fix before merge — security vulnerability or data loss risk |
| HIGH | Should fix — significant quality or reliability problem |
| MEDIUM | Recommended fix — maintainability or minor risk concern |
| LOW | Informational — style or best practice suggestion |

## Complexity (2)

| Type | Severity | Description |
|------|----------|-------------|
| HIGH_COMPLEXITY | HIGH | Cyclomatic complexity exceeds threshold |
| VERY_HIGH_COMPLEXITY | CRITICAL | Cyclomatic complexity far exceeds threshold |

## Code Smells (8)

| Type | Severity | Description |
|------|----------|-------------|
| LONG_FUNCTION | MEDIUM | Function body exceeds line count threshold |
| LONG_PARAMETER_LIST | MEDIUM | Too many parameters — consider a config object |
| DEEP_NESTING | MEDIUM | Excessive indentation depth (3+ levels) |
| DUPLICATE_CODE | MEDIUM | Near-identical code blocks detected |
| DEAD_CODE | HIGH | Unreachable or unused function/variable |
| MAGIC_NUMBER | LOW | Unexplained numeric literal in logic |
| GOD_CLASS | HIGH | Class with too many methods or responsibilities |
| INCOMPLETE_TODO | MEDIUM | TODO/FIXME/HACK comment left in code |

## Security (6)

| Type | Severity | Description |
|------|----------|-------------|
| HARDCODED_SECRET | CRITICAL | API key, password, or token in source code |
| SQL_INJECTION_RISK | CRITICAL | String interpolation in SQL query |
| EVAL_USAGE | HIGH | Use of eval() or exec() — code injection risk |
| PICKLE_USAGE | HIGH | Pickle deserialization of untrusted data |
| ASSERT_IN_PRODUCTION | MEDIUM | Assert used for validation (stripped with -O) |
| BARE_EXCEPT | MEDIUM | Except clause without specific exception type |

## Best Practices (3)

| Type | Severity | Description |
|------|----------|-------------|
| MISSING_DOCSTRING | LOW | Public function/class lacks docstring |
| POOR_NAMING | LOW | Variable or function name is unclear |
| STYLE_VIOLATION | LOW | Code style inconsistency |

## YAML (5)

| Type | Severity | Description |
|------|----------|-------------|
| YAML_SYNTAX_ERROR | HIGH | Invalid YAML syntax |
| YAML_DUPLICATE_KEY | MEDIUM | Duplicate key in mapping |
| YAML_INDENTATION | LOW | Inconsistent indentation |
| YAML_SECRET_EXPOSURE | CRITICAL | Secret value in YAML file |
| YAML_UNSAFE_COMMAND | HIGH | Shell command in CI/CD pipeline without safety |

## Terraform/HCL (5)

| Type | Severity | Description |
|------|----------|-------------|
| TF_OPEN_SECURITY_GROUP | CRITICAL | Security group open to 0.0.0.0/0 |
| TF_HARDCODED_SECRET | CRITICAL | Secret in Terraform configuration |
| TF_MISSING_ENCRYPTION | HIGH | Resource without encryption enabled |
| TF_PUBLIC_ACCESS | HIGH | Resource publicly accessible |
| TF_OVERLY_PERMISSIVE | MEDIUM | IAM policy grants excessive permissions |

## Shell (6)

| Type | Severity | Description |
|------|----------|-------------|
| SHELL_UNQUOTED_VARIABLE | MEDIUM | Variable expansion without quotes |
| SHELL_COMMAND_INJECTION | CRITICAL | User input passed to shell command |
| SHELL_UNSAFE_TEMP | HIGH | Temp file in predictable location |
| SHELL_DEPRECATED_SYNTAX | LOW | Outdated shell syntax (`backticks`, etc.) |
| SHELL_UNSAFE_COMMAND | HIGH | Dangerous command without safeguards |
| SHELL_MISSING_SAFETY | MEDIUM | Script lacks set -euo pipefail |

## PowerShell (6)

| Type | Severity | Description |
|------|----------|-------------|
| PS_INVOKE_EXPRESSION | HIGH | Invoke-Expression with dynamic input |
| PS_REMOTE_CODE_EXECUTION | CRITICAL | Remote code execution pattern |
| PS_COMMAND_INJECTION | CRITICAL | Command injection via string interpolation |
| PS_HARDCODED_SECRET | CRITICAL | Credential in PowerShell script |
| PS_EXECUTION_POLICY_BYPASS | HIGH | Bypassing execution policy |
| PS_TLS_BYPASS | HIGH | Disabling TLS certificate validation |

## Dockerfile (11)

| Type | Severity | Description |
|------|----------|-------------|
| DOCKERFILE_INSECURE_BASE_IMAGE | HIGH | Base image from untrusted source |
| DOCKERFILE_LATEST_TAG | MEDIUM | Using :latest tag (non-reproducible) |
| DOCKERFILE_MISSING_USER | MEDIUM | No USER directive (runs as root) |
| DOCKERFILE_PRIVILEGE_ESCALATION | CRITICAL | Privilege escalation pattern |
| DOCKERFILE_SECRET_EXPOSURE | CRITICAL | Secret in Dockerfile |
| DOCKERFILE_WEAK_PERMISSIONS | HIGH | Overly permissive file permissions |
| DOCKER_LATEST_TAG | MEDIUM | Using :latest tag |
| DOCKER_ROOT_USER | MEDIUM | Running as root user |
| DOCKER_APT_CLEANUP | LOW | apt-get without cleanup in same layer |
| DOCKER_CURL_BASH | HIGH | curl \| bash anti-pattern |
| DOCKER_SECRET_IN_ENV | CRITICAL | Secret passed via ENV instruction |

## SQL (7)

| Type | Severity | Description |
|------|----------|-------------|
| SQL_SYNTAX_ERROR | HIGH | Invalid SQL syntax |
| SQL_DROP_WITHOUT_WHERE | CRITICAL | DROP without safety clause |
| SQL_SELECT_STAR | LOW | SELECT * in production query |
| SQL_MISSING_INDEX_HINT | LOW | Query on large table without index hint |
| SQL_OVERLY_PERMISSIVE_GRANT | HIGH | GRANT ALL or excessive permissions |
| SQL_DELETE_WITHOUT_WHERE | CRITICAL | DELETE without WHERE clause |
| SQL_UPDATE_WITHOUT_WHERE | CRITICAL | UPDATE without WHERE clause |

## Reliability Drift — EPIC 4 (5)

See [reliability_drift.md](reliability_drift.md) for patterns and fixes.

| Type | Severity | Description |
|------|----------|-------------|
| RELIABILITY_UNBOUNDED_GLOBAL | MEDIUM | Module-level mutable grown in functions |
| RELIABILITY_UNBOUNDED_CACHE | MEDIUM | @lru_cache(maxsize=None) — unbounded |
| RELIABILITY_SESSION_LIFECYCLE | MEDIUM | Session/connection without cleanup |
| RELIABILITY_LOGGING_HANDLER_DUP | MEDIUM | addHandler() inside function body |
| RELIABILITY_THREAD_IN_REQUEST | MEDIUM | threading.Thread() in request handler |

## Cross-Language (3)

| Type | Severity | Description |
|------|----------|-------------|
| INSECURE_COMMUNICATION | HIGH | HTTP instead of HTTPS, weak TLS, etc. |
| SECURITY_MISCONFIGURATION | MEDIUM | Insecure default configuration |
| EXTERNAL_FINDING | varies | Finding from external provider integration |
