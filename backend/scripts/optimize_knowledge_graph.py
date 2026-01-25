import asyncio
import os
import sys
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.neo4j_client import neo4j_client

async def clean_and_link_knowledge():
    if not neo4j_client.driver:
        await neo4j_client.connect()
        
    async with neo4j_client.driver.session() as session:
        print("1. 내용 없는 유령 노드 삭제 중...")
        # title, name, content, description이 모두 없거나 'N/A'인 노드 삭제
        delete_ghosts_query = """
        MATCH (n)
        WHERE labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
        AND (
            (n.title IS NULL OR n.title = 'N/A') AND 
            (n.name IS NULL OR n.name = 'N/A') AND 
            (n.content IS NULL OR n.content = 'N/A') AND 
            (n.description IS NULL OR n.description = 'N/A') AND
            (n.summary IS NULL OR n.summary = 'N/A')
        )
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """
        res = await session.run(delete_ghosts_query)
        ghost_count = await res.single()
        print(f"   => {ghost_count['deleted_count']}개의 유령 노드 삭제 완료.")

        print("2. 중복 개념 통합 중 (동일 제목 기준)...")
        # 동일한 project_id 내에서 동일한 title을 가진 노드 통합
        merge_duplicates_query = """
        MATCH (n)
        WHERE labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
        WITH n.project_id as pid, coalesce(n.title, n.name) as title, collect(n) as nodes
        WHERE size(nodes) > 1
        CALL apoc.refactor.mergeNodes(nodes, {properties: 'combine', mergeRels: true})
        YIELD node
        RETURN count(node) as merged_count
        """
        # APOC가 없을 수 있으므로 수동 통합 로직 (간소화)
        try:
            res = await session.run(merge_duplicates_query)
            merge_count = await res.single()
            print(f"   => {merge_count['merged_count']}개 그룹의 중복 노드 통합 완료.")
        except Exception as e:
            print(f"   => APOC 미설치로 자동 통합 건너뜀 (수동 로직 필요 시 추후 보완): {str(e)}")

        print("3. 모든 지식 노드를 Project와 연결 (HAS_KNOWLEDGE)...")
        link_project_query = """
        MATCH (n)
        WHERE labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
        AND n.project_id IS NOT NULL
        MATCH (p:Project {id: n.project_id})
        MERGE (p)-[:HAS_KNOWLEDGE]->(n)
        RETURN count(*) as linked_count
        """
        res = await session.run(link_project_query)
        link_count = await res.single()
        print(f"   => {link_count['linked_count']}개의 노드를 프로젝트와 연결 완료.")

        print("4. 근거 메시지 연결 확인 및 복구 (BASED_ON)...")
        # source_message_id가 있는 경우 Message 노드와 연결
        link_message_query = """
        MATCH (n)
        WHERE labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Logic', 'Fact', 'Task', 'File', 'History']
        AND n.source_message_id IS NOT NULL
        MERGE (m:Message {id: n.source_message_id})
        MERGE (n)-[:BASED_ON]->(m)
        RETURN count(*) as based_on_count
        """
        res = await session.run(link_message_query)
        based_on_count = await res.single()
        print(f"   => {based_on_count['based_on_count']}개의 노드에 근거 메시지(BASED_ON) 연결 완료.")

async def main():
    await clean_and_link_knowledge()
    print("\n지식 그래프 최적화 작업이 모두 완료되었습니다.")

if __name__ == "__main__":
    asyncio.run(main())
