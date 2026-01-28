# -*- coding: utf-8 -*-
"""
Test Script: Embedding & Vector DB Integration

테스트 목적:
1. 임베딩 서비스 동작 확인
2. Vector DB 저장/조회 확인
3. 의미 기반 검색 정확도 측정

실행 방법:
python backend/scripts/test_embedding_vector_integration.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.embedding_service import embedding_service
from app.core.vector_store import PineconeClient
from structlog import get_logger

logger = get_logger(__name__)


async def test_embedding_generation():
    """
    Test 1: 임베딩 생성
    """
    print("\n" + "="*60)
    print("Test 1: 임베딩 생성")
    print("="*60)
    
    test_texts = [
        "블로그 스케줄러 프로젝트",
        "매일 아침 9시에 포스트 발행",
        "PostgreSQL 데이터베이스 사용"
    ]
    
    for text in test_texts:
        try:
            embedding = await embedding_service.generate_embedding(text)
            print(f"✅ '{text[:30]}...'")
            print(f"   Vector dimension: {len(embedding)}")
            print(f"   Sample values: [{embedding[0]:.4f}, {embedding[1]:.4f}, ...]")
        except Exception as e:
            print(f"❌ '{text[:30]}...': {e}")
    
    print("\n✅ Test 1 완료!")


async def test_batch_embedding():
    """
    Test 2: 배치 임베딩
    """
    print("\n" + "="*60)
    print("Test 2: 배치 임베딩")
    print("="*60)
    
    test_texts = [
        "첫 번째 텍스트",
        "두 번째 텍스트",
        "세 번째 텍스트",
        "네 번째 텍스트",
        "다섯 번째 텍스트"
    ]
    
    try:
        embeddings = await embedding_service.generate_batch_embeddings(test_texts)
        print(f"✅ {len(embeddings)}개 임베딩 생성 완료")
        print(f"   Vector dimension: {len(embeddings[0]) if embeddings else 0}")
    except Exception as e:
        print(f"❌ 배치 임베딩 실패: {e}")
    
    print("\n✅ Test 2 완료!")


async def test_vector_db_operations():
    """
    Test 3: Vector DB 저장 & 조회
    """
    print("\n" + "="*60)
    print("Test 3: Vector DB 저장 & 조회")
    print("="*60)
    
    vector_client = PineconeClient()
    
    if not vector_client.index:
        print("⚠️ Pinecone 설정이 없습니다. 이 테스트를 건너뜁니다.")
        return
    
    # 테스트 데이터
    test_data = [
        {
            "text": "블로그 스케줄러 프로젝트",
            "metadata": {"type": "Concept", "project_id": "test-project"}
        },
        {
            "text": "매일 아침 9시에 포스트 자동 발행",
            "metadata": {"type": "Requirement", "project_id": "test-project"}
        },
        {
            "text": "PostgreSQL 데이터베이스와 JWT 인증 사용",
            "metadata": {"type": "Decision", "project_id": "test-project"}
        }
    ]
    
    # 1. 임베딩 생성 & 저장
    print("\n[1] 임베딩 저장...")
    vectors = []
    for i, data in enumerate(test_data):
        embedding = await embedding_service.generate_embedding(data["text"])
        vectors.append({
            "id": f"test-{i}",
            "values": embedding,
            "metadata": data["metadata"]
        })
    
    try:
        await vector_client.upsert_vectors(
            tenant_id="test-project",
            vectors=vectors,
            namespace="test"
        )
        print(f"✅ {len(vectors)}개 벡터 저장 완료")
    except Exception as e:
        print(f"❌ 벡터 저장 실패: {e}")
        return
    
    # 2. 의미 기반 검색
    print("\n[2] 의미 기반 검색...")
    queries = [
        "스케줄러는 몇 시에 동작하나요?",  # 2번과 유사
        "어떤 데이터베이스를 사용하나요?",  # 3번과 유사
    ]
    
    for query in queries:
        query_embedding = await embedding_service.generate_embedding(query)
        results = await vector_client.query_vectors(
            tenant_id="test-project",
            vector=query_embedding,
            top_k=2,
            namespace="test"
        )
        
        print(f"\n질문: {query}")
        for i, result in enumerate(results):
            print(f"  {i+1}. ID: {result['id']}, Score: {result['score']:.4f}")
            print(f"     Metadata: {result['metadata']}")
    
    print("\n✅ Test 3 완료!")


async def test_semantic_search_accuracy():
    """
    Test 4: 의미 기반 검색 정확도
    """
    print("\n" + "="*60)
    print("Test 4: 의미 기반 검색 정확도")
    print("="*60)
    
    # 유사도 측정
    test_pairs = [
        ("블로그 스케줄러", "자동 포스트 발행 시스템"),
        ("PostgreSQL 데이터베이스", "관계형 DB 시스템"),
        ("안녕하세요", "블로그 스케줄러"),  # 비유사
    ]
    
    print("\n코사인 유사도 측정:")
    for text1, text2 in test_pairs:
        emb1 = await embedding_service.generate_embedding(text1)
        emb2 = await embedding_service.generate_embedding(text2)
        
        # 코사인 유사도 계산
        import numpy as np
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        
        print(f"\n'{text1}' vs '{text2}'")
        print(f"  유사도: {similarity:.4f} {'✅' if similarity > 0.5 else '❌'}")
    
    print("\n✅ Test 4 완료!")


async def main():
    """
    메인 테스트 실행
    """
    print("\n" + "="*60)
    print("Embedding & Vector DB Integration Test")
    print("="*60)
    
    try:
        await test_embedding_generation()
        await test_batch_embedding()
        await test_vector_db_operations()
        await test_semantic_search_accuracy()
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 완료!")
        print("="*60)
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
