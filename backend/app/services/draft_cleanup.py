# -*- coding: utf-8 -*-
"""
Draft Cleanup Service - v3.2
만료된 Draft 자동 정리 (TTL 기반)
"""
import asyncio
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)

async def cleanup_expired_drafts_task():
    """
    백그라운드 작업: 만료된 Draft 삭제
    - 1시간마다 실행
    - TTL 기간 (기본 7일) 초과한 UNVERIFIED Draft 삭제
    """
    from app.core.database import delete_expired_drafts
    
    while True:
        try:
            logger.info("🧹 Draft 정리 작업 시작...")
            deleted_count = await delete_expired_drafts(days=7)
            logger.info(f"✅ Draft 정리 완료: {deleted_count}개 삭제")
        except Exception as e:
            logger.error(f"❌ Draft 정리 실패: {e}")
        
        # 1시간 대기
        await asyncio.sleep(3600)

async def purge_project_drafts(project_id: str):
    """
    프로젝트 완료/취소 시 관련 Draft 정리
    """
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import Table, MetaData, update
    
    try:
        metadata = MetaData()
        from app.core.database import AsyncEngine
        drafts_table = Table('drafts', metadata, autoload_with=AsyncEngine)
        
        async with AsyncSessionLocal() as session:
            stmt = update(drafts_table).where(
                drafts_table.c.project_id == project_id
            ).values(status='EXPIRED')
            
            result = await session.execute(stmt)
            await session.commit()
            logger.info(f"✅ 프로젝트 {project_id} Draft purge 완료: {result.rowcount}개")
            return result.rowcount
    except Exception as e:
        logger.error(f"❌ Draft purge 실패: {e}")
        return 0
