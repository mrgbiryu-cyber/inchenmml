import asyncio
import os
import sys
import json
from neo4j import AsyncGraphDatabase

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.core.vector_store import PineconeClient

async def audit_system():
    print("=== 1. Neo4j Node Property Audit ===")
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI, 
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    
    async with driver.session() as session:
        # Fetch a few nodes to see their exact properties
        query = """
        MATCH (n)
        WHERE labels(n)[0] IN ['Concept', 'Requirement']
        RETURN n.id as id, n.name as name, n.title as title, n.content as content, n.text as text
        LIMIT 5
        """
        result = await session.run(query)
        records = [record async for record in result]
        
        for r in records:
            print(f"Node ID: {r['id']}")
            print(f"  - Name: {r['name']}")
            print(f"  - Title: {r['title']}")
            print(f"  - Content Preview: {str(r['content'])[:50] if r['content'] else 'None'}")
            print(f"  - Text Preview: {str(r['text'])[:50] if r['text'] else 'None'}")
            print("-" * 30)

    await driver.close()

    print("\n=== 2. Vector Search Audit ===")
    query_text = "지식 그래프 기능"
    print(f"Querying for: '{query_text}'")
    
    try:
        # Generate embedding
        vector = await embedding_service.generate_embedding(query_text)
        print(f"Generated embedding length: {len(vector)}")
        
        # Query Pinecone
        client = PineconeClient()
        # "conversation" namespace was used in the code, but knowledge is stored in "knowledge" namespace?
        # Let's check both or check where knowledge is stored.
        # knowledge_service.py uses namespace="knowledge"
        
        print("Searching namespace: 'knowledge'")
        results = await client.query_vectors(
            tenant_id="system-master",
            vector=vector,
            top_k=3,
            namespace="knowledge"
        )
        
        if results:
            for i, res in enumerate(results):
                meta = res.get("metadata", {})
                print(f"[{i+1}] Score: {res['score']:.4f}")
                print(f"    ID: {res['id']}")
                print(f"    Title: {meta.get('title')}")
                print(f"    Text: {meta.get('text', '')[:50]}...")
        else:
            print("No results found in 'knowledge' namespace.")
            
    except Exception as e:
        print(f"Vector search failed: {e}")

if __name__ == "__main__":
    asyncio.run(audit_system())
