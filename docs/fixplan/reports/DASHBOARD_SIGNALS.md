# DASHBOARD SIGNALS - Monitoring Metrics (Non-Automated)

**Purpose**: Define signals for manual monitoring and alerting  
**Scope**: Observability only - no automatic control actions  
**Format**: Metrics, queries, and alert thresholds

---

## Core Principle

**Data Collection**: Yes  
**Automatic Actions**: No

This document defines **what to measure** and **when to alert**, but system should NOT automatically:
- Restart workers
- Scale resources
- Modify configurations
- Kill jobs

Human operators review dashboard → take action manually.

---

## Metric Categories

### 1. Job Health Metrics

#### `jobs_queued_total{tenant_id}`
**Type**: Gauge  
**Source**: Redis `llen(job_queue:{tenant_id})`  
**Query**:
```python
async def get_queue_depth(tenant_id: str) -> int:
    return await redis_client.llen(f"job_queue:{tenant_id}")
```

**Alert**:
- **Warning**: > 20 jobs queued for > 5 minutes
- **Critical**: > 50 jobs queued (max queue size)

#### `jobs_running_total{tenant_id}`
**Type**: Gauge  
**Source**: Redis keys matching `job:*:status` with value "RUNNING"  
**Query**:
```python
async def get_running_jobs(tenant_id: str) -> int:
    keys = await redis_client.keys(f"job:*:status")
    count = 0
    for key in keys:
        status = await redis_client.get(key)
        if status == "RUNNING":
            # Check if tenant matches (parse job spec)
            count += 1
    return count
```

**Alert**:
- **Warning**: > 10 running jobs simultaneously (capacity issue)

#### `job_duration_seconds{status}`
**Type**: Histogram  
**Source**: `timestamp(job completion) - timestamp(job created)`  
**Buckets**: [10, 30, 60, 120, 300, 600, 1800, 3600]

**Query**:
```python
async def get_job_duration(job_id: str) -> float:
    created_at = await redis_client.get(f"job:{job_id}:created_at")
    # If completed, get result timestamp
    result = await redis_client.get(f"job:{job_id}:result")
    if result:
        result_data = json.loads(result)
        completed_at = result_data.get("timestamp")
        return (parse(completed_at) - parse(created_at)).total_seconds()
    return None
```

**Alert**:
- **Warning**: P95 duration > 1.5 × timeout_sec (jobs barely finishing)

### 2. Worker Health Metrics

#### `worker_heartbeat_last_seconds{worker_id}`
**Type**: Gauge  
**Source**: Redis `worker:{worker_id}:heartbeat` timestamp  
**Query**:
```python
async def get_worker_staleness(worker_id: str) -> float:
    last_heartbeat = await redis_client.get(f"worker:{worker_id}:heartbeat")
    if not last_heartbeat:
        return float('inf')
    last_time = datetime.fromisoformat(last_heartbeat.decode())
    return (datetime.utcnow() - last_time).total_seconds()
```

**Alert**:
- **Warning**: > 120 seconds (worker might be dead)
- **Critical**: > 300 seconds (worker definitely dead)

#### `worker_active_total`
**Type**: Gauge  
**Source**: Count of workers with heartbeat < 120s ago  
**Alert**:
- **Warning**: 0 active workers (no capacity)
- **Info**: > 5 active workers (scale-up happened)

### 3. LLM Health Metrics

#### `llm_call_total{model, status}`
**Type**: Counter  
**Labels**: `model` (e.g., "deepseek-chat-v3"), `status` (success/error)  
**Source**: Increment on each LLM call  
**Code**:
```python
# In llm_factory.py or master_agent_service.py
try:
    response = await llm.ainvoke(messages)
    metrics.increment("llm_call_total", labels={"model": model, "status": "success"})
except Exception as e:
    metrics.increment("llm_call_total", labels={"model": model, "status": "error"})
    raise
```

