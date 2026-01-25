# RUNTIME SPEC - Workflow Execution & Job Management

**Issue**: H1 - START TASK 멈춤, Job/Worker/State/Timeout 고착  
**Evidence**: Analysis based on file paths and code inspection  
**Goal**: Reliable workflow execution with proper timeout and state management

---

## Evidence Summary

### Worker Polling Loop
- **File**: `local_agent_hub/worker/poller.py:165-232`
- **Function**: `poll_loop(executor_callback)`
- **Mechanism**: Long polling with 30s timeout (line 61)
- **Issue**: No evidence of stuck polling, but timeout is sync-only

### Job State Machine
- **File**: `backend/app/services/job_manager.py:129`
- **Initial State**: `"status": JobStatus.QUEUED.value`
- **State Progression**: QUEUED → RUNNING → COMPLETED/FAILED/TIMEOUT
- **Storage**: Redis keys `job:{job_id}:status`

### Orchestration Pause Points
- **File**: `backend/app/services/orchestration_service.py:79-84`
- **Function**: `wait_for_start(state)` - Waits for 'start_task' event
- **File**: `backend/app/services/orchestration_service.py:104-108`
- **Function**: `ask_approval(state)` - Waits for 'approve_push' event
- **Issue**: No timeout on event wait → infinite blocking possible

### Event Publishing
- **File**: `backend/app/services/orchestration_service.py:182-200`
- **Function**: `_publish_event(project_id, event_type, data)`
- **Transport**: Redis pub/sub via `redis_client.publish()`
- **Frontend**: Must subscribe to `project:{project_id}:events` channel

---

## Root Cause Analysis

### Blocking Issue #1: Event Stream Not Received

**Symptom**: Orchestrator prints "⏳ Paused. Waiting for 'start_task' event..." and never continues

**Hypothesis**:
1. Frontend does not send event to correct Redis channel
2. Frontend sends event but orchestrator already past the wait point
3. Redis pub/sub connection dropped

**Evidence Gap**:
- ❌ No frontend event emission code found
- ❌ No Redis connection health check in orchestrator
- ❌ No timeout on `asyncio.sleep()` loops in wait functions

### Blocking Issue #2: Job Stuck in QUEUED

**Symptom**: Worker never picks up job

**File**: `backend/app/services/job_manager.py:403-418`  
**Function**: `fix_orphaned_jobs(tenant_id)` - Marks QUEUED jobs not in queue as FAILED

**Root Cause**:
1. Job created and saved to Redis
2. Job pushed to `job_queue:{tenant_id}`
3. Worker polls queue but signature verification fails → job dropped
4. Job remains QUEUED in status but removed from queue

**File**: `local_agent_hub/worker/poller.py:112-142`  
**Function**: `verify_and_validate_job(job)`  
**Issue**: If verification fails, job is reported as security violation but status not updated

---

## Design Solution

### 1. Add Timeout to Orchestrator Wait Points

**Location**: `backend/app/services/orchestration_service.py`

**Current**:
```python
async def wait_for_start(state: AgentState):
    while True:
        event = await redis_client.get(f"event:{project_id}:start_task")
        if event:
            break
        await asyncio.sleep(1)
```

**Proposed**:
```python
async def wait_for_start(state: AgentState):
    timeout = 300  # 5 minutes
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError("START TASK event not received within 5 minutes")
        event = await redis_client.get(f"event:{project_id}:start_task")
        if event:
            break
        await asyncio.sleep(1)
```

### 2. Job Heartbeat & Lease Mechanism

**Problem**: No evidence of job heartbeat or lease system

**Proposed**:
- Worker acquires job with lease (e.g., 60 seconds)
- Worker sends heartbeat every 30 seconds
- If heartbeat not received, job lease expires → job re-queued
- Job has `retry_count` (max 3) to prevent infinite retries

**Implementation**:
- `backend/app/services/job_manager.py` - Add `acquire_job_with_lease()`
- `local_agent_hub/worker/executor.py` - Add heartbeat during execution

### 3. Worker Dead Letter Queue (DLQ)

**Problem**: Jobs that fail verification disappear

**Proposed**:
- Security violations → `job_dlq:{tenant_id}` queue
- Admin can inspect DLQ and re-sign jobs if needed
- DLQ entries expire after 24 hours

### 4. Event Stream Reliability

**Problem**: No confirmation that frontend receives orchestrator events

**Proposed**:
- Orchestrator publishes event + stores in Redis with TTL
- Frontend polls event store if WebSocket/SSE connection fails
- Hybrid: SSE for real-time + HTTP polling fallback

