# IMPLEMENTATION TASKLIST - Phase-by-Phase Execution Plan

**Generated**: 2026-01-24  
**Source**: Derived from /docs/fixplan/* documents  
**Status**: 🔵 Ready for Phase 1

---

## ⚠️ CRITICAL RULES

1. **MD-Only Source**: All tasks derived from fixplan/*.md ONLY
2. **Phase Approval**: MUST get user approval after Phase 1 before proceeding
3. **No Cross-Phase**: Do NOT modify files outside current phase scope
4. **Degraded Mode**: Do NOT change models on failure, do NOT throw on missing context
5. **Evidence-Based**: Every change references specific MD file + section

---

## 📋 PHASE 1: Runtime Stability + Conversation Consistency

**Priority**: CRITICAL (선행 필수)  
**Estimated Time**: 4-6 hours  
**Goal**: START TASK 멈춤 해결, 대화 목록 유지 보장

### Task 1.1: Add Orchestrator Timeouts ✅
**Source**: [RUNTIME_SPEC.md](./RUNTIME_SPEC.md) - "1. Add Timeout to Orchestrator Wait Points"  
**File**: `backend/app/services/orchestration_service.py`  
**Changes**:
- [x] Line 79-84: Add 300s timeout to `wait_for_start()`
- [x] Line 104-108: Add 600s timeout to `ask_approval()`
- [x] Raise `TimeoutError` if timeout exceeded
- [ ] Test: Workflow fails after 5min if no start_task event

**Evidence**: Line 81 현재 `while True` with no timeout  
**Status**: ✅ IMPLEMENTED

### Task 1.2: Implement Job Heartbeat ⏸️
**Reason**: Complex change crossing job_manager + worker, not critical for Phase 1  
**Status**: ⏸️ DEFERRED TO PHASE 2

### Task 1.3: Add Event Storage (Not Just Pub/Sub) ✅
**Source**: [RUNTIME_SPEC.md](./RUNTIME_SPEC.md) - "4. Event Stream Reliability"  
**File**: `backend/app/services/orchestration_service.py`  
**Changes**:
- [x] Line 182-200: Update `_publish_event()` to also store in Redis with TTL
- [x] Event key: `event:{project_id}:{event_type}` with 5min TTL
- [ ] Test: Event retrievable via HTTP GET even if WebSocket missed it

**Status**: ✅ IMPLEMENTED

### Task 1.4: Normalize project_id ✅
**Source**: [CONVERSATION_CONSISTENCY.md](./CONVERSATION_CONSISTENCY.md) - "1. Normalize project_id Input"  
**File**: `backend/app/core/database.py`  
**Changes**:
- [x] Line 115-143: Add `_normalize_project_id()` helper function
- [x] Line 127-133: Replace inline UUID conversion with helper
- [x] Lowercase + strip before uuid5() to ensure case-insensitivity
- [ ] Test: "Blog-Project" and "blog-project" → same UUID

**Status**: ✅ IMPLEMENTED

### Task 1.5: Return thread_id from save_message ✅
**Source**: [CONVERSATION_CONSISTENCY.md](./CONVERSATION_CONSISTENCY.md) - "2. Strict thread_id Contract"  
**File**: `backend/app/core/database.py`  
**Changes**:
- [x] Line 115: Change return type from `uuid.UUID` to `Tuple[uuid.UUID, str]`
- [x] Line 117-122: Auto-generate thread_id if None
- [x] Return `(msg_id, thread_id)`
- [x] **Breaking**: Update all 13 call sites in `master_agent_service.py`

**Status**: ✅ IMPLEMENTED

### Task 1.6: Update master_agent_service call sites ✅
**Source**: [CONVERSATION_CONSISTENCY.md](./CONVERSATION_CONSISTENCY.md) - "Breaking Changes"  
**File**: `backend/app/services/master_agent_service.py`  
**Changes**:
- [x] Line 302: `msg_id, thread_id = await save_message_to_rdb(...)`
- [x] Line 314: Updated
- [x] Line 332: Updated
- [x] Line 350: Updated
- [x] Line 370: Updated
- [x] Line 374: Updated
- [x] Line 384: Updated
- [x] Line 394: Updated
- [x] Line 446: Updated
- [x] Line 473: Updated
- [x] Line 500: Updated
- [x] Line 503: Updated
- [ ] Test: All 13 locations compile and run

**Status**: ✅ IMPLEMENTED

### Task 1.7: Add Database Indexes ⏸️
**Source**: [CONVERSATION_CONSISTENCY.md](./CONVERSATION_CONSISTENCY.md) - "3. Add Conversation Index"  
**File**: `backend/app/core/database.py` (or migration script)  
**Changes**:
- [ ] Add index: `idx_messages_project_thread` on `(project_id, thread_id, timestamp DESC)`
- [ ] Test: Query performance improved for conversation listing

**Status**: ⏸️ DEFERRED TO PHASE 2 (not critical for functionality)


---

## ✅ PHASE 1 VALIDATION (MUST PASS BEFORE PHASE 2)

### Test Scenarios
1. **Timeout Test**: Start workflow, don't send start_task → Fails after 5 min ✓
2. **Conversation Roundtrip**: Save with project="Proj-ABC" → Query with "proj-abc" → Message found ✓
3. **thread_id Generation**: Save with thread_id=None → Returns generated ID ✓
4. **No Regression**: Existing conversations still retrievable ✓

### Success Criteria
- [ ] START TASK timeout works (orchestrator doesn't hang forever)
- [ ] Conversation list persists after refresh (project_id normalized)
- [ ] All tests pass
- [ ] No exceptions in logs

**⏸️ STOP HERE - GET USER APPROVAL BEFORE PHASE 2**

---

## 📋 PHASE 2: KG Cleanup + Routing Verification

**Priority**: HIGH  
**Estimated Time**: 3-4 hours  
**Depends On**: Phase 1 approved

### Task 2.1: Expand Noise Filter Keywords
**Source**: [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md) - "1. Enhanced Noise Filter"  
**File**: `backend/app/services/knowledge_service.py`  
**Changes**:
- [ ] Line 121-137: Expand `noise_keywords` from 15 to 50+
- [ ] Add agent ops keywords: "에이전트 생성", "에이전트 추가", "system_prompt", etc.
- [ ] Add pattern matching with regex
- [ ] Test: "에이전트 추가해줘" → Filtered out

### Task 2.2: Add Role-Based Filtering
**Source**: [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md) - "2. Role-Based Filtering"  
**File**: `backend/app/services/knowledge_service.py`  
**Changes**:
- [ ] Line 74-119: Skip messages with `sender_role` in ["system", "tool"]
- [ ] Pass metadata to `_evaluate_importance()`
- [ ] Test: Tool messages not extracted to KG

### Task 2.3: Refine LLM Extraction Prompt
**Source**: [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md) - "3. LLM Prompt Refinement"  
**File**: `backend/app/services/knowledge_service.py`  
**Changes**:
- [ ] Line 192-216: Update prompt with EXCLUDE section
- [ ] Explicitly exclude: system operations, meta requests, agent management
- [ ] Test: Operational conversation → `{"nodes": [], "reason": "No domain knowledge"}`

### Task 2.4: Implement Content-Based Node ID
**Source**: [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md) - "5. Idempotency for Knowledge Nodes"  
**File**: `backend/app/services/knowledge_service.py`  
**Changes**:
- [ ] Line 275-337: Replace `uuid.uuid4()` with content hash
- [ ] `node_id = sha256(f"{project_id}:{content}").hexdigest()[:16]`
- [ ] Test: Same fact extracted twice → Only 1 node in Neo4j

### Task 2.5: Fix Agent Node Cleanup
**Source**: [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md) - "4. Neo4j Agent Node Cleanup"  
**File**: `backend/app/core/neo4j_client.py`  
**Changes**:
- [ ] Line 38-97: Add DELETE old agents before creating new ones
- [ ] Cypher: `MATCH (p:Project {id: $project_id})-[:HAS_AGENT]->(a:Agent) DETACH DELETE a`
- [ ] Test: Update project with 2 agents (was 3) → Only 2 agents in graph

### Task 2.6: Run One-Time Cleanup Script
**Source**: [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md) - "Clean-Up Operations"  
**File**: NEW `backend/scripts/cleanup_kg_pollution.py`  
**Changes**:
- [ ] Create script to delete operational cognition nodes
- [ ] Delete duplicates
- [ ] Run once manually
- [ ] Test: Cognition node count reduced significantly

### Task 2.7: Verify No Router/Cache (No Code Change)
**Source**: [ROUTING_FALLBACK_CACHE.md](./ROUTING_FALLBACK_CACHE.md) - "Conclusion"  
**Action**: Document finding - no cache layer exists
- [ ] Confirm: No LRU cache, no Redis response cache
- [ ] Note: "Fixed output" issue is H4 (KG pollution), not H3

---

## ✅ PHASE 2 VALIDATION

### Test Scenarios
1. **Noise Filter**: Send "에이전트 설정 변경해줘" → 0 nodes extracted ✓
2. **Idempotency**: Extract same fact twice → 1 node with updated timestamp ✓
3. **Agent Cleanup**: Update project agents → Old agents deleted ✓
4. **KG Quality**: Check node type distribution → Tools < 30% ✓

### Success Criteria
- [ ] Operational conversations not stored in KG
- [ ] Duplicate facts deduplicated
- [ ] Agent nodes cleaned up on project update

**⏸️ STOP HERE - GET USER APPROVAL BEFORE PHASE 3**

---

## 📋 PHASE 3: Model Strategy + Degraded Mode + Observability

**Priority**: MEDIUM-HIGH  
**Estimated Time**: 5-7 hours  
**Depends On**: Phase 2 approved

### Task 3.1: Create LLM Factory
**Source**: [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - "3. Centralized LLM Factory"  
**File**: NEW `backend/app/core/llm_factory.py`  
**Changes**:
- [ ] Create `ModelTier` enum (PRIMARY, SECONDARY)
- [ ] Create `LLMFactory.get_llm(tier)` method
- [ ] PRIMARY: deepseek/deepseek-chat-v3, 60s timeout
- [ ] SECONDARY: gpt-4o-mini, 30s timeout (log usage warning)
- [ ] Validate forbidden models (gpt-4o, gpt-4-turbo)
- [ ] Test: Factory returns correct model for each tier

### Task 3.2: Update Config for Model Strategy
**Source**: [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - "2. Configuration Schema"  
**File**: `backend/app/core/config.py`  
**Changes**:
- [ ] Line 91-92: Replace with PRIMARY_MODEL, PRIMARY_PROVIDER, etc.
- [ ] Add SECONDARY_MODEL, FORBIDDEN_MODELS list
- [ ] Test: Config loads successfully

### Task 3.3: Update Master Agent to Use Factory
**Source**: [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - "4. Update All Services"  
**File**: `backend/app/services/master_agent_service.py`  
**Changes**:
- [ ] Line 377-381: Replace `_get_llm()` with `LLMFactory.get_llm(ModelTier.PRIMARY)`
- [ ] Remove provider check (always use PRIMARY)
- [ ] Test: Master agent uses DeepSeek

### Task 3.4: Update Knowledge Service to Use Factory
**Source**: [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - "4. Update All Services"  
**File**: `backend/app/services/knowledge_service.py`  
**Changes**:
- [ ] Line 59-72: Remove tier-based selection
- [ ] Always use `LLMFactory.get_llm(ModelTier.PRIMARY)`
- [ ] Test: Knowledge extraction uses DeepSeek

### Task 3.5: Remove Hardcoded gpt-4o in Agents
**Source**: [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - "4. Update All Services"  
**File**: `backend/app/services/master_agent_service.py`  
**Changes**:
- [ ] Line 255-257: Remove hardcoded `model="gpt-4o"` in agent definitions
- [ ] Let orchestrator use factory (implementation in orchestration_service.py)
- [ ] Test: Agents use DeepSeek, not gpt-4o

### Task 3.6: Update Orchestration to Use Factory
**Source**: [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - "4. Update All Services"  
**File**: `backend/app/services/orchestration_service.py`  
**Changes**:
- [ ] Line 221-222: Force PRIMARY model, ignore agent-level override
- [ ] Use `LLMFactory.get_llm(ModelTier.PRIMARY)`
- [ ] Test: Workflow agents use DeepSeek

### Task 3.7: Implement Enhanced Tavily Client
**Source**: [RAG_AUDIT_AND_DEGRADED_MODE.md](./RAG_AUDIT_AND_DEGRADED_MODE.md) - "1. Enhanced Tavily Client"  
**File**: `backend/app/core/search_client.py`  
**Changes**:
- [ ] Add `SearchStatus` enum
- [ ] Add `SearchResult` dataclass
- [ ] Update `search()` to return `SearchResult` with status
- [ ] Add 10s timeout
- [ ] Classify errors: NO_RESULTS, TIMEOUT, NETWORK_ERROR, etc.
- [ ] Test: Timeout after 10s, status correctly classified

### Task 3.8: Update Web Search Tool for Degraded Mode
**Source**: [RAG_AUDIT_AND_DEGRADED_MODE.md](./RAG_AUDIT_AND_DEGRADED_MODE.md) - "2. Degraded Mode in Tool"  
**File**: `backend/app/services/master_agent_service.py`  
**Changes**:
- [ ] Line 49-61: Update `web_search_intelligence_tool()`
- [ ] Check `search_result.status`
- [ ] If degraded: Return "[웹 검색 사용 불가]..." message
- [ ] Do NOT throw, do NOT change model
- [ ] Test: Tavily down → Task continues with degraded context

### Task 3.9: Add Startup Validation
**Source**: [COLD_START_AND_DATA_HYGIENE.md](./COLD_START_AND_DATA_HYGIENE.md) - "Startup Validation"  
**File**: `backend/app/main.py`  
**Changes**:
- [ ] Add `@app.on_event("startup")` handler
- [ ] Check DB (required) - raise if fails
- [ ] Check Redis (required) - raise if fails
- [ ] Check Neo4j (optional) - warn if unavailable
- [ ] Check Pinecone (optional) - warn if unavailable
- [ ] Check Tavily (optional) - warn if unavailable
- [ ] Test: Server starts with only DB+Redis, logs warnings for others

### Task 3.10: Add Health Check Endpoint
**Source**: [COLD_START_AND_DATA_HYGIENE.md](./COLD_START_AND_DATA_HYGIENE.md) - "Monitoring Degraded Mode"  
**File**: `backend/app/main.py` or new router  
**Changes**:
- [ ] Add `GET /api/v1/health` endpoint
- [ ] Return service status for DB, Redis, Neo4j, Pinecone, Tavily
- [ ] Status: "connected", "unavailable", "error"
- [ ] Test: Endpoint returns correct status

### Task 3.11: Create Event Publisher
**Source**: [EVENT_SCHEMA.md](./EVENT_SCHEMA.md) - "Event Publishing Helper"  
**File**: NEW `backend/app/core/events.py`  
**Changes**:
- [ ] Create `EventPublisher` class
- [ ] `publish_event(event_type, data, project_id, user_id)`
- [ ] UTC timestamp with "Z" suffix
- [ ] Store in Redis list (last 1000, 24h TTL)
- [ ] Publish to pub/sub channel
- [ ] Test: Event published and retrievable

### Task 3.12: Integrate Event Publisher in Job Manager
**Source**: [EVENT_SCHEMA.md](./EVENT_SCHEMA.md) - "Usage Examples"  
**File**: `backend/app/services/job_manager.py`  
**Changes**:
- [ ] Publish `job_created` event on job creation
- [ ] Publish `job_status_changed` on status update
- [ ] Test: Events appear in Redis

### Task 3.13: Integrate Event Publisher in Orchestration
**Source**: [EVENT_SCHEMA.md](./EVENT_SCHEMA.md) - "Usage Examples"  
**File**: `backend/app/services/orchestration_service.py`  
**Changes**:
- [ ] Publish `workflow_step` events
- [ ] Test: Events published during workflow

### Task 3.14: Add Metrics Endpoint Stub
**Source**: [DASHBOARD_SIGNALS.md](./DASHBOARD_SIGNALS.md) - "Metrics API Endpoint"  
**File**: NEW router or add to existing  
**Changes**:
- [ ] `GET /api/v1/metrics/jobs` - queue depth, running count
- [ ] `GET /api/v1/metrics/llm` - cost, call count
- [ ] Return JSON with current values
- [ ] Test: Endpoints return valid JSON

---

## ✅ PHASE 3 VALIDATION

### Test Scenarios
1. **Model Strategy**: Send message → Verify DeepSeek used, cost logged ✓
2. **Tavily Degraded**: Mock Tavily down → Task continues, degraded message returned ✓
3. **Cold Start**: Start server with only DB+Redis → Server runs, logs warnings ✓
4. **Events**: Create job → Event in Redis with UTC timestamp ✓
5. **Health Check**: GET /health → Returns service status ✓

### Success Criteria
- [ ] All LLM calls use DeepSeek V3.1 (PRIMARY)
- [ ] Tavily failures don't stop tasks
- [ ] Server starts without Neo4j/Pinecone/Tavily
- [ ] Events published with UTC timestamps
- [ ] Health endpoint works

---

## 📋 PHASE 4: VectorDB Pipeline (Optional / Nice-to-Have)

**Priority**: LOW  
**Estimated Time**: 4-6 hours  
**Depends On**: Phase 3 approved  
**Note**: GAP identified - chunking/embedding not implemented

### Task 4.1: Install Dependencies
**Source**: [VECTORDB_RETRIEVAL_INGEST.md](./VECTORDB_RETRIEVAL_INGEST.md)  
**Changes**:
- [ ] Add to requirements.txt: `langchain`, `langchain-openai`
- [ ] Test: `pip install -r requirements.txt` succeeds

### Task 4.2: Create Chunking Service
**Source**: [VECTORDB_RETRIEVAL_INGEST.md](./VECTORDB_RETRIEVAL_INGEST.md) - "1. Document Chunking Service"  
**File**: NEW `backend/app/services/chunking_service.py`  
**Changes**:
- [ ] Implement `ChunkingService` with RecursiveCharacterTextSplitter
- [ ] chunk_size=500, chunk_overlap=50
- [ ] Return chunks with metadata
- [ ] Test: Long document → Multiple chunks with IDs

### Task 4.3: Create Embedding Service
**Source**: [VECTORDB_RETRIEVAL_INGEST.md](./VECTORDB_RETRIEVAL_INGEST.md) - "2. Embedding Service"  
**File**: NEW `backend/app/services/embedding_service.py`  
**Changes**:
- [ ] Implement `EmbeddingService` with OpenAIEmbeddings
- [ ] Model: text-embedding-3-small
- [ ] Async wrapper for embed_documents
- [ ] Test: Text list → Vector list

### Task 4.4: Create Document Upload Endpoint
**Source**: [VECTORDB_RETRIEVAL_INGEST.md](./VECTORDB_RETRIEVAL_INGEST.md) - "3. Document Upload API"  
**File**: NEW `backend/app/api/v1/documents.py`  
**Changes**:
- [ ] `POST /projects/{id}/documents/upload`
- [ ] Read file → Chunk → Embed → Upsert to Pinecone
- [ ] Test: Upload document → Chunks in Pinecone

### Task 4.5: Add Document Retrieval Tool
**Source**: [VECTORDB_RETRIEVAL_INGEST.md](./VECTORDB_RETRIEVAL_INGEST.md) - "4. Retrieval Integration"  
**File**: `backend/app/services/master_agent_service.py`  
**Changes**:
- [ ] Add `retrieve_documents_tool(query, project_id)`
- [ ] Embed query → Query Pinecone → Format results
- [ ] Test: Query retrieves relevant chunks

### Task 4.6: Add Document Delete Endpoint
**Source**: [VECTORDB_RETRIEVAL_INGEST.md](./VECTORDB_RETRIEVAL_INGEST.md) - "Cascade Delete"  
**File**: `backend/app/api/v1/documents.py`  
**Changes**:
- [ ] `DELETE /projects/{id}/documents/{doc_id}`
- [ ] Delete from Pinecone by doc_id metadata filter
- [ ] Test: Delete removes all chunks

---

## ✅ PHASE 4 VALIDATION

### Test Scenarios
1. **Upload**: Upload PDF → Chunked and embedded ✓
2. **Retrieval**: Query → Relevant chunks returned ✓
3. **Delete**: Delete doc → All chunks removed ✓

### Success Criteria
- [ ] Document upload pipeline works end-to-end
- [ ] Retrieval returns relevant content
- [ ] Cascade delete works

---

## 📊 FINAL VALIDATION (All Phases)

### Integration Tests
1. **START TASK Timeout**: Workflow doesn't hang ✓
2. **Conversation Persistence**: Refresh → Messages still visible ✓
3. **KG Quality**: Only domain knowledge stored ✓
4. **Model Consistency**: All calls use DeepSeek ✓
5. **Degraded Mode**: Tavily down → System works ✓
6. **Cold Start**: Start with minimal services → System works ✓
7. **Events**: All events have UTC timestamps ✓
8. **Cost Tracking**: Daily cost < $0.30 (vs $2.40 before) ✓

### Deliverable: IMPLEMENTATION_REPORT.md
- [ ] Summary of changes per phase
- [ ] Test results
- [ ] Remaining risks (if any)
- [ ] Reproduction scenarios

---

## 📈 Progress Tracking

- [ ] Phase 1 Complete (Runtime + Conversation)
- [ ] Phase 1 Approved by User ⏸️
- [ ] Phase 2 Complete (KG + Routing)
- [ ] Phase 2 Approved by User ⏸️
- [ ] Phase 3 Complete (Model + Degraded + Observability)
- [ ] Phase 3 Approved by User ⏸️
- [ ] Phase 4 Complete (VectorDB) - Optional
- [ ] Final Validation Complete
- [ ] IMPLEMENTATION_REPORT.md Created

**Current Status**: 🔵 Ready to Start Phase 1
