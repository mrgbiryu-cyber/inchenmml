import asyncio
import sys
import os
import json
from datetime import datetime

# Adjust path to import app modules
sys.path.append(os.getcwd())

from app.core.neo4j_client import neo4j_client
from app.services.knowledge_service import knowledge_service
from app.core.database import AsyncSessionLocal, MessageModel
from sqlalchemy import select, desc

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

async def check_ingestion_status():
    print("🔍 Checking Knowledge Ingestion Status...")
    
    # 1. Get recent message that triggered ingestion
    # From logs: message_id=dc5a6568-0f28-49f5-820e-9e25f1719a0c
    target_msg_id = "dc5a6568-0f28-49f5-820e-9e25f1719a0c"
    
    print(f"\n[Message Trace] Checking Message ID: {target_msg_id}")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MessageModel).where(MessageModel.message_id == target_msg_id))
        msg = result.scalar_one_or_none()
        if msg:
            print(f"✅ Message found in RDB.")
            print(f"   Content Preview: {msg.content[:50]}...")
            print(f"   Project ID: {msg.project_id}")
        else:
            print(f"❌ Message NOT found in RDB (Check UUID vs String format).")
            # Try fetching latest message
            print("   Fetching latest message instead...")
            result = await session.execute(select(MessageModel).order_by(desc(MessageModel.timestamp)).limit(1))
            msg = result.scalar_one_or_none()
            if msg:
                print(f"   Latest Message ID: {msg.message_id}")
                target_msg_id = str(msg.message_id)

    # 2. Check Neo4j for nodes linked to this message
    print(f"\n[Neo4j Verification] Source Message ID: {target_msg_id}")
    async with neo4j_client.driver.session() as session:
        query = """
        MATCH (n)
        WHERE n.source_message_id = $msg_id
        RETURN n.id, labels(n), n.title
        """
        result = await session.run(query, {"msg_id": target_msg_id})
        nodes = [dict(record) async for record in result]
        
        if nodes:
            print(f"✅ Found {len(nodes)} nodes in Neo4j linked to this message:")
            for n in nodes:
                print(f"  - [{n.get('labels(n)')[0]}] {n.get('n.title')} (ID: {n.get('n.id')})")
        else:
            print("❌ No nodes found in Neo4j for this message.")
            
            # Check for any recent nodes
            print("   Checking for ANY recent nodes in last 10 mins...")
            query_recent = """
            MATCH (n)
            WHERE n.created_at > datetime() - duration('PT10M')
            RETURN n.id, labels(n), n.title, n.source_message_id
            LIMIT 5
            """
            result_recent = await session.run(query_recent)
            recent_nodes = [dict(record) async for record in result_recent]
            if recent_nodes:
                print(f"   Found {len(recent_nodes)} recent nodes (orphaned or different ID?):")
                for n in recent_nodes:
                    print(f"   - {n.get('n.title')} (Source: {n.get('n.source_message_id')})")
            else:
                print("   ❌ No recent nodes found at all.")

if __name__ == "__main__":
    try:
        asyncio.run(check_ingestion_status())
    except Exception as e:
        print(f"Error: {e}")