**Alert**:
- **Warning**: Error rate > 10% over 10 minutes

#### `llm_latency_seconds{model}`
**Type**: Histogram  
**Buckets**: [0.5, 1, 2, 5, 10, 30, 60]  
**Alert**:
- **Warning**: P95 latency > 10 seconds (slow responses)

#### `llm_cost_usd{tier}`
**Type**: Counter  
**Labels**: `tier` (primary/secondary)  
**Source**: Cost logs in RDB  
**Query**:
```python
async def get_daily_cost() -> float:
    # Query CostLogModel for last 24h
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.sum(CostLogModel.estimated_cost))
            .filter(CostLogModel.timestamp > datetime.utcnow() - timedelta(days=1))
        )
        return result.scalar() or 0.0
```

**Alert**:
- **Warning**: Daily cost > $4 (approaching $5 budget)
- **Critical**: Daily cost > $5 (budget exceeded)

### 4. Knowledge Graph Metrics

#### `kg_nodes_total{type, project_id}`
**Type**: Gauge  
**Labels**: `type` (Cognition, Project, Agent, Message)  
**Source**: Neo4j count queries  
**Query**:
```cypher
MATCH (n:Cognition {project_id: $project_id})
RETURN count(n) as total
```

**Alert**:
- **Warning**: > 10,000 Cognition nodes (possible pollution)

#### `kg_extraction_rate{status}`
**Type**: Counter  
**Labels**: `status` (success/skip/fail)  
**Source**: Knowledge service logs  
**Alert**:
- **Info**: Skip rate > 80% (heavy filtering working correctly)
- **Warning**: Fail rate > 10% (extraction errors)

### 5. RAG/Search Metrics

#### `web_search_total{status}`
**Type**: Counter  
**Labels**: `status` (success, no_results, timeout, error, etc.)  
**Source**: Tavily client (see RAG_AUDIT_AND_DEGRADED_MODE.md)  
**Alert**:
- **Warning**: Success rate < 50% over 1 hour
- **Critical**: Success rate < 10% over 1 hour

#### `vector_retrieval_latency_seconds`
**Type**: Histogram  
**Source**: Pinecone query calls  
**Alert**:
- **Warning**: P95 > 2 seconds (Pinecone slow)

### 6. Conversation Metrics

#### `conversations_total{project_id}`
**Type**: Gauge  
**Source**: RDB count distinct thread_id  
**Query**:
```python
async def get_conversation_count(project_id: str) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count(func.distinct(MessageModel.thread_id)))
            .filter(MessageModel.project_id == uuid.UUID(project_id))
        )
        return result.scalar()
```

**Alert**: None (informational only)

#### `messages_per_conversation{project_id}`
**Type**: Histogram  
**Source**: RDB group by thread_id, count messages  
**Alert**:
- **Info**: P50 > 50 messages (users engaging deeply)
- **Warning**: P99 > 200 messages (possible bot/spam)

---

## Dashboard Layout (Recommended)

### Page 1: Job System Health
```
┌─────────────────────────────────────────┐
│ Jobs Queued: 5                          │
│ Jobs Running: 2                         │
│ Workers Active: 3                       │
│ Avg Job Duration: 45s                   │
└─────────────────────────────────────────┘

[Graph: Job Queue Depth over 24h]
[Graph: Job Duration Histogram]
[Table: Recent Failed Jobs]
```

### Page 2: LLM Cost & Performance
```
┌─────────────────────────────────────────┐
│ Daily Cost: $1.23 / $5.00               │
│ Primary Model Calls: 145                │
│ Secondary Model Calls: 3                │
│ Avg Latency: 2.3s                       │
└─────────────────────────────────────────┘

[Graph: Hourly Cost Breakdown]
[Graph: LLM Latency P50/P95]
[Table: Top 10 Expensive Queries]
```

