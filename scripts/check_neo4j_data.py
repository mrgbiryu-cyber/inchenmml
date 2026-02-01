import asyncio
import os
import sys
from neo4j import AsyncGraphDatabase

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import settings

async def check_knowledge():
    print(f"Checking Neo4j at {settings.NEO4J_URI}...")
    
    try:
        driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        
        async with driver.session() as session:
            # 1. Check for BUJA Project or Nodes
            print("\n=== Searching for 'BUJA' related nodes ===")
            query = """
            MATCH (n) 
            WHERE n.title CONTAINS 'BUJA' OR n.content CONTAINS 'BUJA' OR n.name CONTAINS 'BUJA'
            RETURN labels(n) as labels, n.title as title, n.name as name, n.content as content
            LIMIT 5
            """
            result = await session.run(query)
            records = [record async for record in result]
            
            if records:
                print(f"✅ Found {len(records)} nodes related to 'BUJA':")
                for r in records:
                    print(f" - [{r['labels'][0]}] {r['title'] or r['name']}")
            else:
                print("❌ No nodes found with keyword 'BUJA'.")

            # 2. Check recent nodes
            print("\n=== Checking 5 most recent nodes ===")
            query_recent = """
            MATCH (n)
            WHERE n.created_at IS NOT NULL
            RETURN labels(n) as labels, n.title as title, n.created_at as created_at
            ORDER BY n.created_at DESC
            LIMIT 5
            """
            result = await session.run(query_recent)
            records = [record async for record in result]
            for r in records:
                print(f" - [{r['labels'][0]}] {r['title']} (Created: {r['created_at']})")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_knowledge())
