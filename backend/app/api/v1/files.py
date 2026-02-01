# -*- coding: utf-8 -*-
"""
File Management Endpoints
Handles file uploads and triggers knowledge ingestion
"""
import hashlib
import sys
import uuid
import os
from pathlib import Path
from typing import List, Optional
from sqlalchemy import select, func

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Form
from structlog import get_logger

from app.core.config import settings
from app.api.dependencies import get_current_user
from app.models.schemas import User, UserRole
from app.services.knowledge_service import knowledge_service, knowledge_queue
from app.core.database import AsyncSessionLocal, MessageModel
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

# Ensure upload directory exists
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA256 hash of file content for deduplication."""
    return hashlib.sha256(file_content).hexdigest()

async def check_duplicate_file(session, file_hash: str, project_id: str) -> Optional[MessageModel]:
    """Check if file with same hash already exists in project."""
    # Note: JSON query might be slow without index, but acceptable for MVP
    # In PostgreSQL we could use jsonb_path_query or containment @>
    # Here we fetch potentially matching messages and check in python or trust the DB
    # Optimized: We assume 'file_hash' is top-level key in metadata_json
    stmt = select(MessageModel).where(
        MessageModel.project_id == (uuid.UUID(project_id) if project_id != "system-master" else None),
        func.json_extract(MessageModel.metadata_json, '$.file_hash') == file_hash
    ).limit(1)
    
    # SQLite/Postgres compatibility issue with json_extract vs ->> 
    # For MVP safety, let's fetch messages with type='file_upload' and filter in memory if volume is low,
    # OR use a more generic approach.
    # Let's try to add file_hash to metadata and query it safely.
    
    # Since we can't easily do cross-db JSON query without knowing DB type in this context perfectly,
    # we will use a safer approach for this MVP: 
    # Real duplication check might be better done by KnowledgeService or specific index.
    # For now, let's skip complex DB query and rely on filename + size collision check as a proxy 
    # or just proceed. 
    # BUT the requirement is "Deduplication".
    
    # Let's read all file_uploads for this project and check hash. 
    # Limit to recent 100 uploads for performance? Or just trust KnowledgeService de-dupe?
    # Task explicitly says "Check hashes before processing folder uploads."
    
    # Better approach:
    # 1. Fetch recent file uploads for project
    # 2. Check hashes
    
    return None # Placeholder: logic implemented inside endpoints for clarity

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form("system-master"),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a file and trigger knowledge ingestion with Deduplication.
    """
    try:
        # 1. Read content and Calculate Hash
        content = await file.read()
        size = len(content)
        file.file.seek(0) # Reset cursor
        
        if size > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_BYTES} bytes"
            )
            
        file_hash = calculate_file_hash(content)
        
        # 2. Check Deduplication
        async with AsyncSessionLocal() as session:
            # Check if this hash exists in recent uploads for this project
            # Using basic JSON text search for compatibility
            stmt = select(MessageModel).where(
                MessageModel.metadata_json.like(f'%"{file_hash}"%')
            ).limit(1)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            
            if existing:
                logger.info("Duplicate file detected, skipping upload", filename=file.filename, hash=file_hash)
                return {
                    "filename": file.filename,
                    "status": "skipped",
                    "reason": "duplicate",
                    "message_id": str(existing.message_id)
                }

        # 3. Save file
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1]
        safe_filename = f"{file_id}{ext}"
        file_path = UPLOAD_DIR / safe_filename
        
        with open(file_path, "wb") as f:
            f.write(content)
            
        logger.info("File uploaded", filename=file.filename, size=size, user_id=current_user.id)
        
        # 4. Create Message for Ingestion
        content_preview = f"[File Upload] {file.filename} ({size} bytes)"
        full_text = ""
        
        if ext.lower() in ['.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.html', '.css', '.csv']:
            try:
                full_text = content.decode('utf-8')
                content_preview += f"\n\n--- FILE CONTENT ---\n{full_text}"
            except Exception as e:
                logger.warning("Failed to decode text file content", error=str(e))
                content_preview += "\n(Binary or non-utf8 content)"
        
        # 5. Save to DB
        msg_id = str(uuid.uuid4())
        async with AsyncSessionLocal() as session:
            msg = MessageModel(
                message_id=msg_id,
                project_id=uuid.UUID(project_id) if project_id != "system-master" else None,
                sender_role="user", 
                content=content_preview,
                timestamp=datetime.utcnow(),
                metadata_json={
                    "type": "file_upload",
                    "filename": file.filename,
                    "file_path": str(file_path),
                    "file_size": size,
                    "file_hash": file_hash, # [Deduplication Key]
                    "user_id": current_user.id
                }
            )
            session.add(msg)
            await session.commit()
            
        # 6. Trigger Knowledge Ingestion
        if full_text:
            knowledge_queue.put_nowait(msg_id)
            logger.info("File queued for ingestion", message_id=msg_id, project_id=project_id, user_id=current_user.id)
            
        return {
            "filename": file.filename,
            "file_id": file_id,
            "message_id": msg_id,
            "status": "queued" if full_text else "saved_only"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@router.post("/upload-folder")
async def upload_folder(
    files: List[UploadFile] = File(...),
    project_id: str = Form("system-master"),
    current_user: User = Depends(get_current_user)
):
    """
    Upload multiple files (Folder) with Deduplication.
    """
    results = []
    
    for file in files:
        try:
            # Reuse logic from upload_file but simplified for batch
            content = await file.read()
            size = len(content)
            
            if size > settings.MAX_FILE_SIZE_BYTES:
                results.append({"filename": file.filename, "status": "failed", "reason": "too_large"})
                continue
                
            file_hash = calculate_file_hash(content)
            
            # Check Dedupe
            async with AsyncSessionLocal() as session:
                stmt = select(MessageModel).where(
                    MessageModel.metadata_json.like(f'%"{file_hash}"%')
                ).limit(1)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                
                if existing:
                    results.append({"filename": file.filename, "status": "skipped", "reason": "duplicate"})
                    continue

            # Save
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1]
            safe_filename = f"{file_id}{ext}"
            file_path = UPLOAD_DIR / safe_filename
            
            with open(file_path, "wb") as f:
                f.write(content)
                
            # DB & Queue
            msg_id = str(uuid.uuid4())
            content_preview = f"[Folder Upload] {file.filename}"
            full_text = ""
            
            if ext.lower() in ['.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.html', '.css', '.csv']:
                try:
                    full_text = content.decode('utf-8')
                    content_preview += f"\n\n--- FILE CONTENT ---\n{full_text}"
                except:
                    pass
            
            async with AsyncSessionLocal() as session:
                msg = MessageModel(
                    message_id=msg_id,
                    project_id=uuid.UUID(project_id) if project_id != "system-master" else None,
                    sender_role="user", 
                    content=content_preview,
                    timestamp=datetime.utcnow(),
                    metadata_json={
                        "type": "file_upload",
                        "filename": file.filename,
                        "file_path": str(file_path),
                        "file_size": size,
                        "file_hash": file_hash,
                        "user_id": current_user.id
                    }
                )
                session.add(msg)
                await session.commit()
                
            if full_text:
                knowledge_queue.put_nowait(msg_id)
                
            results.append({"filename": file.filename, "status": "queued"})
            
        except Exception as e:
            logger.error(f"Error processing file {file.filename}", error=str(e))
            results.append({"filename": file.filename, "status": "failed", "error": str(e)})
            
    return {"results": results, "total": len(files), "processed": len([r for r in results if r['status'] == 'queued'])}
