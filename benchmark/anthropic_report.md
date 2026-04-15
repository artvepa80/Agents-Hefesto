# HefestoAI Code Quality Report — Anthropic Open Source Repositories

**Date:** 2026-04-13
**Tool:** HefestoAI v4.10.0 (deterministic analysis, no AI enrichment)
**Repos audited:**
- `anthropics/anthropic-sdk-python` (850 files)
- `anthropics/claude-code` (48 files — plugins/examples only, core is TypeScript)
- `anthropics/anthropic-cookbook` (122 files)

---

## Summary

| Repo | Files | Total findings | Verified actionable |
|------|-------|---------------|-------------------|
| anthropic-sdk-python | 850 | 410 | 12 |
| claude-code | 48 | 51 | 2 |
| anthropic-cookbook | 122 | 267 | 10 |

Most findings are code complexity and style (LONG_FUNCTION, HIGH_COMPLEXITY)
which are informational. This report focuses on the **verified actionable**
findings: security, reliability, and error-handling patterns.

---

## Verified Findings — anthropic-sdk-python

### 1. Silent exception swallowing in SDK core (7 instances)

**Severity:** MEDIUM
**Pattern:** `except Exception: pass` or `except Exception: return`

**`src/anthropic/_base_client.py:910`** — `__del__` finalizer:
```python
try:
    self.close()
except Exception:
    pass
```

**`src/anthropic/_base_client.py:1548`** — async `__del__` finalizer:
```python
try:
    asyncio.get_running_loop().create_task(self.aclose())
except Exception:
    pass
```

**Assessment:** The `__del__` cases are **defensible** — finalizers should
not raise. However, `src/anthropic/_models.py:532` swallows validation
errors during union type construction, which could mask real deserialization
bugs in user payloads:

```python
# _models.py:530-533
try:
    return validate_type(type_=cast("type[object]", original_type or type_), value=value)
except Exception:
    pass
```

**`src/anthropic/_utils/_httpx.py:19,27`** — IP address validation:
```python
try:
    ipaddress.IPv4Address(hostname.split("/")[0])
except Exception:
    return False
```

**Assessment:** These catch `Exception` where `ValueError` would suffice.
Not a bug, but unnecessarily broad.

**`src/anthropic/lib/tools/_beta_builtin_memory_tool.py:389,676`** —
directory iteration in memory tool:
```python
try:
    dir_contents = sorted(dir_path.iterdir(), key=lambda x: x.name)
except Exception:
    return
```

**Assessment:** Silently returns on any directory read error (permission
denied, broken symlink, etc.). Could mask real filesystem issues during
memory tool operations. `except OSError` would be more precise.

**Recommendation:** Consider narrowing the exception types to what each
block actually expects. The `_models.py` case is the most concerning — a
silent fallback during type validation can produce incorrect model objects.

### 2. Unbounded LRU caches (2 instances)

**Severity:** MEDIUM
**Rule:** RELIABILITY_UNBOUNDED_CACHE

**`src/anthropic/_base_client.py:2198`**:
```python
@lru_cache(maxsize=None)
def platform_headers(version: str, *, platform: Platform | None) -> Dict[str, str]:
```

**`src/anthropic/lib/bedrock/_stream_decoder.py:13`**:
```python
@lru_cache(maxsize=None)
def get_response_stream_shape()
```

**Assessment:** `platform_headers` is bounded in practice (few unique
version+platform combinations). `get_response_stream_shape` returns a
single value and is effectively a `@cache` singleton. Both are **low risk**
in practice, but `maxsize=None` on a public SDK means any downstream
long-running process inherits unbounded caches. `maxsize=128` would be
equivalent in practice and bounded by design.

### 3. Session without context manager (1 instance)

**Severity:** MEDIUM
**Rule:** RELIABILITY_SESSION_LIFECYCLE

**`src/anthropic/lib/bedrock/_client.py:80`**:
```python
session = boto3.Session()
```

**Assessment:** The `Session()` is used to read `region_name` and is not
stored. No connection leak. **Low risk / informational.**

---

## Verified Findings — anthropic-cookbook

### 4. SQL injection in tool_use demo (4 instances)

**Severity:** HIGH
**Rule:** SQL_INJECTION_RISK

**`tool_use/memory_demo/sample_code/sql_query_builder.py:30,49,60,72`**

These are **intentionally vulnerable** — the file explicitly documents them
as `BUG: SQL INJECTION VULNERABILITY!` with safe alternatives. However:

- This file appears in a cookbook that developers clone and adapt
- The vulnerable patterns are copy-paste ready
- No CI gate prevents the vulnerable code from being used in production

**Recommendation:** Consider adding a `# nosec` or similar annotation, or
moving the vulnerable examples to a clearly-named
`intentionally_vulnerable/` directory. Alternatively, a pre-commit hook
using HefestoAI or similar would catch if someone adapts these patterns.

### 5. Pickle usage in evaluation code (3 instances)

**Severity:** HIGH
**Rule:** PICKLE_USAGE

**`capabilities/classification/evaluation/vectordb.py:3`**
**`capabilities/retrieval_augmented_generation/evaluation/vectordb.py:3`**
**`capabilities/text_to_sql/evaluation/vectordb.py:3`**

**Assessment:** These are evaluation/benchmarking scripts deserializing
vector DB data. Risk is low if the pickle files are self-generated, but
the pattern is unsafe if users substitute their own data files.

### 6. Dockerfile running as root (1 instance)

**Severity:** MEDIUM
**Rule:** DOCKERFILE_MISSING_USER

**`claude_agent_sdk/observability_agent/docker/Dockerfile`**

No `USER` instruction — container runs as root. The Dockerfile also
installs Docker CLI inside the container and runs
`curl ... | bash -` for Node.js setup.

**Recommendation:** Add a non-root `USER` after the install steps.

### 7. Silent exception swallowing (2 instances)

**`third_party/ElevenLabs/stream_voice_assistant_websocket.py:140`**
**`claude_agent_sdk/utils/agent_visualizer.py:59`**

---

## Verified Findings — claude-code

### 8. Silent exception swallowing in plugins (2 instances)

**Severity:** MEDIUM

Found in plugin/hook code. Low impact given the plugin context.

### 9. Shell unquoted variables (12 instances)

**Severity:** MEDIUM

Shell scripts in `scripts/` directory. Informational.

---

## False Positives Acknowledged

**9 HARDCODED_SECRET findings in `lib/bedrock/`** — These are **false
positives**. HefestoAI flagged parameter names like `aws_secret_key: str`
and references to `AWSEventStreamDecoder` as potential AWS keys. The
regex pattern matches `AWS` followed by alphanumeric characters, which
triggers on type annotations and class names. We are tracking this FP
class for improvement.

---

## About This Report

This report was generated by [HefestoAI](https://github.com/artvepa80/Agents-Hefesto),
an open-source deterministic code quality and security analyzer. No AI/LLM
was used for the analysis — all findings are from static, offline,
reproducible rules.

To reproduce:
```bash
pip install hefesto-ai
git clone --depth 1 https://github.com/anthropics/anthropic-sdk-python.git
hefesto analyze anthropic-sdk-python/ --severity LOW
```

**Contact:** Arturo — contact@narapallc.com / github.com/artvepa80
**License:** HefestoAI is MIT licensed.