---

## State Diagram (Corrected)

```
[Client Request]
      ↓
[JobManager.create_job()]
      ↓
[QUEUED] → Redis: job_queue:{tenant_id}
      ↓
[Worker.poll_once()] → Signature Verify
      ↓                    ↓ FAIL
[RUNNING]            [DLQ + Report]
      ↓
[Executor.execute_job()]
      ↓ (heartbeat every 30s)
[COMPLETED / FAILED / TIMEOUT]
      ↓
[JobManager.update_job_status()]
```

---

## Timeout Policy (Unified)

| Component | Timeout | Location | Current | Proposed |
|-----------|---------|----------|---------|----------|
| Worker Long Poll | 30s | `local_agent_hub/core/config.py:69` | ✅ | Keep |
| Job Execution | 600s (default) | `backend/app/models/schemas.py:96` | ✅ | Keep |
| Job Max | 3600s | `backend/app/core/config.py:76` | ✅ | Keep |
| Orchestrator Wait | None | `orchestration_service.py:81` | ❌ | Add 300s |
| Approval Wait | None | `orchestration_service.py:106` | ❌ | Add 600s |
| LLM Call (Ollama) | 30s | `master_agent_service.py:380` | ✅ | Keep |
| LLM Call (OpenRouter) | 60s | `master_agent_service.py:381` | ✅ | Keep |

---

## Redis Key Schema (Documented)

### Job Storage
- `job:{job_id}:spec` - Full job JSON (TTL: 7 days)
- `job:{job_id}:status` - Current status string (TTL: 7 days)
- `job:{job_id}:created_at` - ISO timestamp (TTL: 7 days)
- `job:{job_id}:result` - Execution result (TTL: 7 days)

### Queue Management
- `job_queue:{tenant_id}` - FIFO list of job_ids
- `job_dlq:{tenant_id}` - Dead letter queue (TTL: 24h)

### Idempotency
- `job:idempotency:{key}` - Prevents duplicate job creation (TTL: 24h)

### Events (NEW)
- `event:{project_id}:start_task` - Start task event payload (TTL: 5min)
- `event:{project_id}:approve_push` - Approval event payload (TTL: 10min)

### Worker Heartbeat (NEW)
- `worker:{worker_id}:heartbeat` - Last heartbeat timestamp (TTL: 2min)
- `job:{job_id}:lease` - Worker lease info (TTL: 60s)

---

## Monitoring Signals

### Health Check Endpoints
- `GET /api/v1/jobs/{job_id}/status` - Job status
- `GET /api/v1/workers` - Active workers (with heartbeat)

### Metrics to Expose
- `jobs_queued_total{tenant_id}` - Current queue depth
- `jobs_running_total{tenant_id}` - Active jobs
- `jobs_stuck_duration_seconds{job_id}` - Time in QUEUED state
- `worker_heartbeat_last_seconds{worker_id}` - Time since last heartbeat

### Alerts (Non-Automated)
- Job in QUEUED > 5 minutes → Investigate
- Job in RUNNING > timeout_sec → Force FAILED
- Worker heartbeat missing > 2 minutes → Mark offline

---

## Implementation Checklist

- [ ] Add timeout to `wait_for_start()` and `ask_approval()`
- [ ] Implement job lease + heartbeat mechanism
- [ ] Add dead letter queue for failed verifications
- [ ] Store events in Redis with TTL (not just pub/sub)
- [ ] Add worker health check endpoint
- [ ] Update job status to TIMEOUT if execution exceeds limit
- [ ] Add monitoring for queue depth and stuck jobs
- [ ] Document Redis key TTL policy

---

## Testing Requirements

1. **Timeout Test**: Start workflow but never send start_task event → Should fail after 5min
2. **Heartbeat Test**: Worker starts job but crashes mid-execution → Job should re-queue after 60s
3. **Signature Fail Test**: Invalid signature → Job goes to DLQ, not stuck in QUEUED
4. **Orphan Cleanup**: Run `fix_orphaned_jobs()` → QUEUED jobs not in queue marked FAILED

---

## Breaking Changes

None - This is additive hardening.

---

## References

- `local_agent_hub/worker/poller.py` - Polling mechanism
- `local_agent_hub/worker/executor.py` - Job execution
- `backend/app/services/job_manager.py` - Job lifecycle
- `backend/app/services/orchestration_service.py` - Workflow orchestration
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md) - Event standardization
