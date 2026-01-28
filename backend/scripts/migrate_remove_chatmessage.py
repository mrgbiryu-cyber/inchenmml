# -*- coding: utf-8 -*-
"""
Migration Script: Remove ChatMessage nodes from Neo4j

목적:
- Neo4j에 중복 저장되어 있는 ChatMessage 노드 제거
- RDB (PostgreSQL)가 Single Source of Truth이므로 Neo4j에는 불필요

실행 방법:
python backend/scripts/migrate_remove_chatmessage.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.neo4j_client import neo4j_client
from structlog import get_logger

logger = get_logger(__name__)


async def migrate():
    """
    Neo4j에서 ChatMessage 노드 제거
    """
    logger.info("Starting ChatMessage removal migration")
    
    if not neo4j_client.driver:
        logger.error("Neo4j driver not initialized")
        return
    
    async with neo4j_client.driver.session() as session:
        # 1. ChatMessage 노드 개수 확인
        count_query = "MATCH (m:ChatMessage) RETURN count(m) as count"
        count_result = await session.run(count_query)
        count_record = await count_result.single()
        count = count_record["count"] if count_record else 0
        
        logger.info(f"Found {count} ChatMessage nodes to remove")
        
        if count == 0:
            logger.info("No ChatMessage nodes found, migration complete")
            return
        
        # 2. HAS_MESSAGE 관계 제거
        logger.info("Removing HAS_MESSAGE relationships...")
        rel_query = """
            MATCH ()-[r:HAS_MESSAGE]->()
            DELETE r
            RETURN count(r) as deleted_count
        """
        rel_result = await session.run(rel_query)
        rel_record = await rel_result.single()
        rel_deleted = rel_record["deleted_count"] if rel_record else 0
        
        logger.info(f"Deleted {rel_deleted} HAS_MESSAGE relationships")
        
        # 3. ChatMessage 노드 제거
        logger.info("Removing ChatMessage nodes...")
        node_query = """
            MATCH (m:ChatMessage)
            DELETE m
            RETURN count(m) as deleted_count
        """
        node_result = await session.run(node_query)
        node_record = await node_result.single()
        node_deleted = node_record["deleted_count"] if node_record else 0
        
        logger.info(f"Deleted {node_deleted} ChatMessage nodes")
        
        # 4. 확인
        verify_query = "MATCH (m:ChatMessage) RETURN count(m) as count"
        verify_result = await session.run(verify_query)
        verify_record = await verify_result.single()
        remaining = verify_record["count"] if verify_record else 0
        
        if remaining == 0:
            logger.info("✅ Migration completed successfully")
        else:
            logger.warning(f"⚠️ {remaining} ChatMessage nodes still remaining")


async def main():
    try:
        await migrate()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
