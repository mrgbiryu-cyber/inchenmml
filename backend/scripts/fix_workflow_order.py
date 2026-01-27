#!/usr/bin/env python3
"""Fix workflow order for project"""
import asyncio
import sys
sys.path.insert(0, 'D:/project/myllm/backend')

from app.core.neo4j_client import neo4j_client
from app.models.schemas import Project

async def main():
    project_id = "1ac0293c-3089-4ffd-9404-fb6e8cfbdb13"
    
    print(f"\n=== Fixing workflow for project: {project_id} ===\n")
    
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        print(f"❌ Project not found!")
        return
    
    config = project_data.get('agent_config', {})
    agents = config.get('agents', [])
    
    # 표준 순서로 재설정
    print("🔧 Setting standard workflow: PLANNER → DEVELOPER → QA_ENGINEER → REPORTER → 완료\n")
    
    for agent in agents:
        role = agent.get('role')
        if role == 'PLANNER':
            agent['next_agents'] = ['DEVELOPER']
            print(f"✅ PLANNER → DEVELOPER")
        elif role == 'DEVELOPER':
            agent['next_agents'] = ['QA_ENGINEER']
            print(f"✅ DEVELOPER → QA_ENGINEER")
        elif role == 'QA_ENGINEER':
            agent['next_agents'] = ['REPORTER']
            print(f"✅ QA_ENGINEER → REPORTER")
        elif role == 'REPORTER':
            agent['next_agents'] = []
            print(f"✅ REPORTER → 완료")
    
    config['workflow_type'] = 'SEQUENTIAL'
    config['entry_agent_id'] = 'PLANNER'
    project_data['agent_config'] = config
    
    # Neo4j 업데이트
    await neo4j_client.create_project_graph(Project(**project_data))
    
    print("\n✅ 워크플로우 수정 완료!\n")
    
    # 확인
    updated_data = await neo4j_client.get_project(project_id)
    config = updated_data.get('agent_config', {})
    agents = config.get('agents', [])
    
    print("=== Updated Workflow ===\n")
    for agent in agents:
        role = agent.get('role')
        next_agents = agent.get('next_agents', [])
        next_str = " → ".join(next_agents) if next_agents else "완료"
        print(f"{role} → {next_str}")

if __name__ == "__main__":
    asyncio.run(main())
