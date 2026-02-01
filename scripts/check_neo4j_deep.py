import asyncio
import os
import sys
from neo4j import AsyncGraphDatabase
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import settings

async def check_knowledge_deep():
    print(f"Checking Neo4j at {settings.NEO4J_URI}...")
    
    try:
        driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        
        async with driver.session() as session:
            # 1. Check all nodes in the system-master project (assuming that's where we are)
            # Or just check all nodes with relevant labels
            print("\n=== Sampling Nodes (Concept/Requirement/Fact) ===")
            query = """
            MATCH (n) 
            WHERE labels(n)[0] IN ['Concept', 'Requirement', 'Fact']
            RETURN labels(n) as labels, n.id as id, n.title as title, n.name as name, n.project_id as project_id
            LIMIT 10
            """
            result = await session.run(query)
            records = [record async for record in result]
            
            if records:
                for r in records:
                    lbl = r['labels'][0] if r['labels'] else 'NoLabel'
                    title = r['title'] or r['name'] or "NO_TITLE"
                    nid = r['id']
                    pid = r['project_id']
                    print(f"[{lbl}] ID: {nid} | Title: {title} | PID: {pid}")
            else:
                print("❌ No relevant nodes found.")

            # 2. Check Relationships
            print("\n=== Sampling Relationships ===")
            query_rels = """
            MATCH (n)-[r]->(m)
            WHERE labels(n)[0] IN ['Concept', 'Requirement', 'Fact']
            RETURN labels(n)[0] as source_type, n.title as source_title, type(r) as rel_type, labels(m)[0] as target_type, m.title as target_title
            LIMIT 10
            """
            result = await session.run(query_rels)
            records = [record async for record in result]
            
            if records:
                for r in records:
                    print(f"{r['source_type']}({r['source_title']}) -[{r['rel_type']}]-> {r['target_type']}({r['target_title']})")
            else:
                print("❌ No relationships found between relevant nodes.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_knowledge_deep())
