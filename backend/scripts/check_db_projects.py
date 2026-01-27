import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, MessageModel

async def check_msgs():
    async with AsyncSessionLocal() as session:
        stmt = select(MessageModel.project_id).distinct()
        result = await session.execute(stmt)
        project_ids = [r[0] for r in result.all()]
        print(f"Project IDs in DB: {project_ids}")

if __name__ == "__main__":
    asyncio.run(check_msgs())
