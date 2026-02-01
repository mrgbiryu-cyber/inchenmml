import asyncio
import sys
import os
import uuid
from datetime import datetime

# Adjust path
sys.path.append(os.getcwd())

from app.core.database import AsyncSessionLocal, MessageModel, ThreadModel
from app.core.neo4j_client import neo4j_client
from app.core.vector_store import PineconeClient
from app.services.embedding_service import embedding_service
from sqlalchemy import select, text

# [UTF-8]
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    print("=== BUJA v5.0 Data Integrity Verification ===")
    
    # 1. VISIBILITY CHECK (RDB)
    print("\n[1] Checking Visibility Chain (RDB)...")
    async with AsyncSessionLocal() as session:
        # Check for Default Threads
        result = await session.execute(text("SELECT project_id, count(*) FROM threads WHERE title = '기본 대화방' GROUP BY project_id"))
        default_threads = result.fetchall()
        print(f"   Projects with 'Default Room': {len(default_threads)}")
        for dt in default_threads:
            print(f"   - Project: {dt[0]} (Count: {dt[1]})")
            
        # Check for orphaned messages (No Thread ID)
        result = await session.execute(text("SELECT count(*) FROM messages WHERE thread_id IS NULL"))
        orphaned = result.scalar()
        print(f"   Orphaned Messages (No Thread ID): {orphaned}")
        if orphaned > 0:
            print("   ⚠️ WARNING: Orphaned messages detected. Run migration script.")

    # 2. CONNECTION CHECK (Neo4j)
    print("\n[2] Checking Connection Chain (Neo4j)...")
    # Verify System Master
    try:
        sys_master = await neo4j_client.get_project("system-master")
        if sys_master:
            print("   ✅ System Master Project Node exists.")
        else:
            print("   ❌ System Master Project Node MISSING.")
    except Exception as e:
        print(f"   ❌ Neo4j Error: {e}")

    # Check for Cartesian Product Warning Signals (Indirectly)
    # We can't check query logs easily here, but we can check if we have duplicate nodes
    async with neo4j_client.driver.session() as session:
        query = """
        MATCH (n:Concept)
        WITH n.title as title, count(*) as c
        WHERE c > 1
        RETURN title, c
        LIMIT 5
        """
        result = await session.run(query)
        dupes = [dict(record) async for record in result]
        if dupes:
            print(f"   ⚠️ Potential Duplicates in Knowledge Graph: {len(dupes)} found.")
            for d in dupes:
                print(f"   - {d['title']}: {d['c']} copies")
        else:
            print("   ✅ No obvious title-based duplicates found in first check.")

    # 3. SCORING CHECK (Pinecone)
    print("\n[3] Checking Scoring Chain (Pinecone)...")
    pc = PineconeClient()
    if pc.index:
        print(f"   Connected to Index: {pc.index_name}")
        # Try a dummy query to check filter logic
        try:
            # We assume 'system-master' exists
            dummy_vec = [0.0] * 1536
            results = await pc.query_vectors(
                tenant_id="system-master",
                vector=dummy_vec,
                top_k=1,
                namespace="knowledge"
            )
            if results:
                print(f"   ✅ Query successful. Found {len(results)} matches.")
                meta = results[0]['metadata']
                print(f"   - Sample Metadata Tenant/Project ID: {meta.get('tenant_id')} / {meta.get('project_id')}")
            else:
                print("   ⚠️ Query returned no results (Index might be empty or filter mismatch).")
        except Exception as e:
            print(f"   ❌ Pinecone Query Failed: {e}")
    else:
        print("   ❌ Pinecone Client not initialized (Check API Key).")

if __name__ == "__main__":
    asyncio.run(main())
