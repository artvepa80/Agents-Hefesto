# Hefesto API Implementation Plan

**Version:** v4.1.0
**Target Release:** Q1 2026
**Last Updated:** October 30, 2025
**Reference:** [API_ARCHITECTURE.md](./API_ARCHITECTURE.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Implementation Timeline](#implementation-timeline)
3. [Phase 1: Health & Monitoring](#phase-1-health--monitoring)
4. [Phase 2: Analysis Endpoints](#phase-2-analysis-endpoints)
5. [Phase 3: Findings Management](#phase-3-findings-management)
6. [Phase 4: Iris Integration](#phase-4-iris-integration)
7. [Phase 5: Metrics & Analytics](#phase-5-metrics--analytics)
8. [Phase 6: Configuration & Admin](#phase-6-configuration--admin)
9. [Testing Strategy](#testing-strategy)
10. [Deployment Strategy](#deployment-strategy)
11. [Rollback Plan](#rollback-plan)
12. [Success Metrics](#success-metrics)

---

## Executive Summary

**Goal:** Implement 15 REST API endpoints to support Hefesto standalone usage and OMEGA Guardian integration.

**Duration:** 4 weeks (20 working days)
**Team Size:** 1-2 developers
**Complexity:** Medium to High

### Key Milestones

| Milestone | Date | Deliverable |
|-----------|------|-------------|
| **Phase 1 Complete** | Week 1, Day 3 | Health & monitoring endpoints live |
| **Phase 2 Complete** | Week 1, Day 5 | Analysis API functional |
| **Phase 3 Complete** | Week 2, Day 3 | Findings management working |
| **Phase 4 Complete** | Week 2, Day 5 | Iris integration ready |
| **Phase 5 Complete** | Week 3, Day 2 | Metrics & analytics available |
| **Phase 6 Complete** | Week 3, Day 3 | Configuration endpoint done |
| **Integration Tests** | Week 3, Day 4-5 | End-to-end tests passing |
| **Documentation** | Week 4, Day 1-2 | API docs complete |
| **Beta Release** | Week 4, Day 3 | v4.1.0-beta deployed |
| **Production Release** | Week 4, Day 5 | v4.1.0 live |

---

## Implementation Timeline

### Week 1: Foundation & Core Analysis

```
Day 1-2: Phase 1 - Health & Monitoring
├─ Create FastAPI app structure
├─ Implement health endpoints
├─ Fix `hefesto serve` command
├─ Add CORS middleware
└─ Write unit tests

Day 3-5: Phase 2 - Analysis Endpoints
├─ Create analysis schemas
├─ Implement POST /api/v1/analyze
├─ Implement GET /api/v1/analyze/{id}
├─ Implement POST /api/v1/analyze/batch
└─ Write integration tests
```

### Week 2: Findings & Iris Integration

```
Day 1-3: Phase 3 - Findings Management
├─ Design BigQuery schema
├─ Implement findings persistence
├─ Implement GET /api/v1/findings
├─ Implement GET /api/v1/findings/{id}
├─ Implement PATCH /api/v1/findings/{id}
└─ Write tests with BigQuery mock

Day 4-5: Phase 4 - Iris Integration
├─ Implement code context extraction
├─ Implement correlation algorithm
├─ Implement GET /api/v1/iris/code-context
├─ Implement POST /api/v1/iris/correlate-alert
├─ Implement GET /api/v1/iris/findings-history
├─ Implement POST /api/v1/iris/webhook
└─ Write Iris integration tests
```

### Week 3: Metrics & Quality Assurance

```
Day 1-2: Phase 5 - Metrics & Analytics
├─ Implement metrics aggregation
├─ Implement GET /api/v1/metrics/summary
├─ Implement GET /api/v1/metrics/trends
└─ Write metrics tests

Day 3: Phase 6 - Configuration & Admin
├─ Implement GET /api/v1/config
└─ Write config tests

Day 4-5: Integration Testing
├─ End-to-end test suite
├─ Load testing (100 req/s)
├─ Security testing
└─ Performance profiling
```

### Week 4: Documentation & Release

```
Day 1-2: Documentation
├─ API documentation (OpenAPI)
├─ Integration guides
├─ Code examples
└─ Migration guide from CLI

Day 3: Beta Release
├─ Deploy to staging
├─ Smoke tests
├─ Performance validation
└─ Beta announcement

Day 4-5: Production Release
├─ Production deployment
├─ Monitoring setup
├─ Rollout verification
└─ v4.1.0 announcement
```

---

## Phase 1: Health & Monitoring

**Duration:** 2 days
**Priority:** CRITICAL
**Blockers:** None

### Objectives
1. Fix broken `hefesto serve` command
2. Implement basic health check
3. Implement detailed status endpoint
4. Set up FastAPI application structure

### Tasks

#### Task 1.1: Create FastAPI App (4 hours)

**File:** `hefesto/api/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from hefesto.__version__ import __version__
from hefesto.api.middleware import add_middlewares
from hefesto.api.routers import health

app = FastAPI(
    title="Hefesto API",
    description="AI-powered code quality analysis",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure per environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware (logging, etc.)
add_middlewares(app)

# Register routers
app.include_router(health.router)

@app.get("/")
async def root():
    return {
        "message": "Hefesto API",
        "version": __version__,
        "docs": "/docs"
    }
```

#### Task 1.2: Create Health Router (3 hours)

**File:** `hefesto/api/routers/health.py`

```python
from datetime import datetime
from fastapi import APIRouter
from hefesto.__version__ import __version__
from hefesto.api.schemas.common import APIResponse
from hefesto.api.schemas.health import HealthResponse, SystemStatusResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=APIResponse[HealthResponse])
async def health_check():
    """Basic health check for load balancers"""
    return APIResponse(
        success=True,
        data=HealthResponse(
            status="healthy",
            version=__version__,
            timestamp=datetime.utcnow()
        )
    )

@router.get("/api/v1/status", response_model=APIResponse[SystemStatusResponse])
async def system_status():
    """Detailed system status"""
    # Check analyzer availability
    analyzers = check_analyzers()
    integrations = check_integrations()

    return APIResponse(
        success=True,
        data=SystemStatusResponse(
            status="operational",
            version=__version__,
            analyzers=analyzers,
            integrations=integrations,
            uptime_seconds=get_uptime(),
            last_health_check=datetime.utcnow()
        )
    )
```

#### Task 1.3: Create Health Schemas (2 hours)

**File:** `hefesto/api/schemas/health.py`

```python
from datetime import datetime
from enum import Enum
from typing import Dict, Literal
from pydantic import BaseModel

class AnalyzerStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"

class IntegrationStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ENABLED = "enabled"
    DISABLED = "disabled"

class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    version: str
    timestamp: datetime

class SystemStatusResponse(BaseModel):
    status: Literal["operational", "degraded", "outage"]
    version: str
    analyzers: Dict[str, AnalyzerStatus]
    integrations: Dict[str, IntegrationStatus]
    uptime_seconds: int
    last_health_check: datetime
```

#### Task 1.4: Update CLI to Fix Import (1 hour)

**File:** `hefesto/cli/main.py`

```python
# Line 46: Change this
from hefesto.api.health import app

# To this
from hefesto.api.main import app
```

#### Task 1.5: Write Tests (4 hours)

**File:** `tests/api/test_health.py`

```python
import pytest
from fastapi.testclient import TestClient
from hefesto.api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "healthy"

def test_system_status():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "analyzers" in data["data"]
    assert "integrations" in data["data"]
```

### Deliverables
- [ ] FastAPI app created
- [ ] Health endpoints functional
- [ ] `hefesto serve` command works
- [ ] Tests passing (>90% coverage)
- [ ] Documentation updated

### Testing Checklist
- [ ] `hefesto serve` starts without errors
- [ ] `curl http://localhost:8080/health` returns 200
- [ ] `curl http://localhost:8080/api/v1/status` returns system status
- [ ] OpenAPI docs accessible at `/docs`

---

## Phase 2: Analysis Endpoints

**Duration:** 3 days
**Priority:** HIGH
**Dependencies:** Phase 1 complete

### Objectives
1. Enable programmatic code analysis
2. Support async analysis
3. Implement batch processing

### Tasks

#### Task 2.1: Create Analysis Schemas (4 hours)

**File:** `hefesto/api/schemas/analysis.py`

```python
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    path: str = Field(..., description="File or directory path")
    analyzers: Optional[List[str]] = None
    severity_threshold: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = "MEDIUM"
    format: Optional[Literal["json", "text", "html"]] = "json"
    exclude_patterns: Optional[List[str]] = []

class FindingSchema(BaseModel):
    id: str
    analyzer: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    file: str
    line: int
    column: Optional[int] = None
    description: str
    recommendation: str
    code_snippet: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None

class AnalysisSummary(BaseModel):
    total_issues: int
    critical: int
    high: int
    medium: int
    low: int

class AnalysisResponse(BaseModel):
    analysis_id: str
    path: str
    timestamp: datetime
    summary: AnalysisSummary
    findings: List[FindingSchema]
    execution_time_ms: int
```

#### Task 2.2: Implement Analysis Service (8 hours)

**File:** `hefesto/api/services/analysis_service.py`

```python
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from hefesto.analyzers import (
    ComplexityAnalyzer,
    SecurityAnalyzer,
    CodeSmellAnalyzer,
    BestPracticesAnalyzer
)
from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.api.schemas.analysis import AnalysisResponse, FindingSchema

class AnalysisService:
    def __init__(self):
        self.engine = AnalyzerEngine()
        self._register_analyzers()

    def _register_analyzers(self):
        self.engine.register_analyzer(ComplexityAnalyzer())
        self.engine.register_analyzer(SecurityAnalyzer())
        self.engine.register_analyzer(CodeSmellAnalyzer())
        self.engine.register_analyzer(BestPracticesAnalyzer())

    async def analyze(
        self,
        path: str,
        analyzers: Optional[List[str]] = None,
        severity_threshold: str = "MEDIUM",
        exclude_patterns: Optional[List[str]] = None
    ) -> AnalysisResponse:
        """Run code analysis"""
        start_time = datetime.utcnow()
        analysis_id = str(uuid.uuid4())

        # Validate path
        if not Path(path).exists():
            raise FileNotFoundError(f"Path not found: {path}")

        # Run analysis
        report = self.engine.analyze_path(
            path,
            exclude_patterns=exclude_patterns or []
        )

        # Convert to API format
        findings = self._convert_findings(report.issues)
        summary = self._create_summary(findings)

        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AnalysisResponse(
            analysis_id=analysis_id,
            path=path,
            timestamp=start_time,
            summary=summary,
            findings=findings,
            execution_time_ms=int(execution_time)
        )
```

#### Task 2.3: Implement Analysis Router (6 hours)

**File:** `hefesto/api/routers/analysis.py`

```python
from fastapi import APIRouter, HTTPException
from hefesto.api.schemas.common import APIResponse
from hefesto.api.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse
)
from hefesto.api.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/v1", tags=["Analysis"])
analysis_service = AnalysisService()

@router.post("/analyze", response_model=APIResponse[AnalysisResponse])
async def analyze_code(request: AnalysisRequest):
    """Analyze code file or directory"""
    try:
        result = await analysis_service.analyze(
            path=request.path,
            analyzers=request.analyzers,
            severity_threshold=request.severity_threshold,
            exclude_patterns=request.exclude_patterns
        )
        return APIResponse(success=True, data=result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### Task 2.4: Write Tests (6 hours)

**File:** `tests/api/test_analysis.py`

```python
import pytest
from fastapi.testclient import TestClient
from hefesto.api.main import app

client = TestClient(app)

def test_analyze_single_file(tmp_path):
    # Create test file
    test_file = tmp_path / "test.py"
    test_file.write_text("x = eval(input())")

    response = client.post("/api/v1/analyze", json={
        "path": str(test_file),
        "severity_threshold": "MEDIUM"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "analysis_id" in data["data"]
    assert len(data["data"]["findings"]) > 0

def test_analyze_invalid_path():
    response = client.post("/api/v1/analyze", json={
        "path": "/nonexistent/path.py"
    })
    assert response.status_code == 400
```

### Deliverables
- [ ] Analysis service implemented
- [ ] All 3 analysis endpoints working
- [ ] Tests passing (>85% coverage)
- [ ] API docs updated

---

## Phase 3: Findings Management

**Duration:** 3 days
**Priority:** MEDIUM
**Dependencies:** Phase 2 complete

### Objectives
1. Persist findings to BigQuery
2. Enable findings search and filtering
3. Support findings status updates

### Tasks

#### Task 3.1: Design BigQuery Schema (3 hours)

**File:** `hefesto/api/services/bigquery_schema.sql`

```sql
CREATE TABLE `hefesto_findings` (
  id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  analysis_id STRING NOT NULL,
  file_path STRING NOT NULL,
  line_number INT64 NOT NULL,
  column_number INT64,
  analyzer STRING NOT NULL,
  severity STRING NOT NULL,
  description STRING NOT NULL,
  recommendation STRING,
  code_snippet STRING,
  confidence FLOAT64 NOT NULL,
  status STRING NOT NULL DEFAULT 'open',
  first_seen TIMESTAMP NOT NULL,
  last_seen TIMESTAMP NOT NULL,
  occurrence_count INT64 NOT NULL DEFAULT 1,
  metadata JSON
);

-- Indexes
CREATE INDEX idx_file_path ON hefesto_findings(file_path);
CREATE INDEX idx_timestamp ON hefesto_findings(timestamp);
CREATE INDEX idx_severity ON hefesto_findings(severity);
CREATE INDEX idx_status ON hefesto_findings(status);
```

#### Task 3.2: Implement Findings Service (10 hours)

**File:** `hefesto/api/services/findings_service.py`

```python
from datetime import datetime
from typing import List, Optional
from google.cloud import bigquery

class FindingsService:
    def __init__(self):
        self.client = bigquery.Client()
        self.table_id = "hefesto_findings"

    async def save_finding(self, finding: Finding) -> str:
        """Save finding to BigQuery"""
        # Insert or update based on duplicate detection
        pass

    async def get_findings(
        self,
        file_path: Optional[str] = None,
        severity: Optional[str] = None,
        status: str = "open",
        limit: int = 50,
        offset: int = 0
    ) -> List[Finding]:
        """Query findings with filters"""
        pass

    async def get_finding(self, finding_id: str) -> Finding:
        """Get single finding by ID"""
        pass

    async def update_finding_status(
        self,
        finding_id: str,
        status: str,
        comment: Optional[str] = None
    ) -> Finding:
        """Update finding status"""
        pass
```

#### Task 3.3: Implement Findings Router (6 hours)

**File:** `hefesto/api/routers/findings.py`

```python
from fastapi import APIRouter, HTTPException, Query
from hefesto.api.services.findings_service import FindingsService

router = APIRouter(prefix="/api/v1/findings", tags=["Findings"])
findings_service = FindingsService()

@router.get("", response_model=APIResponse[FindingsListResponse])
async def list_findings(
    file_path: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List findings with filters"""
    findings = await findings_service.get_findings(
        file_path=file_path,
        severity=severity,
        limit=limit,
        offset=offset
    )
    return APIResponse(success=True, data=findings)
```

#### Task 3.4: Write Tests (5 hours)

**File:** `tests/api/test_findings.py`

```python
def test_list_findings():
    response = client.get("/api/v1/findings?limit=10")
    assert response.status_code == 200

def test_get_finding_by_id(finding_id):
    response = client.get(f"/api/v1/findings/{finding_id}")
    assert response.status_code == 200

def test_update_finding_status(finding_id):
    response = client.patch(
        f"/api/v1/findings/{finding_id}",
        json={"status": "resolved"}
    )
    assert response.status_code == 200
```

### Deliverables
- [ ] BigQuery schema created
- [ ] Findings persistence working
- [ ] All 3 findings endpoints functional
- [ ] Tests passing (>80% coverage)

---

## Phase 4: Iris Integration

**Duration:** 2 days
**Priority:** CRITICAL (for OMEGA Guardian)
**Dependencies:** Phase 2 & 3 complete

### Objectives
1. Enable code context extraction for alerts
2. Implement alert-to-finding correlation
3. Support historical findings analysis

### Tasks

#### Task 4.1: Implement Code Context Service (6 hours)

**File:** `hefesto/api/services/code_context_service.py`

```python
class CodeContextService:
    async def get_code_context(
        self,
        file_path: str,
        line_number: Optional[int] = None
    ) -> CodeContextResponse:
        """Extract code context for a file/line"""
        # Get complexity info
        complexity = await self._get_complexity(file_path, line_number)

        # Get security findings
        security_findings = await self._get_security_findings(file_path)

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            complexity,
            security_findings
        )

        return CodeContextResponse(
            file_path=file_path,
            line_number=line_number,
            complexity=complexity,
            security_findings=security_findings,
            risk_score=risk_score,
            risk_factors=self._identify_risk_factors(...)
        )
```

#### Task 4.2: Implement Correlation Service (10 hours)

**File:** `hefesto/api/services/correlation_service.py`

```python
class CorrelationService:
    async def correlate_alert(
        self,
        alert: AlertCorrelationRequest
    ) -> AlertCorrelationResponse:
        """Correlate production alert with findings"""
        # Parse stacktrace
        files_and_lines = self._parse_stacktrace(alert.stacktrace)

        # Find matching findings
        matching_findings = await self._find_matching_findings(
            files_and_lines,
            alert.error_type
        )

        # Calculate confidence score
        confidence = self._calculate_confidence(
            alert,
            matching_findings
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            alert,
            matching_findings
        )

        return AlertCorrelationResponse(
            correlation_id=str(uuid.uuid4()),
            alert_id=alert.alert_id,
            correlation_found=len(matching_findings) > 0,
            confidence_score=confidence,
            matching_findings=matching_findings,
            recommended_actions=recommendations
        )
```

#### Task 4.3: Implement Iris Router (6 hours)

**File:** `hefesto/api/routers/iris.py`

```python
from fastapi import APIRouter
from hefesto.api.services.code_context_service import CodeContextService
from hefesto.api.services.correlation_service import CorrelationService

router = APIRouter(prefix="/api/v1/iris", tags=["Iris Integration"])

@router.get("/code-context")
async def get_code_context(file_path: str, line_number: Optional[int] = None):
    """Get code context for alert enrichment"""
    service = CodeContextService()
    context = await service.get_code_context(file_path, line_number)
    return APIResponse(success=True, data=context)

@router.post("/correlate-alert")
async def correlate_alert(request: AlertCorrelationRequest):
    """Correlate production alert with findings"""
    service = CorrelationService()
    correlation = await service.correlate_alert(request)
    return APIResponse(success=True, data=correlation)
```

#### Task 4.4: Write Tests (6 hours)

**File:** `tests/api/test_iris.py`

```python
def test_get_code_context():
    response = client.get(
        "/api/v1/iris/code-context?file_path=test.py&line_number=10"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "complexity" in data
    assert "risk_score" in data

def test_correlate_alert():
    alert = {
        "alert_id": "alert_123",
        "error_type": "AttributeError",
        "stacktrace": "...",
        "timestamp": "2025-10-30T12:00:00Z"
    }
    response = client.post("/api/v1/iris/correlate-alert", json=alert)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "correlation_found" in data
    assert "confidence_score" in data
```

### Deliverables
- [ ] Code context extraction working
- [ ] Alert correlation functional
- [ ] All 4 Iris endpoints implemented
- [ ] Integration tests with Iris mock

---

## Phase 5: Metrics & Analytics

**Duration:** 2 days
**Priority:** MEDIUM
**Dependencies:** Phase 3 complete

### Tasks

#### Task 5.1: Implement Metrics Service (6 hours)

**File:** `hefesto/api/services/metrics_service.py`

```python
class MetricsService:
    async def get_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> MetricsSummaryResponse:
        """Get aggregate metrics"""
        # Query BigQuery for summary stats
        pass

    async def get_trends(
        self,
        period: str = "daily",
        days: int = 30
    ) -> MetricsTrendsResponse:
        """Get time-series trends"""
        # Query BigQuery for trends
        pass
```

#### Task 5.2: Implement Metrics Router (4 hours)

#### Task 5.3: Write Tests (4 hours)

### Deliverables
- [ ] Metrics aggregation working
- [ ] Trends calculation functional
- [ ] Both endpoints implemented

---

## Phase 6: Configuration & Admin

**Duration:** 1 day
**Priority:** LOW
**Dependencies:** None (can be done anytime)

### Tasks

#### Task 6.1: Implement Config Router (3 hours)

**File:** `hefesto/api/routers/config.py`

```python
@router.get("/config")
async def get_config():
    """Get Hefesto configuration"""
    return APIResponse(
        success=True,
        data=ConfigResponse(
            version=__version__,
            analyzers=get_analyzer_config(),
            integrations=get_integration_config(),
            license=get_license_info()
        )
    )
```

#### Task 6.2: Write Tests (2 hours)

### Deliverables
- [ ] Config endpoint working
- [ ] Tests passing

---

## Testing Strategy

### Unit Tests
**Target Coverage:** 85%+
**Tools:** pytest, pytest-cov

```bash
pytest tests/api/ --cov=hefesto/api --cov-report=html
```

### Integration Tests
**Scope:** End-to-end API flows

```python
def test_full_analysis_flow():
    # 1. Trigger analysis
    analysis_response = client.post("/api/v1/analyze", json={...})
    analysis_id = analysis_response.json()["data"]["analysis_id"]

    # 2. Retrieve analysis
    get_response = client.get(f"/api/v1/analyze/{analysis_id}")
    assert get_response.status_code == 200

    # 3. List findings
    findings_response = client.get("/api/v1/findings")
    assert findings_response.status_code == 200

    # 4. Update finding status
    finding_id = findings_response.json()["data"]["findings"][0]["id"]
    update_response = client.patch(
        f"/api/v1/findings/{finding_id}",
        json={"status": "resolved"}
    )
    assert update_response.status_code == 200
```

### Load Tests
**Tool:** Locust
**Target:** 100 requests/second sustained

```python
# locustfile.py
from locust import HttpUser, task, between

class HefestoUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def health_check(self):
        self.client.get("/health")

    @task(3)
    def analyze_code(self):
        self.client.post("/api/v1/analyze", json={
            "path": "test.py",
            "severity_threshold": "MEDIUM"
        })
```

Run: `locust -f locustfile.py --host=http://localhost:8080`

### Security Tests
**Tool:** OWASP ZAP

```bash
# Run ZAP baseline scan
docker run -v $(pwd):/zap/wrk/:rw \
  owasp/zap2docker-stable zap-baseline.py \
  -t http://localhost:8080/openapi.json \
  -r zap_report.html
```

---

## Deployment Strategy

### Staging Deployment

```bash
# Build Docker image
docker build -t hefesto-api:4.1.0-beta .

# Deploy to Cloud Run (staging)
gcloud run deploy hefesto-api-staging \
  --image hefesto-api:4.1.0-beta \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="ENV=staging"

# Verify deployment
curl https://hefesto-api-staging-xyz.run.app/health
```

### Production Deployment

```bash
# Tag production image
docker tag hefesto-api:4.1.0-beta hefesto-api:4.1.0

# Deploy with zero-downtime
gcloud run deploy hefesto-api \
  --image hefesto-api:4.1.0 \
  --region us-central1 \
  --min-instances=2 \
  --max-instances=10 \
  --set-env-vars="ENV=production"

# Gradual rollout (10% → 50% → 100%)
```

---

## Rollback Plan

### Rollback Triggers
- Error rate >5%
- P95 latency >2 seconds
- Critical bug discovered
- Customer complaints

### Rollback Procedure

```bash
# Step 1: Identify previous version
gcloud run revisions list --service=hefesto-api

# Step 2: Route traffic to previous version
gcloud run services update-traffic hefesto-api \
  --to-revisions=hefesto-api-00042-abc=100

# Step 3: Verify rollback
curl https://api.hefesto.dev/health
# Should return previous version

# Step 4: Investigate issue
# Check logs, metrics, alerts

# Step 5: Fix and redeploy
```

---

## Success Metrics

### Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Uptime** | >99.9% | Uptime Robot |
| **Error Rate** | <1% | Application logs |
| **P95 Latency** | <500ms | Prometheus |
| **Test Coverage** | >85% | pytest-cov |
| **Load Capacity** | 100 req/s | Locust |

### Business Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Adoption** | 50+ developers | API key registrations |
| **Iris Integration** | 100% success | Correlation accuracy |
| **Customer Satisfaction** | >4.5/5 | Support tickets |
| **Documentation Views** | 1000+/month | Analytics |

### Launch Criteria

**Beta Launch (v4.1.0-beta):**
- [ ] All 15 endpoints implemented
- [ ] Tests passing (>85% coverage)
- [ ] Load tests successful (100 req/s)
- [ ] Documentation complete
- [ ] Staging deployment verified

**Production Launch (v4.1.0):**
- [ ] Beta feedback addressed
- [ ] Security audit passed
- [ ] Performance benchmarks met
- [ ] Monitoring configured
- [ ] Rollback plan tested

---

## Risk Mitigation

### Risk 1: BigQuery Latency
**Impact:** Slow API responses
**Mitigation:**
- Implement Redis caching layer
- Use BigQuery streaming inserts
- Add response time monitoring

### Risk 2: Correlation Accuracy
**Impact:** Poor Iris integration
**Mitigation:**
- Extensive testing with real alerts
- Confidence threshold tuning
- Feedback loop from Iris

### Risk 3: Load Scalability
**Impact:** API unavailable under load
**Mitigation:**
- Horizontal scaling (Cloud Run)
- Rate limiting
- Async task queue (Celery)

---

## Post-Launch Tasks

### Week 1 Post-Launch
- [ ] Monitor error rates and latency
- [ ] Gather user feedback
- [ ] Fix critical bugs
- [ ] Performance tuning

### Week 2-4 Post-Launch
- [ ] Add missing features from feedback
- [ ] Optimize slow endpoints
- [ ] Improve documentation
- [ ] Plan v4.2.0 enhancements

---

**Document Status:** Ready for Implementation
**Next Action:** Begin Phase 1 implementation
**Estimated Completion:** 4 weeks from start date