### Page 3: Knowledge Graph Health
```
┌─────────────────────────────────────────┐
│ Cognition Nodes: 1,234                  │
│ Extraction Rate: 85% filtered           │
│ Neo4j Status: Connected                 │
└─────────────────────────────────────────┘

[Graph: Node Count over Time by Type]
[Table: Recent Extractions (pass/skip/fail)]
```

### Page 4: RAG/Search Health
```
┌─────────────────────────────────────────┐
│ Tavily Success Rate: 92%                │
│ Vector Retrieval P95: 450ms             │
│ Pinecone Status: Connected              │
└─────────────────────────────────────────┘

[Graph: Search Status Distribution]
[Table: Recent Search Failures]
```

---

## Implementation Checklist

- [ ] Add metrics collection to job_manager.py
- [ ] Add metrics collection to master_agent_service.py
- [ ] Add metrics collection to knowledge_service.py
- [ ] Add metrics collection to search_client.py
- [ ] Create `/api/v1/metrics` endpoint (aggregation API)
- [ ] Create simple dashboard UI (React + charts)
- [ ] Add alert threshold configuration
- [ ] Document alert runbooks (what to do when alert fires)

---

## Metrics API Endpoint

**Example**: `GET /api/v1/metrics/jobs`

**Response**:
```json
{
  "queued": 5,
  "running": 2,
  "completed_last_24h": 45,
  "failed_last_24h": 2,
  "avg_duration_seconds": 45.3,
  "p95_duration_seconds": 120.5
}
```

**Example**: `GET /api/v1/metrics/llm`

**Response**:
```json
{
  "daily_cost_usd": 1.23,
  "primary_calls": 145,
  "secondary_calls": 3,
  "error_rate": 0.02,
  "avg_latency_seconds": 2.3,
  "p95_latency_seconds": 4.5
}
```

---

## Alert Runbooks

### Alert: "Job Queue Depth > 20 for 5 minutes"

**Possible Causes**:
1. Worker offline
2. Worker stuck on job
3. Surge in user requests

**Actions**:
1. Check worker heartbeat: `GET /api/v1/workers`
2. Check stuck jobs: `GET /api/v1/jobs?status=RUNNING`
3. If worker dead → restart worker
4. If job stuck → `POST /api/v1/jobs/{job_id}/cancel`

### Alert: "Daily Cost > $4"

**Possible Causes**:
1. Unexpected traffic spike
2. Knowledge extraction running on large batch
3. Expensive model accidentally used

**Actions**:
1. Check cost breakdown: `GET /api/v1/metrics/llm`
2. Check if secondary model overused
3. Pause knowledge extraction if needed: `POST /api/v1/admin/pause-knowledge`

### Alert: "Neo4j Cognition Nodes > 10,000"

**Possible Causes**:
1. Knowledge graph pollution (operational conversations stored)
2. Legitimate growth (many projects)

**Actions**:
1. Run cleanup script: `python backend/scripts/cleanup_kg_pollution.py`
2. Check node content: `GET /api/v1/admin/kg/sample-nodes`
3. If pollution → update noise filters

---

## Testing Requirements

1. **Metric Collection**:
   - Create job → Verify `jobs_queued_total` increments
   - Complete job → Verify `job_duration_seconds` recorded

2. **Alert Threshold**:
   - Mock queue depth = 25 → Verify warning alert fires

3. **Dashboard**:
   - Navigate to dashboard → Verify graphs render
   - Check refresh rate (30s recommended)

---

## Breaking Changes

None (new feature)

---

## References

- [RUNTIME_SPEC.md](./RUNTIME_SPEC.md) - Job metrics
- [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - LLM cost tracking
- [RAG_AUDIT_AND_DEGRADED_MODE.md](./RAG_AUDIT_AND_DEGRADED_MODE.md) - Search metrics
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md) - Event-based metrics

---

## Compliance

✅ **Data Collection** - Metrics defined  
✅ **Non-Automated** - No automatic actions  
✅ **Human Review** - Alert → Operator → Manual action
