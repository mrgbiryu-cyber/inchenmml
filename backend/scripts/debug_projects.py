import asyncio
from app.core.neo4j_client import neo4j_client

async def check():
    projects = await neo4j_client.list_projects('tenant_hyungnim')
    print("--- PROJECTS ---")
    for p in projects:
        print(f"ID: {p['id']}, Name: {p['name']}")
    print("----------------")

if __name__ == "__main__":
    asyncio.run(check())
