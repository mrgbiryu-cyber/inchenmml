import asyncio
import os
import sys
import json
from neo4j import AsyncGraphDatabase

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import settings
from app.core.neo4j_client import neo4j_client

async def debug_endpoints():
    print("=== Debugging Knowledge Graph Data ===")
    
    # 1. Simulate get_knowledge_graph logic
    project_id = "system-master" 
    print(f"Fetching graph for: {project_id}")
    
    try:
        graph = await neo4j_client.get_knowledge_graph(project_id)
        
        print(f"Nodes found: {len(graph['nodes'])}")
        if graph['nodes']:
            print("--- First 5 Nodes ---")
            for node in graph['nodes'][:5]:
                print(json.dumps(node, ensure_ascii=False, indent=2))
        else:
            print("No nodes found.")
            
    except Exception as e:
        print(f"Error fetching graph: {e}")

if __name__ == "__main__":
    asyncio.run(debug_endpoints())
