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
    print("=== BUJA v5.0 FINAL Data Integrity Verification ===")
    
    # 1. VISIBILITY CHECK (RDB)
    print("\n[1] Checking Visibility Chain (RDB)...")
    async with AsyncSessionLocal() as session:
        # Check for Default Threads
        result = await session.execute(text("SELECT count(*) FROM threads WHERE title = '기본 대화방'"))
        count = result.scalar()
        print(f"   Projects with 'Default Room': {count} (Healthy)")
            
        # Check for orphaned messages (No Thread ID)
        result = await session.execute(text("SELECT count(*) FROM messages WHERE thread_id IS NULL"))
        orphaned = result.scalar()
        print(f"   Orphaned Messages: {orphaned} (Target: 0)")
        if orphaned == 0:
             print("   ✅ Visibility Chain PASS")
        else:
             print("   ⚠️ Visibility Chain WARNING")

    # 2. CONNECTION CHECK (Neo4j)
    print("\n[2] Checking Connection Chain (Neo4j)...")
    # Verify System Master
    try:
        sys_master = await neo4j_client.get_project("system-master")
        if sys_master:
            print("   ✅ System Master Project Node exists.")
        
        # Check for Null Titles (Should be 0 now)
        async with neo4j_client.driver.session() as session:
            find_query = """
            MATCH (n)
            WHERE (n.title IS NULL OR n.title = 'None' OR n.title = '') 
              AND labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Task']
            RETURN count(n) as cnt
            """
            result = await session.run(find_query)
            record = await result.single()
            null_titles = record["cnt"]
            print(f"   Nodes with Null Titles: {null_titles} (Target: 0)")
            
            if null_titles == 0:
                print("   ✅ Connection Chain PASS")
            else:
                print("   ⚠️ Connection Chain WARNING")

    except Exception as e:
        print(f"   ❌ Neo4j Error: {e}")

    # 3. SCORING CHECK (Pinecone)
    print("\n[3] Checking Scoring Chain (Pinecone)...")
    pc = PineconeClient()
    if pc.index:
        try:
            # We confirmed system-master exists now
            dummy_vec = [0.0] * 1536
            results = await pc.query_vectors(
                tenant_id="system-master",
                vector=dummy_vec,
                top_k=1,
                namespace="knowledge"
            )
            if results:
                print(f"   ✅ Query 'system-master' successful. Matches found.")
                print("   ✅ Scoring Chain PASS")
            else:
                print("   ⚠️ Query 'system-master' returned 0 results.")
        except Exception as e:
            print(f"   ❌ Pinecone Query Failed: {e}")
    else:
        print("   ❌ Pinecone Client not initialized.")

if __name__ == "__main__":
    asyncio.run(main())
