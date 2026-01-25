import asyncio
from app.core.neo4j_client import neo4j_client

async def cleanup_duplicates():
    if not await neo4j_client.verify_connectivity():
        print("Failed to connect to Neo4j")
        return

    # 1. Create uniqueness constraint if not exists
    # Neo4j 4.4+ syntax
    constraint_query = "CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE"
    
    # 2. Delete duplicates keeping only one
    # This query finds duplicate projects and deletes all but the one with the lowest internal ID
    cleanup_query = """
    MATCH (p:Project)
    WITH p.id as id, collect(p) as nodes
    WHERE size(nodes) > 1
    FOREACH (n in tail(nodes) | DETACH DELETE n)
    """

    async with neo4j_client.driver.session() as session:
        print("Cleaning up duplicate projects...")
        await session.run(cleanup_query)
        print("Duplicate cleanup complete.")
        
        try:
            print("Creating uniqueness constraint...")
            await session.run(constraint_query)
            print("Constraint created.")
        except Exception as e:
            print(f"Warning: Could not create constraint: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
