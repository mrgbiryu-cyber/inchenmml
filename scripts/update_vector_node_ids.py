"""
[v5.0] Vector DB에 node_id 메타데이터 추가 스크립트

기존 Vector DB 데이터에 node_id를 추가합니다.
Neo4j에서 각 노드의 ID를 가져와 Vector DB 메타데이터를 업데이트합니다.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.vector_store import PineconeClient
from app.core.neo4j_client import Neo4jClient


async def update_vector_node_ids():
    """Vector DB의 모든 벡터에 node_id 추가"""
    
    print("🚀 Starting Vector DB node_id update...")
    
    vector_client = PineconeClient()
    neo4j_client = Neo4jClient()
    
    try:
        # 1. Neo4j에서 모든 knowledge 노드 가져오기
        print("\n📊 Fetching knowledge nodes from Neo4j...")
        
        query = """
        MATCH (n)
        WHERE labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
        RETURN n.id as node_id, n.title as title, n.project_id as project_id
        """
        
        async with neo4j_client.driver.session() as session:
            result = await session.run(query)
            nodes = []
            async for record in result:
                nodes.append({
                    "node_id": record["node_id"],
                    "title": record["title"],
                    "project_id": record["project_id"]
                })
        
        print(f"✅ Found {len(nodes)} knowledge nodes in Neo4j")
        
        # 2. Pinecone에서 각 노드의 벡터를 찾아 업데이트
        print("\n🔄 Updating Vector DB metadata...")
        
        updated_count = 0
        not_found_count = 0
        
        for node in nodes:
            node_id = node["node_id"]
            project_id = node["project_id"]
            
            if not node_id or not project_id:
                continue
            
            # Pinecone에서 해당 ID의 벡터 조회
            try:
                # Fetch vector by ID
                fetch_result = vector_client.index.fetch(
                    ids=[node_id],
                    namespace="knowledge"
                )
                
                if node_id in fetch_result.vectors:
                    # 기존 메타데이터 가져오기
                    existing_vector = fetch_result.vectors[node_id]
                    metadata = existing_vector.metadata or {}
                    
                    # node_id 추가
                    metadata["node_id"] = node_id
                    
                    # 업데이트
                    vector_client.index.upsert(
                        vectors=[{
                            "id": node_id,
                            "values": existing_vector.values,
                            "metadata": metadata
                        }],
                        namespace="knowledge"
                    )
                    
                    updated_count += 1
                    
                    if updated_count % 10 == 0:
                        print(f"   Progress: {updated_count}/{len(nodes)} vectors updated")
                else:
                    not_found_count += 1
                    
            except Exception as e:
                print(f"⚠️  Failed to update {node_id}: {e}")
                continue
        
        print(f"\n✅ Update complete!")
        print(f"   - Updated: {updated_count} vectors")
        print(f"   - Not found in Vector DB: {not_found_count} nodes")
        
        # 주요 발견: Vector DB에 없는 노드가 많음
        if not_found_count > updated_count:
            print(f"\n💡 Tip: Most nodes are not in Vector DB yet.")
            print(f"   This is normal if they were created before embeddings were generated.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # [FIX] Neo4jClient uses driver.close(), not close()
        await neo4j_client.driver.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Vector DB node_id Update Script")
    print("=" * 60)
    print("\n⚠️  WARNING: This will update all vectors in the knowledge namespace")
    print("Press Ctrl+C to cancel, or wait 5 seconds to continue...\n")
    
    try:
        import time
        time.sleep(5)
        asyncio.run(update_vector_node_ids())
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        sys.exit(1)
