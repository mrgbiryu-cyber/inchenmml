# -*- coding: utf-8 -*-
"""
Embedding Service - OpenRouter Integration
임베딩 생성 서비스 (OpenRouter API 사용)
"""
from typing import List, Dict, Any
from openai import AsyncOpenAI
from app.core.config import settings
from structlog import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    OpenRouter를 통한 임베딩 생성 서비스
    
    지원 모델:
    - openai/text-embedding-3-small (권장: 저렴하고 빠름)
    - openai/text-embedding-3-large (최고 성능)
    - qwen/qwen3-embedding-0.6b (한국어 우수)
    - jina/jina-embeddings-v4 (멀티모달)
    """
    
    def __init__(self):
        """
        OpenRouter API 클라이언트 초기화
        """
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not set in environment variables")
        
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # 모델 선택 (한국어 프로젝트에 최적)
        # text-embedding-3-small: 검증된 성능 + 저렴
        # text-embedding-3-large: 최고 성능
        self.model = "openai/text-embedding-3-small"  # 안정적이고 저렴함
        
        logger.info(
            "EmbeddingService initialized",
            provider="OpenRouter",
            model=self.model
        )
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        단일 텍스트를 임베딩 벡터로 변환
        
        Args:
            text: 임베딩할 텍스트
        
        Returns:
            임베딩 벡터 (List[float])
        
        Raises:
            Exception: API 호출 실패 시
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return []
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text.strip()
            )
            
            embedding = response.data[0].embedding
            
            logger.debug(
                "Embedding generated",
                text_length=len(text),
                vector_dim=len(embedding)
            )
            
            return embedding
            
        except Exception as e:
            logger.error(
                "Embedding generation failed",
                error=str(e),
                text_preview=text[:100]
            )
            raise
    
    async def generate_batch_embeddings(
        self, 
        texts: List[str], 
        batch_size: int = 20
    ) -> List[List[float]]:
        """
        여러 텍스트를 배치로 임베딩 (비용 절약)
        
        Args:
            texts: 임베딩할 텍스트 리스트
            batch_size: 한 번에 처리할 텍스트 개수 (OpenRouter 제한 고려)
        
        Returns:
            임베딩 벡터 리스트
        """
        if not texts:
            return []
        
        # 빈 텍스트 필터링
        texts = [t.strip() for t in texts if t and t.strip()]
        
        if not texts:
            return []
        
        all_embeddings = []
        
        # 배치 단위로 처리
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)
                
                logger.debug(
                    "Batch embeddings generated",
                    batch_start=i,
                    batch_size=len(batch),
                    total_processed=len(all_embeddings)
                )
                
            except Exception as e:
                logger.error(
                    "Batch embedding failed",
                    error=str(e),
                    batch_start=i,
                    batch_size=len(batch)
                )
                # 실패한 배치는 빈 벡터로 채움 (또는 개별 재시도)
                all_embeddings.extend([[] for _ in batch])
        
        return all_embeddings
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        현재 사용 중인 모델 정보 반환
        """
        return {
            "provider": "OpenRouter",
            "model": self.model,
            "base_url": "https://openrouter.ai/api/v1",
            "supports_batch": True,
            "max_batch_size": 20
        }


# 싱글톤 인스턴스
embedding_service = EmbeddingService()
