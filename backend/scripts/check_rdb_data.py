import asyncio
import os
import sys
import uuid

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.database import AsyncSessionLocal, MessageModel
from sqlalchemy import select

async def check_rdb_data():
    async with AsyncSessionLocal() as session:
        query = select(MessageModel).order_by(MessageModel.timestamp.desc()).limit(10)
        result = await session.execute(query)
        messages = result.scalars().all()
        
        print(f"Total messages found (last 10): {len(messages)}")
        for m in messages:
            print(f"[{m.timestamp}] {m.sender_role}: {m.content[:50]}... (Proj: {m.project_id}, Thread: {m.thread_id})")

if __name__ == "__main__":
    asyncio.run(check_rdb_data())
