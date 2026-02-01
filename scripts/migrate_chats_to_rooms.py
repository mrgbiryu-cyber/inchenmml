# -*- coding: utf-8 -*-
import asyncio
import uuid
import sys
from sqlalchemy import select, update, or_, and_
from app.core.database import AsyncSessionLocal, MessageModel, ThreadModel, _normalize_project_id

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

async def migrate_legacy_chats():
    print("🚀 Starting migration: Merging orphaned legacy chats into 'Default Room' per project...")
    
    async with AsyncSessionLocal() as session:
        # 1. Get all distinct project_ids from messages
        stmt = select(MessageModel.project_id).distinct()
        result = await session.execute(stmt)
        project_ids = result.scalars().all()
        
        migrated_projects = 0
        total_messages_moved = 0
        
        for p_id in project_ids:
            # Determine project label and handling for NULL (system-master)
            project_label = str(p_id) if p_id else "system-master"
            print(f"\nProcessing Project: {project_label}")
            
            # 2. Get or Create Default Thread for this project
            # We look for a thread titled "기본 대화방"
            thread_stmt = select(ThreadModel).where(
                ThreadModel.project_id == p_id,
                ThreadModel.title == "기본 대화방"
            )
            thread_result = await session.execute(thread_stmt)
            default_thread = thread_result.scalars().first()
            
            if default_thread:
                default_thread_id = default_thread.id
                print(f"  - Found existing default thread: {default_thread_id}")
            else:
                default_thread_id = f"thread-{uuid.uuid4()}"
                new_thread = ThreadModel(
                    id=default_thread_id,
                    project_id=p_id,
                    title="기본 대화방"
                )
                session.add(new_thread)
                await session.commit()
                print(f"  - Created new default thread: {default_thread_id}")
            
            # 3. Identify orphaned messages
            # Orphaned = messages where thread_id is NULL OR thread_id is NOT in the threads table
            
            # Get all distinct thread_ids used in messages for this project
            if p_id is None:
                msg_threads_stmt = select(MessageModel.thread_id).distinct().where(MessageModel.project_id == None)
            else:
                msg_threads_stmt = select(MessageModel.thread_id).distinct().where(MessageModel.project_id == p_id)
                
            msg_threads_result = await session.execute(msg_threads_stmt)
            message_thread_ids = msg_threads_result.scalars().all()
            
            # Filter out thread_ids that are actually valid (exist in threads table)
            # We do this check in python to avoid complex NOT IN subqueries if list is small, 
            # but for correctness let's query DB for valid ones.
            
            # If message_thread_ids is empty, skip
            if not message_thread_ids:
                print("  - No messages found.")
                continue

            # Clean list: remove None
            valid_ids_to_check = [tid for tid in message_thread_ids if tid is not None]
            
            valid_threads_in_db = []
            if valid_ids_to_check:
                valid_threads_stmt = select(ThreadModel.id).where(ThreadModel.id.in_(valid_ids_to_check))
                valid_threads_result = await session.execute(valid_threads_stmt)
                valid_threads_in_db = valid_threads_result.scalars().all()
            
            # Identify which ones are orphans
            # Orphans = (All Msg Thread IDs) - (Valid Threads in DB) - (The Default Thread Itself)
            orphans = set(message_thread_ids) - set(valid_threads_in_db)
            
            # Remove the current default_thread_id if it's in the list (we don't move messages already in default thread)
            if default_thread_id in orphans:
                orphans.remove(default_thread_id)
            
            if not orphans:
                print("  - No orphaned legacy threads found.")
                continue
                
            print(f"  - Found {len(orphans)} orphaned thread IDs (including NULL) to merge.")
            
            # 4. Update messages
            # We update messages where thread_id IN orphans (handling None separately if needed)
            
            orphans_list = list(orphans)
            has_none = None in orphans_list
            clean_orphans = [o for o in orphans_list if o is not None]
            
            count = 0
            
            # Update for non-None orphans
            if clean_orphans:
                if p_id is None:
                    # [Fix] system-master can be NULL or 'system-master' string
                    stmt = update(MessageModel).where(
                        or_(MessageModel.project_id == None, MessageModel.project_id == "system-master"),
                        MessageModel.thread_id.in_(clean_orphans)
                    ).values(thread_id=default_thread_id)
                else:
                    stmt = update(MessageModel).where(
                        MessageModel.project_id == p_id,
                        MessageModel.thread_id.in_(clean_orphans)
                    ).values(thread_id=default_thread_id)
                
                res = await session.execute(stmt)
                count += res.rowcount

            # Update for None orphans
            if has_none:
                if p_id is None:
                    stmt = update(MessageModel).where(
                         or_(MessageModel.project_id == None, MessageModel.project_id == "system-master"),
                        MessageModel.thread_id == None
                    ).values(thread_id=default_thread_id)
                else:
                    stmt = update(MessageModel).where(
                        MessageModel.project_id == p_id,
                        MessageModel.thread_id == None
                    ).values(thread_id=default_thread_id)
                
                res = await session.execute(stmt)
                count += res.rowcount
            
            await session.commit()
            
            print(f"  - Moved {count} messages to {default_thread_id}")
            total_messages_moved += count
            migrated_projects += 1

        print(f"\n✅ Migration Complete!")
        print(f"   Projects Processed: {len(project_ids)}")
        print(f"   Projects with Migrations: {migrated_projects}")
        print(f"   Total Messages Moved: {total_messages_moved}")

if __name__ == "__main__":
    try:
        asyncio.run(migrate_legacy_chats())
    except Exception as e:
        print(f"Fatal Error: {e}")
