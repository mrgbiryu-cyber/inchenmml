import asyncio
import os
import sys
import uuid

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Force UTF-8 for this script's output
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from app.core.database import AsyncSessionLocal, MessageModel, init_db
from sqlalchemy import select

async def test_korean_storage():
    await init_db()
    test_content = "테스트 메시지: 한글 저장 및 출력 검증 (assistant_partial)"
    project_id = uuid.uuid4()
    
    print(f"Testing save: {test_content}")
    
    async with AsyncSessionLocal() as session:
        msg = MessageModel(
            message_id=uuid.uuid4(),
            project_id=project_id,
            sender_role="assistant_partial",
            content=test_content
        )
        session.add(msg)
        await session.commit()
        msg_id = msg.message_id

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(MessageModel).where(MessageModel.message_id == msg_id))
        saved_msg = res.scalar_one_or_none()
        if saved_msg:
            print(f"Retrieved content: {saved_msg.content}")
            if saved_msg.content == test_content:
                print("✅ Success: Korean content saved and retrieved correctly.")
            else:
                print("❌ Failure: Content mismatch.")
        else:
            print("❌ Failure: Message not found.")

if __name__ == "__main__":
    asyncio.run(test_korean_storage())
