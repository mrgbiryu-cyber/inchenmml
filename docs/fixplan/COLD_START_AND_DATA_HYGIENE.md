# COLD START & DATA HYGIENE - Graceful Degradation Policy

**Purpose**: Define system behavior when data=0 or optional services unavailable  
**Principle**: Core functionality (chat, jobs) works without Neo4j/Pinecone/Tavily  
**Status**: Policy document - no code changes needed, only validation

---

## Cold Start Definition

**Cold Start** = One or more of:
- No messages in RDB (`MessageModel` table empty)
- No projects in Neo4j
- No cognition nodes in knowledge graph
- No vectors in Pinecone
- Tavily API key not configured
- Neo4j connection unavailable
- Pinecone connection unavailable

**Expected Behavior**: System should still accept messages and create jobs.

---

## Service Tier Classification

### ✅ Tier 1: Required (System Cannot Start Without These)

1. **PostgreSQL/SQLite** (RDB)
   - **File**: `backend/app/core/database.py`
   - **Why Required**: Message persistence, cost logs
   - **Startup Check**: `init_db()` must succeed
   - **Failure Mode**: Server startup fails with clear error

2. **Redis**
   - **File**: `backend/app/core/config.py:32`
   - **Why Required**: Job queues, state management, events
   - **Startup Check**: Connection test on server startup
   - **Failure Mode**: Server startup fails

3. **Master Agent (LLM)**
   - **File**: `backend/app/services/master_agent_service.py`
   - **Why Required**: Core chat functionality
   - **Startup Check**: `OPENROUTER_API_KEY` or `OLLAMA` reachable
   - **Failure Mode**: Chat requests return error, but server runs

---

### ⚠️ Tier 2: Optional (Degraded Mode if Unavailable)

1. **Neo4j**
   - **File**: `backend/app/core/neo4j_client.py`
   - **Why Optional**: Knowledge graph is enhancement, not requirement
   - **Degraded Mode**: 
     - Chat works without knowledge retrieval
     - Projects stored in RDB only (no graph queries)
   - **Current Status**: ✅ Already handled (line 11-20: `_connected = False` fallback)

2. **Pinecone (VectorDB)**
   - **File**: `backend/app/core/vector_store.py`
   - **Why Optional**: Document retrieval is enhancement
   - **Degraded Mode**:
     - Chat works without document context
     - Upload endpoints return "VectorDB not configured"
   - **Current Status**: ✅ Already handled (line 15: `self.client = None` if no API key)

3. **Tavily (Web Search)**
   - **File**: `backend/app/core/search_client.py`
   - **Why Optional**: External search is enhancement
   - **Degraded Mode**:
     - `web_search_intelligence_tool` returns "Search unavailable"
     - LLM continues with internal knowledge only
   - **Current Status**: ✅ Already handled (line 14: `self.client = None` if no API key)

---

## Startup Validation

### Server Initialization Checklist

**File**: `backend/app/main.py` (add to startup event)

```python
from app.core.database import init_db
from app.core.neo4j_client import neo4j_client
from app.core.vector_store import PineconeClient
from app.core.search_client import TavilyClient

@app.on_event("startup")
async def startup_validation():
    """
    Validate system readiness and log degraded mode warnings.
    """
    logger.info("🚀 MYLLM Server Starting...")
    
    # Tier 1: Required
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.critical(f"❌ Database init failed: {e}")
        raise  # Server cannot start
    
    # TODO: Add Redis connection test
    try:
        await redis_client.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.critical(f"❌ Redis connection failed {e}")
        raise  # Server cannot start
    
    # Tier 2: Optional (warn but don't fail)
    if neo4j_client._connected:
        logger.info("✅ Neo4j connected")
    else:
        logger.warning("⚠️ Neo4j unavailable - running in DEGRADED mode (no knowledge graph)")
    
    pinecone = PineconeClient()
    if pinecone.client:
        logger.info("✅ Pinecone configured")
    else:
        logger.warning("⚠️ Pinecone unavailable - running in DEGRADED mode (no vector retrieval)")
    
    tavily = TavilyClient()
    if tavily.client:
        logger.info("✅ Tavily configured")
    else:
        logger.warning("⚠️ Tavily unavailable - running in DEGRADED mode (no web search)")
    
    logger.info("🎯 Server ready")
```

---

## Data Hygiene Rules

### 1. Empty State is Valid

**RDB Empty**:
- First user message creates first row
- No pre-seeding required

**Neo4j Empty**:
- First project creation creates first graph
- `query_knowledge()` returns `[]` gracefully

**Pinecone Empty**:
- First document upload creates first vector
- `query_vectors()` returns `[]` gracefully

### 2. Orphan Prevention

**Avoid**:
- Messages with `project_id` that doesn't exist
- KG nodes with `project_id` that doesn't exist
- Vectors with `tenant_id` that doesn't exist

**Enforcement**:
- (Optional) Foreign key constraints in RDB
- (Recommended) Periodic cleanup scripts

