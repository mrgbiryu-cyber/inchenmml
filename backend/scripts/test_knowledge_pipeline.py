import asyncio
import uuid
import sys
import os

# Add paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.master_agent_service import MasterAgentService
from app.core.database import init_db, get_messages_from_rdb
from app.services.knowledge_service import knowledge_worker, knowledge_queue
from app.core.neo4j_client import neo4j_client

async def test_dual_write_pipeline():
    print("Testing Dual-Write Pipeline (RDB -> Neo4j)...")
    
    # 1. Init DB
    await init_db()
    
    # 2. Start Knowledge Worker in background
    worker_task = asyncio.create_task(knowledge_worker())
    
    # 3. Simulate Master Agent processing a message
    svc = MasterAgentService()
    project_id = str(uuid.uuid4())
    thread_id = "test-thread-456"
    
    print("\n[Step 1] Master Agent processing message...")
    res = await svc.process_message(
        message="SEO_OPTIMIZER 에이전트를 추가하고, 모든 작업 후에는 결과를 blog_report.md로 저장하도록 규칙을 정했습니다.",
        history=[],
        project_id=project_id,
        thread_id=thread_id
    )
    # Avoid printing message that might have special chars
    print(f"Master Agent response received.")
    
    # 4. Wait for worker to process queue
    print("\n[Step 2] Waiting for knowledge extraction...")
    # Wait a bit for the worker to pick it up and complete
    await asyncio.sleep(10) 
    
    # 5. Verify RDB
    print("\n[Step 3] Verifying RDB Memory...")
    msgs = await get_messages_from_rdb(project_id, thread_id)
    print(f"Messages in RDB: {len(msgs)}")
    for m in msgs:
        print(f"- {m.sender_role}")

    # 6. Verify Neo4j
    print("\n[Step 4] Verifying Neo4j Cognition...")
    # Since we added SEO_OPTIMIZER, let's search for SEO
    knowledge = await neo4j_client.query_knowledge(project_id, "SEO")
    print(f"Nodes found in Neo4j: {len(knowledge)}")
    for k in knowledge:
        title = k.get('title') or k.get('name') or "Unnamed"
        print(f"- [{k['types']}] {title}")

    # Cleanup
    worker_task.cancel()
    print("\nTest Complete.")

if __name__ == "__main__":
    asyncio.run(test_dual_write_pipeline())
