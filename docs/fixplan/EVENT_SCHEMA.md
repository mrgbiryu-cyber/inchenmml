# EVENT SCHEMA - Standardized Event and Time Authority

**Purpose**: UTC-based event schema for monitoring, debugging, and frontend updates  
**Time Authority**: Server UTC only - no client timestamps  
**Format**: JSON with strict schema

---

## Core Principles

### 1. UTC Time Authority

**Rule**: All timestamps generated **server-side** in UTC.

**Rationale**:
- Client clocks unreliable (timezone, drift, malicious)
- Server is single source of truth
- Database stores `DateTime` with UTC default

**Implementation**:
```python
from datetime import datetime

# ✅ Correct
timestamp = datetime.utcnow().isoformat() + "Z"

# ❌ Wrong
timestamp = datetime.now().isoformat()  # Local timezone ambiguous
```

### 2. Event Type Registry

All events must be one of:
- `job_created`
- `job_status_changed`
- `workflow_step`
- `master_response`
- `web_search`
- `knowledge_extracted`
- `error`

**Extensible**: Add new types as needed, document here.

---

## Event Schema (Standard)

### Base Schema

Every event MUST include:
```json
{
  "type": "string",           // Event type from registry
  "timestamp": "string",      // UTC ISO 8601 (e.g., "2026-01-24T14:00:00Z")
  "project_id": "string",     // (optional) Associated project
  "user_id": "string",        // (optional) Associated user
  "data": {}                  // Event-specific payload
}
```

### Job Events

**Type**: `job_created`
```json
{
  "type": "job_created",
  "timestamp": "2026-01-24T14:00:00Z",
  "project_id": "uuid",
  "user_id": "uuid",
  "data": {
    "job_id": "uuid",
    "execution_location": "LOCAL_MACHINE",
    "timeout_sec": 600
  }
}
```

**Type**: `job_status_changed`
```json
{
  "type": "job_status_changed",
  "timestamp": "2026-01-24T14:01:30Z",
  "data": {
    "job_id": "uuid",
    "old_status": "QUEUED",
    "new_status": "RUNNING",
    "worker_id": "worker-123"
  }
}
```

### Workflow Events

**Type**: `workflow_step`
```json
{
  "type": "workflow_step",
  "timestamp": "2026-01-24T14:02:00Z",
  "project_id": "uuid",
  "data": {
    "execution_id": "uuid",
    "agent_id": "agent_coder_123",
    "agent_role": "Coder",
    "status": "executing",  // or "completed", "failed"
    "message": "Generating code..."
  }
}
```

### Master Agent Events

**Type**: `master_response`
```json
{
  "type": "master_response",
  "timestamp": "2026-01-24T14:03:00Z",
  "project_id": "system-master",
  "user_id": "uuid",
  "data": {
    "thread_id": "abc123",
    "message_id": "uuid",
    "role": "assistant",
    "content_preview": "Here's how you can...",  // First 100 chars
    "tool_calls": ["search_knowledge_tool", "web_search_intelligence_tool"]
  }
}
```

### RAG/Search Events

**Type**: `web_search`
```json
{
  "type": "web_search",
  "timestamp": "2026-01-24T14:03:30Z",
  "data": {
    "query": "DeepSeek V3 pricing",
    "status": "success",  // or "no_results", "timeout", etc.
    "result_count": 5,
    "error_message": null
  }
}
```

**Type**: `knowledge_extracted`
```json
{
  "type": "knowledge_extracted",
  "timestamp": "2026-01-24T14:04:00Z",
  "project_id": "uuid",
  "data": {
    "message_id": "uuid",
    "node_count": 3,
    "edge_count": 2,
    "extraction_type": "realtime",  // or "batch"
    "cost_usd": 0.001
  }
}
```

### Error Events

**Type**: `error`
```json
{
  "type": "error",
  "timestamp": "2026-01-24T14:05:00Z",
  "project_id": "uuid",
  "data": {
    "error_type": "NETWORK_ERROR",
    "error_message": "Neo4j connection timeout",
    "component": "neo4j_client",
    "stack_trace": "..." // (optional, for debugging)
  }
}
```

---

## Event Storage (Redis)

### List-Based (for history)

**Key**: `events:{project_id}` (or `events:system` for global)

**Operation**:
```python
await redis_client.lpush(
    f"events:{project_id}",
    json.dumps(event)
)
await redis_client.ltrim(f"events:{project_id}", 0, 999)  # Keep last 1000
await redis_client.expire(f"events:{project_id}", 86400)  # 24h TTL
```

### Pub/Sub (for real-time)

**Channel**: `events:{project_id}`

