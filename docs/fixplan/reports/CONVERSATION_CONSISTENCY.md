# CONVERSATION CONSISTENCY - Message Persistence & Retrieval

**Issue**: H2 - 대화 저장되었으나 목록에서 사라짐, session/user_id/conversation_id 불일치  
**Evidence**: Database schema, save/query functions, UUID handling코드  
**Goal**: 100% reliable conversation persistence and retrieval

---

## Evidence Summary

### Database Schema
- **File**: `backend/app/core/database.py:47-56`
- **Table**: `messages`
- **Columns**:
  - `message_id` - GUID(), primary key
  - `project_id` - GUID(), nullable
  - `thread_id` - String, nullable
  - `sender_role` - String, not null
  - `content` - Text, not null
  - `timestamp` - DateTime, default=utcnow
  - `metadata_json` - JSON, nullable

### Save Function
- **File**: `backend/app/core/database.py:115-143`
- **Function**: `save_message_to_rdb(role, content, project_id, thread_id, metadata)`
- **ID Generation**: Line 124 - `msg_id = uuid.uuid4()`
- **thread_id Filtering**: Line 117 - Treats "null", "undefined", "" as None
- **project_id Conversion**: Lines 127-133 - UUID() or uuid5() fallback

### Query Function
- **File**: `backend/app/core/database.py:145-166`
- **Function**: `get_messages_from_rdb(project_id, thread_id, limit=50)`
- **Filters**: Lines 154-161 - Filter by project_id AND/OR thread_id
- **Ordering**: Line 163 - `order_by(MessageModel.timestamp.asc())`

---

## Root Cause Analysis

### Issue #1: Inconsistent project_id Representation

**Evidence**:
```python
# Line 127-133 in database.py
p_id = None
if project_id and project_id != "system-master":
    try:
        p_id = uuid.UUID(project_id)
    except (ValueError, AttributeError):
        # Fallback for non-UUID strings
        p_id = uuid.uuid5(uuid.NAMESPACE_DNS, project_id)
```

**Problem**:
- Frontend may send `project_id = "blog-automation-123"` (string)
- First save: `uuid.uuid5(DNS, "blog-automation-123")` → UUID_A
- **If frontend capitalizes**: `"Blog-Automation-123"` → UUID_B (different!)
- Result: Messages saved under different UUIDs, can't retrieve

**Impact**: Case-sensitive string IDs cause fragmentation

### Issue #2: thread_id Null Handling Mismatch

**Evidence**:
```python
# Save: Line 117
if thread_id in ["null", "undefined", ""]:
    thread_id = None

# Query: Line 147-148
if thread_id in ["null", "undefined", ""]:
    thread_id = None
```

**Scenario**:
1. User starts conversation → Frontend sends `thread_id = undefined`
2. Backend converts to `None`, saves message
3. User refreshes page → Frontend sends `thread_id = "abc123"`
4. Query with `thread_id = "abc123"` → No match (messages have `None`)

**Impact**: Thread fragmentation if frontend inconsistent

### Issue #3: No Explicit Session Management

**Evidence**:
- ❌ No `session_id` or `conversation_id` in MessageModel
- ❌ No `user_id` foreign key constraint
- ✅ `metadata_json` can store `{"user_id": "..."}` but not indexed

**Problem**:
- Messages can be orphaned if `project_id` or `thread_id` lost
- No way to list "all conversations for user X"
- No way to list "all threads in project Y"

---

## Design Solution

### 1. Normalize project_id Input

**Location**: `backend/app/core/database.py:save_message_to_rdb()`

**Current**: String → UUID or uuid5(string)  
**Proposed**: 
```python
def _normalize_project_id(project_id: str) -> uuid.UUID:
    """
    Convert project_id to UUID consistently.
    - If valid UUID string → parse it
    - If special string ("system-master") → deterministic UUID
    - If arbitrary string → lowercase + uuid5
    """
    if not project_id or project_id == "system-master":
        return uuid.uuid5(uuid.NAMESPACE_DNS, "system-master")
    
    try:
        return uuid.UUID(project_id)
    except ValueError:
        # Normalize to lowercase before hashing
        normalized = project_id.lower().strip()
        return uuid.uuid5(uuid.NAMESPACE_DNS, normalized)
```

### 2. Strict thread_id Contract

**Proposed**:
- Frontend MUST send `thread_id` as:
  - Valid string (e.g., `uuid.uuid4().hex`) → Use as-is
  - `null` or omitted → Backend generates `uuid.uuid4().hex` and returns in response
- Backend: 
  - If `thread_id is None` → auto-generate
  - Return `thread_id` in save response so frontend can persist

**API Change**:
```python
# Current
async def save_message_to_rdb(...) -> uuid.UUID:
    return msg_id

# Proposed
async def save_message_to_rdb(...) -> Tuple[uuid.UUID, str]:
    if not thread_id:
        thread_id = uuid.uuid4().hex
    return msg_id, thread_id
```

### 3. Add Conversation Index

**Problem**: No way to list conversations

**Proposed Schema Addition** (non-breaking):
```sql
CREATE INDEX idx_messages_project_thread 
ON messages(project_id, thread_id, timestamp DESC);

CREATE INDEX idx_messages_user 
ON messages((metadata_json->>'user_id'), timestamp DESC);
```

