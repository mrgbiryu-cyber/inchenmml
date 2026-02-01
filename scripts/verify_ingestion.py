import asyncio
import sys
import uuid
import json
from app.core.neo4j_client import neo4j_client
from app.core.database import AsyncSessionLocal, MessageModel, _normalize_project_id
from app.services.embedding_service import embedding_service
from app.core.vector_store import PineconeClient
from sqlalchemy import select

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

async def verify_knowledge_ingestion():
    print("🔍 Verifying Knowledge Ingestion...")

    # 1. Check Neo4j for nodes linked to recent messages
    print("\n[Neo4j Verification]")
    async with neo4j_client.driver.session() as session:
        # Get recent nodes created in the last hour
        query = """
        MATCH (n)
        WHERE n.created_at > datetime() - duration('PT1H')
        RETURN n.id, labels(n), n.title, n.source_message_id, n.project_id
        LIMIT 5
        """
        result = await session.run(query)
        nodes = [dict(record) async for record in result]
        
        if nodes:
            print(f"✅ Found {len(nodes)} recent nodes in Neo4j:")
            for n in nodes:
                print(f"  - Node ID: {n.get('n.id')}")
                print(f"    Labels: {n.get('labels(n)')}")
                print(f"    Title: {n.get('n.title')}")
                print(f"    Source Message ID: {n.get('n.source_message_id')}")
                print(f"    Project ID: {n.get('n.project_id')}")
        else:
            print("❌ No recent nodes found in Neo4j.")

    # 2. Check Vector DB (Pinecone) via client query
    print("\n[Vector DB Verification]")
    try:
        client = PineconeClient()
        # Create a dummy embedding to query
        dummy_embedding = await embedding_service.generate_embedding("test query")
        
        # Query for recent knowledge in system-master
        results = await client.query_vectors(
            tenant_id="system-master",
            vector=dummy_embedding,
            top_k=5,
            namespace="knowledge"
        )
        
        if results:
            print(f"✅ Found {len(results)} vectors in 'knowledge' namespace (system-master):")
            for res in results:
                meta = res.get("metadata", {})
                print(f"  - Vector ID: {res.get('id')}")
                print(f"    Score: {res.get('score')}")
                print(f"    Title: {meta.get('title')}")
                print(f"    Source Message ID: {meta.get('source_message_id')}")
                print(f"    Created At: {meta.get('created_at')}")
        else:
            print("❌ No vectors found in 'knowledge' namespace for system-master.")
            
    except Exception as e:
        print(f"❌ Vector DB Verification Failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(verify_knowledge_ingestion())
    except Exception as e:
        print(f"Error: {e}")
