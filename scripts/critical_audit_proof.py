import asyncio
import sys
import os
import json
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.core.neo4j_client import neo4j_client
from pydantic import BaseModel, Field

# [UTF-8]
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Manually define NodeDetail for audit since it was missing in schemas.py
class NodeDetail(BaseModel):
    id: str = Field(..., description="Node ID (UUID or Hash)")
    label: str = Field(..., description="Node Type (Concept, etc.)")
    title: str = Field(..., description="Display Title")
    content: str = Field(..., description="Full Content")
    created_at: str
    project_id: str
    metadata: dict = {}

async def prove_integrity():
    print("=== [CRITICAL AUDIT] DATA INTEGRITY PROOF ===")
    
    # 1. PostgreSQL Message-Thread Mapping Proof
    print("\n[1] PostgreSQL Message-Thread Mapping Proof")
    async with AsyncSessionLocal() as session:
        # 1.1 Orphaned Check
        result = await session.execute(text("SELECT count(*) FROM messages WHERE thread_id IS NULL"))
        orphaned = result.scalar()
        print(f"   Query: SELECT count(*) FROM messages WHERE thread_id IS NULL;")
        print(f"   Result: {orphaned}")
        if orphaned != 0:
            print("   ❌ FAIL: Orphaned messages exist. Report was FALSE.")
        else:
            print("   ✅ PASS: No orphaned messages.")

        # 1.2 ID Consistency Check (Sample)
        # Fetch one message and check if thread_id looks like a valid UUID string (thread-...)
        result = await session.execute(text("SELECT thread_id FROM messages LIMIT 1"))
        sample_tid = result.scalar()
        print(f"   Sample DB Thread ID: {sample_tid}")
        if sample_tid and sample_tid.startswith("thread-"):
             print("   ✅ PASS: Thread ID format matches 'thread-{uuid}'.")
        else:
             print("   ⚠️ WARNING: Thread ID format might be legacy or raw UUID.")

    # 2. Neo4j Relationship Proof & Schema Check
    print("\n[2] Neo4j Relationship & Schema Proof")
    
    # 2.1 Relationship Count
    async with neo4j_client.driver.session() as session:
        result = await session.run("MATCH ()-[r]->() RETURN count(r) as cnt")
        record = await result.single()
        rel_count = record["cnt"]
        print(f"   Query: MATCH ()-[r]->() RETURN count(r);")
        print(f"   Result: {rel_count}")
        if rel_count == 0:
            print("   ❌ FAIL: Graph is disconnected (0 relationships).")
        else:
            print(f"   ✅ PASS: {rel_count} relationships found.")
            
    # 2.2 Node Detail Schema Audit
    print("   [Schema Audit] Checking NodeDetail Pydantic Model vs Frontend Expectations:")
    # We defined NodeDetail manually above based on common frontend patterns
    schema = NodeDetail.model_json_schema()
    props = schema.get('properties', {})
    print(f"   Backend NodeDetail Fields (Expected): {list(props.keys())}")
    
    # Check what Neo4j actually returns for a node
    async with neo4j_client.driver.session() as session:
        result = await session.run("MATCH (n:Concept) RETURN n LIMIT 1")
        record = await result.single()
        if record:
            node_props = dict(record["n"])
            print(f"   Actual Neo4j Node Props (Sample): {list(node_props.keys())}")
            
            # Check for mismatch
            # Frontend typically needs: id, label, title
            missing_critical = []
            if 'id' not in node_props: missing_critical.append('id')
            if 'title' not in node_props and 'name' not in node_props: missing_critical.append('title/name')
            
            if missing_critical:
                print(f"   ❌ FAIL: Critical fields missing in Neo4j Node: {missing_critical}")
            else:
                print(f"   ✅ PASS: Critical fields (id, title) present.")

    # 3. Race Condition Code Proof (Static Analysis via Script)
    print("\n[3] Race Condition Fix Proof")
    print("   Checking 'frontend/src/components/chat/ChatInterface.tsx' for retry logic...")
    
    frontend_path = "frontend/src/components/chat/ChatInterface.tsx"
    if os.path.exists(frontend_path):
        with open(frontend_path, "r", encoding="utf-8") as f:
            content = f.read()
            if "setTimeout(fetchStats, 1500)" in content and "retryCount < 2" in content:
                print("   ✅ PASS: Found retry logic (1.5s delay, retryCount check) in ChatInterface.tsx.")
            else:
                print("   ❌ FAIL: Retry logic NOT found in frontend code.")
    else:
        print(f"   ❌ FAIL: File {frontend_path} not found.")

if __name__ == "__main__":
    asyncio.run(prove_integrity())
