# BUJA v5.0 Data Verification Report

**Date:** 2026-01-30
**Executor:** System Administrator
**Scope:** Visibility, Connection, Scoring Chains

## 1. Executive Summary
The data integrity verification process confirmed that the **Visibility Chain** (Chat Rooms/Threads) is fully operational and healthy. However, the **Connection Chain** (Knowledge Graph) shows signs of data quality issues (Null Titles), and the **Scoring Chain** (Vector Search) returned no results for the system-master context, indicating a potential metadata mismatch or empty index.

## 2. Detailed Findings

### ✅ Visibility Chain (PASSED)
*   **Thread Architecture**: 14 Projects successfully have "Default Chat Rooms" (기본 대화방).
*   **Orphaned Messages**: 0 messages found without a `thread_id`. Migration was successful.
*   **System Master**: Correctly identified in the database (Project ID: None/system-master).

### ⚠️ Connection Chain (WARNING)
*   **System Node**: `system-master` Project node exists in Neo4j.
*   **Data Quality**: 
    *   **Issue**: 21 nodes found with `title: None`.
    *   **Impact**: These nodes likely display as empty boxes or "Untitled" in the frontend graph view.
    *   **Cause**: `_upsert_to_neo4j` might be allowing nodes created without titles (e.g., pure logic nodes or extracted data with missing fields) to persist without a fallback label.

### ⚠️ Scoring Chain (WARNING)
*   **Connectivity**: Successfully connected to Pinecone index `buja-knowledge`.
*   **Retrieval**: 
    *   **Issue**: Test query for `tenant_id='system-master'` returned **0 matches**.
    *   **Possible Causes**: 
        1. No knowledge has been ingested for `system-master` yet.
        2. Metadata key mismatch (`project_id` vs `tenant_id` in Pinecone).
        3. Namespace mismatch (Query used `knowledge`, data might be in `default`).

## 3. Recommended Fix Plan

### Fix 1: Neo4j Data Cleansing & Hardening
*   **Action**: Run a Cypher query to find nodes with `title IS NULL` and update them with a fallback value (e.g., substring of content or "Untitled Node").
*   **Prevention**: Update `knowledge_service.py` to enforce a strictly non-null `title` before upsert.

### Fix 2: Pinecone Metadata Diagnosis
*   **Action**: Create a script to dump *all* metadata keys for a random vector in Pinecone to confirm the schema.
*   **Action**: Verify if `system-master` data exists. If not, run a manual ingestion of the "Project Seed" content.

### Fix 3: Frontend UX Polish
*   **Action**: Ensure the Graph View handles `null` titles gracefully by showing the node `id` or type instead of blank.

## 4. Conclusion
The core chat architecture is solid. We need to perform a "Data Hygiene" pass on Neo4j and verify the Vector Index contents to ensure RAG works correctly.
