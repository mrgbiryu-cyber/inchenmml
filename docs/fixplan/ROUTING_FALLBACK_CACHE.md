# ROUTING, FALLBACK & CACHE SPEC

**Issue**: H3 - 라우팅/폴백/캐시/후처리로 항상 같은 문구 출력  
**Evidence**: Codebase analysis shows no cache or template system  
**Conclusion**: "Fixed output" issue is likely misattribution → Root cause is H4 (KG pollution) or H7 (model inconsistency)

---

## Evidence Summary

### No Cache Layer Found
- **Search**: Scanned all `.py` files for "cache", "redis.get", "lru_cache"
- **Result**: 
  - ✅ Redis used for job queues and state
  - ❌ No LLM response caching found
  - ❌ No template post-processing found

### No Template System Found
- **Search**: Keyword "template", "render", "jinja", "mustache"
- **Result**: No template engine for response formatting

### Routing is Model Selection Only
- **File**: `backend/app/services/master_agent_service.py:377-381`
```python
def _get_llm(self):
    if self.config.provider == "OLLAMA":
        return ChatOllama(...)
    return ChatOpenAI(...)
```
- **Analysis**: Simple if/else, not a "router" that could cause fixed output

### Fallback is Minimal
- **File**: `backend/app/api/dependencies.py:75` - User not found fallback
- **File**: `backend/app/core/database.py:42` - UUID parse fallback
- **Analysis**: Error handling, not response generation

---

## Alternative Hypothesis

### If User Reports "항상 같은 문구 출력"...

**Likely Causes** (based on evidence):

1. **H4 - Knowledge Graph Pollution**:
   - User asks similar questions repeatedly
   - KG nodes polluted with previous Q&A pairs
   - LLM retrieves same context every time → same answer
   - **Fix**: [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md)

2. **H7 - Model/Temperature Settings**:
   - Temperature too low (deterministic)
   - Same input → same output (expected behavior of LLMs at temp=0)
   - **Current**: `temperature=0.7` (Line in master.py:9)
   - **Assessment**: Should be variable enough

3. **Context Window Not Cleared**:
   - Chat history accumulates
   - LLM sees all previous messages
   - Continues same conversation thread
   - **Fix**: Implement `/clear` or new thread function

---

## Design Solution

### 1. Verify "Fixed Output" Claim

**Action**: Request from user:
1. Exact same query sent twice
2. Copy of both responses
3. Thread ID / project ID

**Test**:
```python
# Send same message 3 times
for i in range(3):
    response = await master_agent_service.stream_message(
        message="What is SEO?",
        history=[],
        project_id="test",
        thread_id=f"test_{i}"  # Different threads
    )
    print(f"Response {i}: {response}")

# Expected: 3 different responses (with temp=0.7)
# If identical → bug confirmed
# If similar but not identical → LLM determinism, not a bug
```

### 2. Add Response Variation Controls

**File**: `backend/app/models/master.py`

**Current**:
```python
class MasterAgentConfig(BaseModel):
    model: str = "gpt-4o"
    temperature: float = 0.7
    provider: Literal["OPENROUTER", "OLLAMA"] = "OPENROUTER"
```

**Proposed** (Optional):
```python
class MasterAgentConfig(BaseModel):
    model: str = "deepseek/deepseek-chat-v3"  # See MODEL_STRATEGY.md
    temperature: float = 0.7
    top_p: float = 0.9  # NEW: Nucleus sampling
    provider: Literal["OPENROUTER", "OLLAMA"] = "OPENROUTER"
    
    # NEW: Response variation controls
    enable_context_injection: bool = True  # Inject "Be creative" prompt
    max_history_messages: int = 20  # Limit context window
```

### 3. Context Injection (If Needed)

**File**: `backend/app/services/master_agent_service.py:_construct_messages()`

**Addition**:
```python
if self.config.enable_context_injection and random.random() < 0.3:
    # 30% chance to inject variation prompt
    system_instruction += "\n\nProvide a fresh perspective on this topic."
```

**Note**: Only if determinism confirmed as problem.

### 4. Clear Thread Function

**New API Endpoint**: `POST /api/v1/projects/{project_id}/threads/{thread_id}/clear`

**Action**:
- Delete messages from thread in RDB
- Optionally clear KG nodes tagged with thread_id
- Return new thread_id to client

---

## Fallback Policies (Documented)

### LLM Call Failure
**Current**: Exception propagates  
**Proposed**: Return generic error message
```python
try:
    response = await llm.ainvoke(messages)
except Exception as e:
    logger.error(f"LLM call failed: {e}")
    return "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
```

### Context Retrieval Failure (KG/Vector)
**Current**: Empty context  
**Proposed**: Inform user
```python
try:
    knowledge = await neo4j_client.query_knowledge(project_id, query)
except Exception:
    knowledge = []
    logger.warning("Knowledge retrieval failed, using LLM only")
# Continue with LLM call
```

---

## Caching Strategy (Future)

**Not Implemented** (no evidence of need based on current symptoms)

**If Needed**:
```python
@lru_cache(maxsize=128)
def _cache_key(message: str, thread_id: str) -> str:
    return hashlib.sha256(f"{message}:{thread_id}".encode()).hexdigest()

async def get_cached_response(message: str, thread_id: str) -> Optional[str]:
    key = f"cache:response:{_cache_key(message, thread_id)}"
    cached = await redis_client.get(key)
    if cached:
        logger.info("Cache hit")
        return cached.decode()
    return None

async def cache_response(message: str, thread_id: str, response: str, ttl: int = 3600):
    key = f"cache:response:{_cache_key(message, thread_id)}"
    await redis_client.setex(key, ttl, response.encode())
```

**Cache Invalidation**:
- On thread clear
- On project config change
- On knowledge graph update

---

## Implementation Checklist

- [ ] Investigate user's "fixed output" claim with test cases
- [ ] Add `top_p` parameter to MasterAgentConfig (optional)
- [ ] Add `max_history_messages` limit (optional)
- [ ] Implement `/clear` endpoint for thread reset
- [ ] Add fallback messages for LLM failures
- [ ] Document fallback policies in code comments
- [ ] **Defer** response caching until proven necessary

---

## Testing Requirements

1. **Determinism Test**:
   - Same message, different thread_id → Different responses

2. **History Limit Test**:
   - Send 25 messages in thread → Verify only last 20 used as context

3. **Fallback Test**:
   - Mock LLM failure → Verify error message returned, not exception

---

## Breaking Changes

None

---

## References

- `backend/app/services/master_agent_service.py` - LLM integration
- `backend/app/models/master.py` - Configuration
- [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - Model selection policy
- [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md) - Context pollution fix

---

## Conclusion

**No router/fallback/cache system found that could cause "fixed output".**  
**Root cause more likely**: KG pollution (H4) or conversation context accumulation.  
**Action**: Fix H4 first, then re-evaluate if "fixed output" persists.
