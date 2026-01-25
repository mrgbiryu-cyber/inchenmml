import asyncio
from app.core.neo4j_client import neo4j_client
from app.core.config import settings

async def check_projects():
    if not await neo4j_client.verify_connectivity():
        print("Failed to connect to Neo4j")
        return

    query = "MATCH (p:Project) RETURN elementId(p) as eid, p.id as id, p.name as name, p.tenant_id as tenant_id"
    async with neo4j_client.driver.session() as session:
        result = await session.run(query)
        print("Projects in Neo4j:")
        async for record in result:
            print(f"EID: {record['eid']}, ID: {record['id']}, Name: {record['name']}, Tenant: {record['tenant_id']}")

if __name__ == "__main__":
    asyncio.run(check_projects())
