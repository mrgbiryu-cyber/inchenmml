import asyncio
import json
from app.core.neo4j_client import neo4j_client

async def check_project():
    project_id = "1ac0293c-3089-4ffd-9404-fb6e8cfbdb13"
    project = await neo4j_client.get_project(project_id)
    if not project:
        print(f"Project {project_id} not found")
        return
    
    print(f"Project Name: {project.get('name')}")
    print("Agent Config:")
    print(json.dumps(project.get('agent_config'), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(check_project())
