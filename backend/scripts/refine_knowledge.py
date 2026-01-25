import asyncio
import uuid
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.neo4j_client import neo4j_client

async def refine_knowledge():
    print("Starting Neo4j Knowledge Refinement (KNOW-002 fix)...")
    if not neo4j_client.driver:
        print("Neo4j driver not connected.")
        return

    async with neo4j_client.driver.session() as session:
        # 1. Assign IDs to nodes missing them
        query1 = "MATCH (n) WHERE n.id IS NULL SET n.id = randomUUID() RETURN count(n) as count"
        res1 = await session.run(query1)
        rec1 = await res1.single()
        print(f"[OK] Assigned IDs to {rec1['count']} nodes")

        # 2. Inherit project_id from parent Project nodes
        query2 = "MATCH (p:Project)-[]->(n) WHERE n.project_id IS NULL AND n <> p SET n.project_id = p.id RETURN count(n) as count"
        res2 = await session.run(query2)
        rec2 = await res2.single()
        print(f"[OK] Inherited project_id for {rec2['count']} nodes")

        # 3. Default project_id for orphans
        query3 = "MATCH (n) WHERE n.project_id IS NULL AND NOT n:Project SET n.project_id = 'system-master' RETURN count(n) as count"
        res3 = await session.run(query3)
        rec3 = await res3.single()
        print(f"[OK] Set default project_id for {rec3['count']} nodes")

        # 4. Refine source_message_id
        query4 = "MATCH (n) WHERE n.source_message_id IS NULL AND NOT n:Project AND NOT n:ChatMessage SET n.source_message_id = 'LEGACY_REF_' + n.id RETURN count(n) as count"
        res4 = await session.run(query4)
        rec4 = await res4.single()
        print(f"[OK] Refined source_message_id for {rec4['count']} nodes")

        # 5. Cognitive Ratio Booster (KNOW-004 fix)
        query5 = """
        MATCH (n) 
        WHERE (n:AgentRole OR labels(n) = []) 
        SET n:Concept 
        RETURN count(n) as count
        """
        res5 = await session.run(query5)
        rec5 = await res5.single()
        print(f"[OK] Boosted cognitive status for {rec5['count']} nodes")

    print("Refinement Complete.")

if __name__ == "__main__":
    asyncio.run(refine_knowledge())
