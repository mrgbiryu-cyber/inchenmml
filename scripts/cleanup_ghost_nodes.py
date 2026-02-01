import asyncio
import sys
import os

# Adjust path
sys.path.append(os.getcwd())

from app.core.neo4j_client import neo4j_client

# [UTF-8]
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def cleanup_null_titles():
    print("🧹 Cleaning up Neo4j Ghost Nodes (Title=None)...")
    
    async with neo4j_client.driver.session() as session:
        # Check count first
        count_query = "MATCH (n) WHERE n.title IS NULL AND NOT n:Project RETURN count(n) as c"
        result = await session.run(count_query)
        record = await result.single()
        count = record["c"]
        
        print(f"   Found {count} nodes with NULL title.")
        
        if count > 0:
            # Delete
            del_query = "MATCH (n) WHERE n.title IS NULL AND NOT n:Project DETACH DELETE n"
            await session.run(del_query)
            print("   ✅ Deleted ghost nodes.")
        else:
            print("   ✨ No ghost nodes found.")

if __name__ == "__main__":
    asyncio.run(cleanup_null_titles())
