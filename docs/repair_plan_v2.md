# BUJA v5.0 Final Repair Plan

## Goal
Address the data quality issues identified in the Verification Report to achieve 100% system integrity.

## 1. Connection Chain Repair (Neo4j)
### Task 1.1: Clean up "Null Title" Nodes
**Objective**: Fix the 21 nodes with `title: None`.
**Plan**:
1. Create a Python script `scripts/fix_neo4j_titles.py`.
2. Logic:
   - Match nodes where `n.title` is NULL or `n.title = 'None'`.
   - Set `n.title` to `n.name` if available, or `substring(n.content, 0, 20)`, or "Unknown Concept".
   - Log the number of updated nodes.

### Task 1.2: Enforce Title in Code
**Objective**: Prevent future null titles.
**Plan**:
- Modify `knowledge_service.py` -> `_upsert_to_neo4j`.
- Add a strict fallback: `title = node.get("title") or node.get("name") or "Untitled ({type})"`.

## 2. Scoring Chain Repair (Pinecone)
### Task 2.1: Metadata & Content Verification
**Objective**: Figure out why `system-master` returns 0 results.
**Plan**:
1. Update `scripts/check_ingestion_debug.py` to:
   - Fetch *any* vector from Pinecone without filters.
   - Print its metadata keys to confirm if we use `tenant_id` or `project_id`.
   - Check if `system-master` has ANY vectors.
2. If empty, trigger "Seed Knowledge" ingestion for `system-master` manually.

## 3. Execution Steps
1. **Run** `scripts/check_ingestion_debug.py` (updated) to diagnose Pinecone.
2. **Run** `scripts/fix_neo4j_titles.py` to clean Neo4j.
3. **Verify** by running `scripts/verify_integrity_v5.py` again.

## 4. Final Output
- Produce `docs/FINAL_COMPLETION_REPORT.md` confirming all resolved.