**Publisher**:
```python
await redis_client.publish(
    f"events:{project_id}",
    json.dumps(event)
)
```

**Subscriber** (Frontend via WebSocket/SSE):
```python
pubsub = redis_client.pubsub()
await pubsub.subscribe(f"events:{project_id}")

async for message in pubsub.listen():
    if message["type"] == "message":
        event = json.loads(message["data"])
        # Send to WebSocket client
        await websocket.send_json(event)
```

---

## Event Publishing Helper

**New File**: `backend/app/core/events.py`

```python
from typing import Dict, Any, Optional
from datetime import datetime
import json
from app.core.config import settings

class EventPublisher:
    """
    Centralized event publishing with schema validation.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        project_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Publish event to Redis (both list storage and pub/sub).
        
        Args:
            event_type: One of registered event types
            data: Event-specific payload
            project_id: Associated project (optional)
            user_id: Associated user (optional)
        """
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "project_id": project_id,
            "user_id": user_id,
            "data": data
        }
        
        # Validate event_type (optional, for safety)
        valid_types = [
            "job_created", "job_status_changed", "workflow_step",
            "master_response", "web_search", "knowledge_extracted", "error"
        ]
        if event_type not in valid_types:
            logger.warning(f"Unknown event type: {event_type}")
        
        event_json = json.dumps(event, ensure_ascii=False)
        
        # Store in list (for history)
        channel = f"events:{project_id}" if project_id else "events:system"
        await self.redis.lpush(channel, event_json)
        await self.redis.ltrim(channel, 0, 999)
        await self.redis.expire(channel, 86400)
        
        # Publish for real-time (pub/sub)
        await self.redis.publish(channel, event_json)
        
        logger.debug(f"Event published: {event_type} to {channel}")

# Global instance
event_publisher = None

def init_event_publisher(redis_client):
    global event_publisher
    event_publisher = EventPublisher(redis_client)
```

---

## Usage Examples

### Job Manager
```python
# In job_manager.py:create_job()
await event_publisher.publish_event(
    event_type="job_created",
    data={
        "job_id": str(job_id),
        "execution_location": job_request.execution_location.value,
        "timeout_sec": job_request.timeout_sec
    },
    project_id=job_request.metadata.get("project_id"),
    user_id=str(user.id)
)
```

### Orchestration Service
```python
# In orchestration_service.py:_create_agent_node()
await event_publisher.publish_event(
    event_type="workflow_step",
    data={
        "execution_id": state.get("execution_id"),
        "agent_id": agent_def.agent_id,
        "agent_role": agent_def.role,
        "status": "executing",
        "message": f"Executing {agent_def.role}..."
    },
    project_id=str(project.id)
)
```

### Master Agent Service
```python
# In master_agent_service.py:stream_message()
await event_publisher.publish_event(
    event_type="master_response",
    data={
        "thread_id": thread_id,
        "message_id": str(msg_id),
        "role": "assistant",
        "content_preview": full_response_content[:100],
        "tool_calls": [tc["name"] for tc in valid_tool_calls]
    },
    project_id=project_id,
    user_id=str(user.id) if user else None
)
```

---

## Implementation Checklist

- [ ] Create `backend/app/core/events.py`
- [ ] Add `init_event_publisher()` to server startup
- [ ] Update `job_manager.py` to publish job events
- [ ] Update `orchestration_service.py` to publish workflow events
- [ ] Update `master_agent_service.py` to publish response events
- [ ] Update `search_client.py` to publish search events
- [ ] Add WebSocket/SSE endpoint for event streaming
- [ ] Add frontend event listener

---

## Frontend Integration

**WebSocket Endpoint**: `ws://localhost:8000/ws/events/{project_id}`

**Client**:
```javascript
const ws = new WebSocket(`wss://api.example.com/ws/events/${projectId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case "workflow_step":
      updateProgressBar(data.data.status);
      break;
    case "master_response":
      appendMessage(data.data.content_preview);
      break;
    case "error":
      showError(data.data.error_message);
      break;
  }
};
```

---

## Testing Requirements

1. **Timestamp Validation**:
   - Publish event without explicit timestamp
   - Verify ISO 8601 with "Z" suffix
   - Verify UTC (no timezone offset)

2. **Redis Storage**:
   - Publish 1005 events to same channel
   - Verify only last 1000 stored (LTRIM working)

3. **Pub/Sub**:
   - Subscribe to channel
   - Publish event
   - Verify subscriber receives event within 100ms

---

## Breaking Changes

None (new feature)

---

## References

- [RUNTIME_SPEC.md](./RUNTIME_SPEC.md) - Job events
- [DASHBOARD_SIGNALS.md](./DASHBOARD_SIGNALS.md) - Event monitoring
