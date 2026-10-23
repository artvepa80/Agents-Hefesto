# Reliability Drift Detection (EPIC 4)

The Resource Safety Pack v1 detects 5 anti-patterns that cause memory leaks,
connection leaks, and resource exhaustion in long-running Python services.

Engine: `internal:resource_safety_v1`
Confidence: 0.85 (static heuristic)
All severities: MEDIUM

These patterns are especially common in AI-generated code because LLMs
optimize for "works in a script" rather than "works in a server."

## R1 — RELIABILITY_UNBOUNDED_GLOBAL

**What**: Module-level mutable (dict, list, set) that gets mutated inside
functions. In long-running workers, this grows without bound.

**Trigger pattern**:
```python
# Module level
cache = {}

def handle_request(key, value):
    cache[key] = value  # grows forever in a web server
```

**Fix**: Move mutable into function scope, use `lru_cache(maxsize=N)`,
or add periodic cleanup.

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_value(key):
    return expensive_lookup(key)
```

## R2 — RELIABILITY_UNBOUNDED_CACHE

**What**: `@lru_cache(maxsize=None)` or `@cache` — the cache grows
without any eviction policy.

**Trigger pattern**:
```python
from functools import lru_cache

@lru_cache(maxsize=None)
def get_user(user_id):
    return db.query(user_id)
```

**Fix**: Set an explicit maxsize.

```python
@lru_cache(maxsize=128)
def get_user(user_id):
    return db.query(user_id)
```

## R3 — RELIABILITY_SESSION_LIFECYCLE

**What**: `Session()`, `connect()`, `create_engine()`, etc. assigned
inside a function without a context manager (`with`) or explicit `.close()`.

**Trigger pattern**:
```python
def fetch_data():
    session = requests.Session()
    response = session.get(url)
    return response.json()
    # session is never closed — connection leak
```

**Fix**: Use a context manager or explicit cleanup.

```python
def fetch_data():
    with requests.Session() as session:
        response = session.get(url)
        return response.json()
```

Detected constructors: Session, ClientSession, connect, create_connection,
create_engine, urlopen, HTTPConnection, HTTPSConnection.

## R4 — RELIABILITY_LOGGING_HANDLER_DUP

**What**: `addHandler()` called inside a function body. Each function call
adds another handler, causing duplicate log entries that multiply over time.

**Trigger pattern**:
```python
def setup_logging():
    logger = logging.getLogger("app")
    logger.addHandler(logging.StreamHandler())
    # called per-request: 100 requests = 100 handlers
```

**Fix**: Configure handlers at module level or guard against duplicates.

```python
logger = logging.getLogger("app")
logger.addHandler(logging.StreamHandler())
# configured once at import time
```

## R5 — RELIABILITY_THREAD_IN_REQUEST

**What**: `threading.Thread()` spawned inside a function. In request
handlers, this creates uncontrolled thread growth.

**Trigger pattern**:
```python
import threading

def handle_upload(file):
    t = threading.Thread(target=process, args=(file,))
    t.start()
    # 1000 uploads = 1000 threads = OOM
```

**Fix**: Use a bounded ThreadPoolExecutor or async task queue.

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

def handle_upload(file):
    executor.submit(process, file)
```

## Why AI Code Triggers These

LLMs generate code that works in isolation (scripts, notebooks, one-off runs).
They don't model process lifetime. Common AI patterns:

- "Let me add a cache" → `@cache` without maxsize
- "Let me store results" → module-level dict, never cleared
- "Let me run this in background" → raw Thread(), no pool
- "Let me add logging" → addHandler() in every function
- "Let me connect to the DB" → Session() without `with`

HefestoAI catches these at commit time, before they reach production.

## CLI Usage

```bash
# All reliability rules run by default in Phase 0
hefesto analyze .

# Gate on reliability issues
hefesto analyze . --fail-on MEDIUM

# Enable memory budget gate (measures actual allocation)
hefesto analyze . --enable-memory-budget-gate
```
