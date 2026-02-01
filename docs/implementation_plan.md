# Audit & Verification Plan

## Goal
Diagnose and verify the 3 broken chains in BUJA v5.0 by instrumenting code with logs and verifying data against the database.

## User Review Required
> [!IMPORTANT]
> This plan focuses on **instrumentation and verification** first. Actual fixes will be proposed after discrepancies are confirmed.

## Proposed Changes (Instrumentation)

### Visibility Chain
#### [MODIFY] [ChatInterface.tsx](file:///d:/project/myllm/frontend/src/components/chat/ChatInterface.tsx)
- Add `console.log` in `fetchHistory` to print `targetThreadId` and `projectId`.
- **[CRITICAL]** Add logic to detect and log 'Race Conditions' where `threadId` might be `undefined` or null during initial load or switching.

#### [MODIFY] [projects.py](file:///d:/project/myllm/backend/app/api/v1/projects.py)
- Add logging to `get_thread_messages` and `get_chat_history` to print received `project_id` and `thread_id`.
- Log the raw SQL query or result count.

### Connection Chain
#### [MODIFY] [knowledge_service.py](file:///d:/project/myllm/backend/app/services/knowledge_service.py)
- Log `$p_id` in `_upsert_to_neo4j`.
- **[REFACTOR]** Modify Cypher queries to use `MATCH...WITH...MERGE` pattern to eliminate Cartesian product warnings.
- **[VERIFY]** Ensure an explicit transaction `commit()` is executed and verified in logs.

### Scoring Chain
#### [MODIFY] [embedding_service.py](file:///d:/project/myllm/backend/app/services/embedding_service.py)
- Log the model name used for embedding generation in `get_embedding` (verify it is exactly `text-embedding-3-small`).
- **[VERIFY]** Add code to cross-reference Pinecone search filter keys: check if `projectId` or `project_id` is used and if it matches the stored metadata format.

## Verification Plan

### Automated Verification
- None (Interactive debugging required).

### Manual Verification
1. **Visibility**:
   - Open Chat Interface.
   - Switch projects/rooms.
   - Check Browser Console for `thread_id`/`projectId`.
   - Check Backend Logs for received IDs.
   - Run SQL query (via `run_command` or user) to check `messages` table.

2. **Connection**:
   - Trigger knowledge extraction.
   - Check Backend Logs for Neo4j query parameters.
   - Verify Neo4j data (if accessible).

3. **Scoring**:
   - Perform a search.
   - Check Backend Logs for model name and metadata filter.