**Cleanup Script** (weekly cron):
```python
# backend/scripts/cleanup_orphans.py

async def cleanup_orphan_messages():
    """Delete messages for deleted projects."""
    # This requires project table in RDB (not just Neo4j)
    # Defer until project model migrated to RDB

async def cleanup_orphan_vectors():
    """Delete vectors for deleted tenants."""
    # Query active tenant list from RDB
    # Query Pinecone namespaces
    # Delete orphaned namespaces
```

### 3. TTL Policy

**Redis** (already configured):
- Job specs: 7 days TTL
- Events: 5-10 min TTL
- Idempotency keys: 24h TTL

**Logs**:
- Application logs: Rotate daily, keep 30 days
- Cost logs in RDB: No TTL (required for billing)

### 4. GDPR/User Deletion

If user deleted:
1. Delete all messages where `metadata_json->>'user_id' = <user_id>`
2. Delete all KG nodes created by user
3. Delete all vectors with `user_id` in metadata
4. Mark user as deleted in users table (soft delete, for audit)

---

## Graceful Degradation Examples

### Example 1: Neo4j Down, Chat Continues

**Request**: User sends "Tell me about SEO"

**Normal Flow**:
1. Master agent calls `search_knowledge_tool("SEO")`
2. Neo4j returns 5 cognition nodes
3. LLM uses nodes as context → answer

**Degraded Flow**:
1. Master agent calls `search_knowledge_tool("SEO")`
2. Neo4j connection fails → returns `[]`
3. LLM uses only chat history → answer (less informed but works)

**Code**: No change needed - already returns `[]` on error (see `neo4j_client.py:query_knowledge()`)

### Example 2: Pinecone Down, Document Retrieval Skipped

**Request**: User asks "Summarize my uploaded docs"

**Normal Flow**:
1. Master agent calls `retrieve_documents_tool()`
2. Pinecone returns top 5 chunks
3. LLM summarizes

**Degraded Flow**:
1. Master agent calls `retrieve_documents_tool()`
2. Pinecone client is None → returns "VectorDB not configured"
3. LLM responds: "I don't have access to uploaded documents. Please provide the content directly."

**Code**: Already handled in `vector_store.py:15`

### Example 3: Tavily Down, Web Search Fails Gracefully

**Request**: User asks "Latest news about DeepSeek V3"

**Normal Flow**:
1. Master agent calls `web_search_intelligence_tool()`
2. Tavily returns 5 search results
3. LLM synthesizes answer

**Degraded Flow**:
1. Master agent calls `web_search_intelligence_tool()`
2. Tavily API fails → SearchStatus.NETWORK_ERROR
3. Tool returns "[웹 검색 사용 불가] 외부 검색 서비스 접근 불가..."
4. LLM uses internal knowledge only

**Code**: Implemented in [RAG_AUDIT_AND_DEGRADED_MODE.md](./RAG_AUDIT_AND_DEGRADED_MODE.md)

---

## Monitoring Degraded Mode

### Health Endpoint

**New**: `GET /api/v1/health`

```python
@app.get("/api/v1/health")
async def health_check():
    """
    System health check with service status.
    """
    return {
        "status": "healthy",  # or "degraded"
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "connected",  # or "error"
            "redis": "connected",
            "neo4j": "connected" if neo4j_client._connected else "unavailable",
            "pinecone": "configured" if PineconeClient().client else "unavailable",
            "tavily": "configured" if TavilyClient().client else "unavailable"
        }
    }
```

### Dashboard Indicator

UI should show:
- 🟢 All services operational
- 🟡 Degraded mode (1-2 services down)
- 🔴 Critical failure (database or Redis down)

---

## Testing Requirements

### Cold Start Tests

1. **Database Empty**:
   - Delete all rows from `messages` table
   - Send chat message
   - Verify message saved and response generated

2. **Neo4j Unreachable**:
   - Stop Neo4j container
   - Send chat message
   - Verify chat works, warning logged

3. **All Optional Services Down**:
   - Stop Neo4j, unset Pinecone/Tavily keys
   - Send chat message
   - Verify basic chat functionality works

---

## Implementation Checklist

- [ ] Add startup validation to `main.py`
- [ ] Add Redis connection test
- [ ] Add `/health` endpoint
- [ ] Document degraded mode behavior in README
- [ ] Create `cleanup_orphans.py` script
- [ ] Add degraded mode indicator to frontend
- [ ] Test cold start scenarios

---

## Breaking Changes

None (validation only)

---

## References

- `backend/app/core/database.py` - RDB (required)
- `backend/app/core/neo4j_client.py` - Neo4j (optional)
- `backend/app/core/vector_store.py` - Pinecone (optional)
- `backend/app/core/search_client.py` - Tavily (optional)
- [RAG_AUDIT_AND_DEGRADED_MODE.md](./RAG_AUDIT_AND_DEGRADED_MODE.md) - Tavily degradation

---

## Compliance

✅ **SQL = Required** - Startup validation enforces  
✅ **Vector/KG = Optional** - Gracefully degraded  
✅ **Graceful Degradation** - All examples documented  
✅ **Cold Start (data=0) = Normal** - No pre-seeding needed
