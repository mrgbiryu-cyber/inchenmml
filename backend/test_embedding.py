#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
임베딩 모델 테스트 스크립트
"""
import asyncio
from openai import AsyncOpenAI
from app.core.config import settings

async def test_embedding():
    """OpenRouter 임베딩 API 테스트"""
    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    test_models = [
        "openai/text-embedding-3-small",
        "openai/text-embedding-3-large",
        # "qwen/qwen3-embedding-0.6b",  # 지원 중단됨
    ]
    
    for model in test_models:
        try:
            print(f"\n[테스트] 모델: {model}")
            response = await client.embeddings.create(
                model=model,
                input="안녕하세요. 임베딩 테스트입니다."
            )
            dimension = len(response.data[0].embedding)
            print(f"✅ 성공! 차원: {dimension}")
        except Exception as e:
            print(f"❌ 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_embedding())
