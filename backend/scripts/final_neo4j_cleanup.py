import asyncio
from app.core.neo4j_client import neo4j_client

async def final_cleanup():
    if not await neo4j_client.verify_connectivity():
        print("Failed to connect to Neo4j")
        return

    async with neo4j_client.driver.session() as session:
        # 1. Find the index name for Project(id)
        # Neo4j 4.x/5.x syntax
        result = await session.run("SHOW INDEXES")
        index_name = None
        async for record in record_iter(result):
            # record['labelsOrTypes'], record['properties']
            labels = record.get('labelsOrTypes')
            props = record.get('properties')
            if labels and 'Project' in labels and props and 'id' in props:
                index_name = record['name']
                break
        
        if index_name:
            print(f"Found index: {index_name}. Dropping it...")
            await session.run(f"DROP INDEX {index_name}")
            print("Index dropped.")
        else:
            # Try pattern drop as fallback (older syntax or specific versions)
            try:
                await session.run("DROP INDEX ON :Project(id)")
                print("Index dropped using old syntax.")
            except:
                print("No index found to drop.")

        # 2. Create the constraint
        print("Creating uniqueness constraint...")
        await session.run("CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE")
        print("Constraint created successfully.")

async def record_iter(result):
    async for record in result:
        yield record

if __name__ == "__main__":
    asyncio.run(final_cleanup())