**New Query Function**:
```python
async def list_conversations(project_id: str, user_id: str = None) -> List[Dict]:
    """
    List all unique thread_ids for a project (and optionally user).
    Returns: [{"thread_id": "...", "last_message": "...", "timestamp": ...}]
    """
    # GROUP BY thread_id, get latest message per thread
```

### 4. Explicit User Association

**Current**: `metadata_json = {"user_id": "..."}`  
**Proposed**: Add `user_id` column (nullable, indexed)

**Migration**:
```python
# Step 1: Add column (nullable)
op.add_column('messages', sa.Column('user_id', sa.String(), nullable=True))

# Step 2: Backfill from metadata_json
UPDATE messages SET user_id = metadata_json->>'user_id' WHERE metadata_json IS NOT NULL;

# Step 3: Add index
op.create_index('idx_messages_user_id', 'messages', ['user_id'])
```

---

## Consistency Guarantees

### Save Guarantees
1. **Idempotency**: Same `(content, project_id, thread_id, timestamp)` → Dedup check optional
2. **Atomicity**: SQLAlchemy async session auto-commit
3. **Durability**: SQLite WAL mode or PostgreSQL persistence

### Query Guarantees
1. **Ordering**: Always `timestamp ASC` → chronological
2. **Completeness**: If `project_id` and `thread_id` match, all messages returned (up to limit)
3. **Consistency**: Read-after-write guaranteed (async session committed before return)

---

## Frontend Contract

### Save Message
**Endpoint**: `POST /api/v1/projects/{project_id}/messages` (hypothetical)

**Request**:
```json
{
  "role": "user",
  "content": "Hello",
  "thread_id": "abc123" // or null
}
```

**Response**:
```json
{
  "message_id": "uuid-here",
  "thread_id": "abc123", // generated if was null
  "timestamp": "2026-01-24T14:00:00Z"
}
```

**Frontend Responsibility**:
- Store returned `thread_id` in localStorage/sessionStorage
- Include `thread_id` in all subsequent messages

### Get Messages
**Endpoint**: `GET /api/v1/projects/{project_id}/messages?thread_id=abc123&limit=50`

**Response**:
```json
{
  "messages": [
    {"message_id": "...", "role": "user", "content": "...", "timestamp": "..."},
    ...
  ],
  "thread_id": "abc123",
  "total": 25
}
```

### List Conversations
**Endpoint**: `GET /api/v1/projects/{project_id}/conversations`

**Response**:
```json
{
  "conversations": [
    {
      "thread_id": "abc123",
      "last_message": "How do I...",
      "last_timestamp": "2026-01-24T14:00:00Z",
      "message_count": 10
    }
  ]
}
```

---

## Implementation Checklist

- [ ] Add `_normalize_project_id()` helper function
- [ ] Update `save_message_to_rdb()` to return `(msg_id, thread_id)`
- [ ] Update `get_messages_from_rdb()` to use normalized project_id
- [ ] Add database index: `idx_messages_project_thread`
- [ ] Add `list_conversations()` function
- [ ] Add migration for `user_id` column (optional, Phase 2)
- [ ] Update API endpoints to match frontend contract
- [ ] Add integration test: save → query → verify exact match

---

## Testing Requirements

### Unit Tests
1. **Normalize project_id**:
   - "Blog-Project" and "blog-project" → Same UUID
   - "system-master" → Deterministic UUID
   - Valid UUID string → Parsed correctly

2. **thread_id Generation**:
   - Save with `thread_id=None` → Returns generated ID
   - Save with `thread_id="abc"` → Stores and returns "abc"

3. **Query Filtering**:
   - Save 3 messages (project=A, thread=1), 2 messages (project=A, thread=2)
   - Query (project=A, thread=1) → Returns 3 messages
   - Query (project=A, thread=None) → Returns all 5 messages

### Integration Tests
1. **Roundtrip Test**:
   ```python
   msg_id, thread_id = await save_message_to_rdb("user", "Hello", "proj1")
   messages = await get_messages_from_rdb("proj1", thread_id)
   assert len(messages) == 1
   assert messages[0].content == "Hello"
   ```

2. **Case Insensitivity**:
   ```python
   await save_message_to_rdb("user", "Msg1", "Proj-ABC")
   messages = await get_messages_from_rdb("proj-abc") # lowercase
   assert len(messages) == 1
   ```

3. **Thread Isolation**:
   ```python
   await save_message_to_rdb("user", "Thread1", "proj", "thread1")
   await save_message_to_rdb("user", "Thread2", "proj", "thread2")
   msgs = await get_messages_from_rdb("proj", "thread1")
   assert len(msgs) == 1
   assert msgs[0].content == "Thread1"
   ```

---

## Breaking Changes

**Minimal**:
- `save_message_to_rdb()` return type changes from `uuid.UUID` to `Tuple[uuid.UUID, str]`
- Callers must unpack: `msg_id, thread_id = await save_message_to_rdb(...)`

**Mitigation**:
- Provide backward-compatible wrapper if needed
- Or update all 13 call sites in codebase (search results show exact locations)

---

## References

- `backend/app/core/database.py` - MessageModel + save/query functions
- `backend/app/services/master_agent_service.py` - 13 call sites for save_message
- `backend/app/api/v1/projects.py:322` - API endpoint for message retrieval
- [COLD_START_AND_DATA_HYGIENE.md](./COLD_START_AND_DATA_HYGIENE.md) - Database=Required policy
