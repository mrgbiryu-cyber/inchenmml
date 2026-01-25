# -*- coding: utf-8 -*-
import asyncio
import sys
import os
import uuid

# Ensure the backend directory is in the python path
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.core.database import AsyncSessionLocal, MessageModel
from app.core.neo4j_client import neo4j_client
from app.services.knowledge_service import knowledge_service

async def sync_all_databases():
    print("🚀 [전체 동기화 작전] 시작합니다...")
    
    # Neo4j 연결 확인
    try:
        if not await neo4j_client.verify_connectivity():
            print("❌ Neo4j 연결 실패: 서버가 응답하지 않습니다.")
            return
        print("✅ Neo4j 연결 확인")
    except Exception as e:
        print(f"❌ Neo4j 연결 실패: {e}")
        return

    async with AsyncSessionLocal() as session:
        # 1. Postgres에서 모든 메시지 가져오기 (시간순)
        print("📥 Postgres 메시지 로딩 중...")
        # Use MessageModel.timestamp as defined in database.py
        result = await session.execute(select(MessageModel).order_by(MessageModel.timestamp))
        messages = result.scalars().all()
        print(f"📊 총 {len(messages)}개의 메시지를 발견했습니다.")

        # 2. 데이터 재처리 및 동기화
        processed_count = 0
        for i, msg in enumerate(messages):
            project_id = str(msg.project_id or "system-master")
            
            # Use KnowledgeService internal logic for importance evaluation
            metadata = {"sender_role": msg.sender_role}
            importance, _ = knowledge_service._evaluate_importance(msg.content, metadata)
            
            # Execute pipeline for HIGH importance messages
            if importance == "HIGH":
                print(f"[{i+1}/{len(messages)}] 중요 지식 추출 중... (Project: {project_id}, Msg: {msg.message_id})")
                try:
                    # process_message_pipeline handles idempotency internally via CostLogModel
                    await knowledge_service.process_message_pipeline(msg.message_id)
                    processed_count += 1
                except Exception as e:
                    print(f"⚠️ 메시지 {msg.message_id} 처리 중 오류 발생: {e}")
            else:
                # Optional: Provide feedback for skipped messages
                if i % 10 == 0 or i == len(messages) - 1:
                    print(f"[{i+1}/{len(messages)}] 건너뛰는 중 (Importance: {importance})")

    print(f"\n🏁 [전체 동기화 작전] 완료! {processed_count}개의 중요 메시지가 처리되었습니다.")

if __name__ == "__main__":
    asyncio.run(sync_all_databases())
