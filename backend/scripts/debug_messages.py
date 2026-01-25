import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.database import AsyncSessionLocal, MessageModel
from sqlalchemy import select

async def check_messages():
    async with AsyncSessionLocal() as session:
        query = select(MessageModel).order_by(MessageModel.timestamp.desc()).limit(20)
        result = await session.execute(query)
        messages = result.scalars().all()
        
        print(f"{'ROLE':<20} | {'PROJECT_ID':<40} | {'THREAD_ID':<20} | {'CONTENT'}")
        print("-" * 100)
        for m in messages:
            content = m.content.replace('\n', ' ')[:50]
            print(f"{m.sender_role:<20} | {str(m.project_id):<40} | {str(m.thread_id):<20} | {content}")

if __name__ == "__main__":
    asyncio.run(check_messages())
