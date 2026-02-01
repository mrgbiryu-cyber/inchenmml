# Data Verification Walkthrough

## Goal
Verify the 3 broken chains by generating and checking logs.

## Prerequisites
- Ensure the backend and frontend are running.
- Open the Browser Console (F12) in the frontend.
- Have access to the backend terminal/logs.

## Step 1: Verify Visibility Chain (Chat History)
1. **Action**: Open the Chat Interface and select a project (or switch rooms).
2. **Frontend Check**: Look for `DEBUG: [Audit] Requesting GET ...` in the Browser Console. Note the `projectId` and `threadId`.
3. **Debug API Check**:
   - Open the **Network** tab in Developer Tools.
   - Filter for `chat_debug`.
   - Check if the request returns `404 Not Found`.
   - If 404, verify if the backend has processed the debug info before the frontend requested it (Race Condition).
4. **Backend Check**: Look for `AUDIT: get_chat_history called` or `AUDIT: get_thread_messages called` in the backend logs.
5. **Verification**:
   - Do the IDs match exactly? (Case, hyphens)
   - If the backend log shows the ID but returns 0 messages, run this SQL command to check the DB:
     ```sql
     SELECT count(*) FROM messages WHERE project_id = 'YOUR_PROJECT_ID';
     ```

## Step 2: Verify Connection Chain (Neo4j)
1. **Action**: Send a message in the chat that contains domain knowledge.
2. **Backend Check**: Look for `AUDIT: _upsert_to_neo4j called` in the logs.
3. **Database Check (Default Room)**:
   - Verify if a "Default Chat Room" exists for the project:
     ```sql
     SELECT * FROM threads WHERE project_id = 'YOUR_PROJECT_ID' AND title = '기본 대화방';
     ```
   - If missing, use this SQL to force-create it (Example):
     ```sql
     INSERT INTO threads (id, project_id, title, created_at, updated_at)
     VALUES ('thread-' || uuid_generate_v4(), 'YOUR_PROJECT_ID', '기본 대화방', NOW(), NOW());
     ```
4. **Verification**:
   - Check if `project_id` matches the one from Step 1.
   - Check if `source_message_id` is present.
   - If you see `[Neo4j] Transaction Failed`, capture the error message.

## Step 3: Verify Scoring Chain (Vector Search)
1. **Action**: Perform a search or ask a question that triggers RAG.
2. **Backend Check**:
   - Look for `AUDIT: generate_embedding called` -> Check `model` (should be `text-embedding-3-small`).
   - Look for `AUDIT: query_vectors called`.
3. **Metadata Verification**:
   - **CRITICAL**: Print the `filter` object sent to Pinecone.
   - Check if the `project_id` value is normalized (e.g., `system-master` vs `System-Master`).
   - Ensure the key matches your Pinecone index schema (e.g., `project_id` vs `projectId`).

## Reporting
Please paste the relevant logs here so I can analyze the "Actual" vs "Expected" values.
