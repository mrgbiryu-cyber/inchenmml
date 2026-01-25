import asyncio
import os
import sys

# Add current path to sys.path
sys.path.append(os.getcwd())

from app.core.neo4j_client import neo4j_client

async def check_projects():
    try:
        # We need to make sure neo4j is reachable
        # During dev, maybe it's localhost
        projects = await neo4j_client.list_projects('tenant_hyungnim')
        print(f"Found {len(projects)} projects.")
        for p in projects:
            print(f"ID: {p['id']}, Name: {p['name']}")
            if '블로그' in p['name'] or 'blog' in p['name'].lower():
                details = await neo4j_client.get_project(p['id'])
                print(f"\n--- Details for {p['name']} ---")
                import json
                print(json.dumps(details, indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await neo4j_client.close()

if __name__ == "__main__":
    asyncio.run(check_projects())
