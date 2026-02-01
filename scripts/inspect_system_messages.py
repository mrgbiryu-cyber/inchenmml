# -*- coding: utf-8 -*-
import asyncio
import sys
from sqlalchemy import select, or_, func
from app.core.database import AsyncSessionLocal, MessageModel, ThreadModel

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

async def inspect_system_messages():
    print("🔍 Inspecting System Master Messages...")
    
    async with AsyncSessionLocal() as session:
        # 1. Count messages for system-master
        stmt = select(func.count(MessageModel.message_id)).where(
            or_(MessageModel.project_id == None, MessageModel.project_id == "system-master")
        )
        count = (await session.execute(stmt)).scalar()
        print(f"Total Messages for System Master: {count}")
        
        if count == 0:
            print("No messages found for System Master.")
            return

        # 2. Check Thread IDs
        stmt = select(MessageModel.thread_id, func.count(MessageModel.message_id))\
            .where(or_(MessageModel.project_id == None, MessageModel.project_id == "system-master"))\
            .group_by(MessageModel.thread_id)
        
        results = (await session.execute(stmt)).all()
        
        print("\nMessage Distribution by Thread ID:")
        for thread_id, msg_count in results:
            t_label = thread_id if thread_id else "NULL"
            print(f"  - Thread: {t_label} | Count: {msg_count}")
            
            # Check if this thread exists in ThreadModel
            if thread_id:
                t_stmt = select(ThreadModel).where(ThreadModel.id == thread_id)
                t_exists = (await session.execute(t_stmt)).scalars().first()
                if t_exists:
                    print(f"    ✅ Exists in ThreadModel: {t_exists.title}")
                else:
                    print(f"    ❌ Orphan (Not in ThreadModel)")
            else:
                 print(f"    ❌ Orphan (NULL)")

if __name__ == "__main__":
    try:
        asyncio.run(inspect_system_messages())
    except Exception as e:
        print(f"Error: {e}")
