#!/usr/bin/env python3
"""Check agents for a specific project in Neo4j"""
import asyncio
import sys
sys.path.insert(0, '/d/project/myllm/backend')

from app.core.neo4j_client import neo4j_client

async def main():
    project_id = "1ac0293c-3089-4ffd-9404-fb6e8cfbdb13"
    
    print(f"\n=== Checking agents for project: {project_id} ===\n")
    
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        print(f"❌ Project {project_id} not found in Neo4j!")
        return
    
    print(f"✅ Project found: {project_data.get('name')}")
    print(f"   Path: {project_data.get('repo_path')}")
    print(f"   Workflow: {project_data.get('workflow_type')}")
    print(f"   Entry: {project_data.get('entry_agent_id')}\n")
    
    config = project_data.get('agent_config', {})
    agents = config.get('agents', [])
    
    print(f"=== Registered Agents ({len(agents)}) ===\n")
    for i, agent in enumerate(agents, 1):
        print(f"{i}. Agent ID: {agent.get('agent_id')}")
        print(f"   Role: {agent.get('role')}")
        print(f"   Type: {agent.get('type', 'CUSTOM')}")
        print(f"   Model: {agent.get('model')}")
        print(f"   Provider: {agent.get('provider')}")
        print(f"   Config: {agent.get('config', {})}")
        print(f"   Next Agents: {agent.get('next_agents', [])}")
        print()
    
    await neo4j_client.close()

if __name__ == "__main__":
    asyncio.run(main())
