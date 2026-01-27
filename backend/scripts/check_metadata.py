import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, MessageModel

async def check_metadata():
    async with AsyncSessionLocal() as session:
        stmt = select(MessageModel.project_id, MessageModel.metadata_json).where(MessageModel.metadata_json.is_not(None)).limit(20)
        result = await session.execute(stmt)
        for r in result.all():
            print(f"ID: {r[0]}, Meta: {r[1]}")

if __name__ == "__main__":
    asyncio.run(check_metadata())
