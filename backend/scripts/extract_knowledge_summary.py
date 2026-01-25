import asyncio
import os
import sys
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.neo4j_client import neo4j_client

async def fetch_all_knowledge():
    query = """
    MATCH (n)
    WHERE labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
    RETURN labels(n) as labels, 
           n.id as id, 
           coalesce(n.title, n.name, n.summary, 'N/A') as title, 
           coalesce(n.content, n.description, n.summary, 'N/A') as content,
           n.project_id as project_id
    LIMIT 100
    """
    if not neo4j_client.driver:
        await neo4j_client.connect()
        
    async with neo4j_client.driver.session() as session:
        result = await session.run(query)
        data = []
        async for record in result:
            data.append({
                "labels": record["labels"],
                "id": record["id"],
                "title": record["title"],
                "content": record["content"][:200] + ("..." if record["content"] and len(record["content"]) > 200 else ""),
                "project_id": record["project_id"]
            })
        return data

async def main():
    data = await fetch_all_knowledge()
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
