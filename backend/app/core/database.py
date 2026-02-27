# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, Text, JSON, Integer, Float
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid
from typing import Tuple, Optional, List
from datetime import datetime
import os
import importlib.util
from app.core.config import settings
from structlog import get_logger

# For SQLite compatibility with UUID-like strings if not using PostgreSQL
from sqlalchemy.types import TypeDecorator, CHAR
import json

logger = get_logger(__name__)

class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as string without dashes.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            try:
                return uuid.UUID(value)
            except ValueError:
                # Fallback for non-UUID strings like 'system-master'
                return value

Base = declarative_base()

class MessageModel(Base):
    __tablename__ = "messages"

    message_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), nullable=True)
    thread_id = Column(String, nullable=True) # Optional grouping
    sender_role = Column(String, nullable=False) # user | master | agent | tool | auditor
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSON, nullable=True)

class CostLogModel(Base):
    __tablename__ = "cost_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), nullable=True)
    message_id = Column(GUID(), nullable=True, unique=True) # Ensure Idempotency
    extraction_type = Column(String) # realtime | batch
    model_tier = Column(String) # high | low
    model_name = Column(String)
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    status = Column(String) # success | skip | fail
    timestamp = Column(DateTime, default=datetime.utcnow)

# [v3.2] Draft Model Definition (Fix for AsyncEngine inspection)
class DraftModel(Base):
    __tablename__ = "drafts"
    
    id = Column(String(255), primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False)
    project_id = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default='UNVERIFIED', index=True)
    category = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(50), default='USER_UTTERANCE')
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ttl_days = Column(Integer, default=7)

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    tenant_id = Column(String(50), nullable=False)
    role = Column(String(20), nullable=False)
    is_active = Column(Integer, default=1) # 1: True, 0: False (SQLite compat)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserProjectModel(Base):
    __tablename__ = "user_projects"

    user_id = Column(String(50), primary_key=True)
    project_id = Column(String(50), primary_key=True)
    role = Column(String(20), default="viewer") # viewer | editor
    assigned_at = Column(DateTime, default=datetime.utcnow)

class ThreadModel(Base):
    __tablename__ = "threads"

    id = Column(String(100), primary_key=True)
    project_id = Column(GUID(), nullable=True) # Matches MessageModel.project_id type
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GrowthRunModel(Base):
    __tablename__ = "growth_runs"

    id = Column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_key = Column(String(100), nullable=False, index=True)
    result_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class GrowthArtifactModel(Base):
    __tablename__ = "growth_artifacts"

    id = Column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(100), nullable=False, index=True)
    project_key = Column(String(100), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False, index=True)
    format = Column(String(20), nullable=False, index=True)
    content_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

# Database URL Handling
DATABASE_URL = (settings.DATABASE_URL or "").strip()
IS_PRODUCTION = settings.ENVIRONMENT.lower() == "production"
LOCAL_SQLITE_PLACEHOLDERS = {
    "postgresql://user:password@localhost:5432/buja_core",
    "postgresql+asyncpg://user:password@localhost:5432/buja_core",
}


def _build_default_sqlite_url() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, "data", "buja.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


def _has_asyncpg() -> bool:
    return importlib.util.find_spec("asyncpg") is not None


def _resolve_database_url() -> str:
    strict_mode = bool(settings.STRICT_DB_MODE) or IS_PRODUCTION
    allow_without_postgres = bool(settings.STARTUP_WITHOUT_POSTGRES)
    unresolved = (not DATABASE_URL) or (DATABASE_URL in LOCAL_SQLITE_PLACEHOLDERS)

    if unresolved:
        if strict_mode and not allow_without_postgres:
            raise RuntimeError(
                "DATABASE_URL is required in production/strict mode. SQLite fallback is blocked."
            )
        logger.warning(
            "DATABASE_URL unresolved; falling back to sqlite",
            strict_mode=strict_mode,
            allow_without_postgres=allow_without_postgres,
        )
        return _build_default_sqlite_url()

    selected_url = DATABASE_URL

    if selected_url.startswith("postgresql://"):
        if strict_mode:
            raise RuntimeError(
                "DATABASE_URL must use postgresql+asyncpg:// in production/strict mode."
            )
        if _has_asyncpg():
            selected_url = selected_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            logger.warning("DATABASE_URL upgraded to postgresql+asyncpg://")
        else:
            raise RuntimeError(
                "DATABASE_URL uses postgresql:// but asyncpg is not available."
            )

    if selected_url.startswith("postgresql+asyncpg://") and not _has_asyncpg():
        raise RuntimeError("DATABASE_URL requires asyncpg, but asyncpg is not installed.")

    if IS_PRODUCTION and ("localhost" in selected_url.lower() or "127.0.0.1" in selected_url):
        raise RuntimeError("DATABASE_URL must not use localhost/127.0.0.1 in production.")

    if IS_PRODUCTION and selected_url.startswith("sqlite"):
        raise RuntimeError("SQLite is not allowed when ENVIRONMENT=production.")

    return selected_url


DATABASE_URL = _resolve_database_url()

# [UTF-8] Ensure all JSON serialization in DB uses ensure_ascii=False
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    } if "sqlite" in DATABASE_URL else {}
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# [UTF-8] Force SQLite to use UTF-8 encoding
from sqlalchemy import event
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA encoding = 'UTF-8'")
        cursor.close()

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Careful in production!
        await conn.run_sync(Base.metadata.create_all)
    
    # [Neo4j] Create indexes for optimized searching
    from app.core.neo4j_client import neo4j_client
    try:
        await neo4j_client.create_indexes()
    except Exception as e:
        logger.warning("Failed to create Neo4j indexes during init", error=str(e))

def _normalize_project_id(project_id: str) -> Optional[uuid.UUID]:
    """
    Task 1.4: Normalize project_id to ensure case-insensitive consistent UUID generation
    Per CONVERSATION_CONSISTENCY.md
    """
    if not project_id or project_id == "system-master":
        return None
    
    try:
        if isinstance(project_id, uuid.UUID):
            return project_id
        # If already a valid UUID, return it
        return uuid.UUID(project_id)
    except (ValueError, AttributeError):
        # Normalize: lowercase + strip, then generate deterministic UUID
        normalized = str(project_id).lower().strip()
        return uuid.uuid5(uuid.NAMESPACE_DNS, normalized)


async def save_message_to_rdb(
    role: str, 
    content: str, 
    project_id: str = None, 
    thread_id: str = None, 
    metadata: dict = None
) -> Tuple[uuid.UUID, str]:
    """
    Save message to RDB. Single Source of Truth.
    Task 1.5: Returns (message_id, thread_id) per CONVERSATION_CONSISTENCY.md
    Auto-generates thread_id if None.
    """
    if thread_id in ["null", "undefined", ""]:
        thread_id = None
    
    # Task 1.5: Auto-generate thread_id if not provided
    if thread_id is None:
        thread_id = f"thread-{uuid.uuid4()}"
        
    async with AsyncSessionLocal() as session:
        msg_id = uuid.uuid4()
        
        # Task 1.4: Use normalized project_id
        p_id = _normalize_project_id(project_id)
        
        new_msg = MessageModel(
            message_id=msg_id,
            project_id=p_id,
            thread_id=thread_id,
            sender_role=role,
            content=content,
            metadata_json=metadata
        )
        session.add(new_msg)
        await session.commit()
        return (msg_id, thread_id)

async def get_messages_from_rdb(project_id: str = None, thread_id: str = None, limit: int = 50):
    if thread_id in ["null", "undefined", ""]:
        thread_id = None
        
    from sqlalchemy import select, or_
    async with AsyncSessionLocal() as session:
        query = select(MessageModel)
        
        # [Task 1.4/1.5 Update] system-master는 NULL로 저장되므로 명시적으로 필터링
        if project_id == "system-master":
            query = query.filter(or_(MessageModel.project_id == None, MessageModel.project_id == "system-master"))
        elif project_id:
            p_id = _normalize_project_id(project_id)
            query = query.filter(MessageModel.project_id == p_id)
            
        if thread_id:
            query = query.filter(MessageModel.thread_id == thread_id)
        
        query = query.order_by(MessageModel.timestamp.asc()).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

# ===== [v3.2] Shadow Mining - Draft Storage =====

async def save_draft_to_rdb(draft) -> str:
    """
    Draft를 PostgreSQL에 저장 (Using declarative model)
    Returns: draft_id
    """
    async with AsyncSessionLocal() as session:
        new_draft = DraftModel(
            id=draft.id,
            session_id=draft.session_id,
            user_id=draft.user_id,
            project_id=draft.project_id,
            status=draft.status,
            category=draft.category,
            content=draft.content,
            source=draft.source,
            timestamp=draft.timestamp,
            ttl_days=draft.ttl_days
        )
        # Using merge to handle potential updates (upsert behavior)
        await session.merge(new_draft)
        await session.commit()
        return draft.id

async def get_drafts_from_rdb(session_id: str = None, status: str = "UNVERIFIED") -> List:
    """
    Draft 조회 (Using declarative model)
    """
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as session:
        query = select(DraftModel)
        
        if session_id:
            query = query.filter(DraftModel.session_id == session_id)
        if status:
            query = query.filter(DraftModel.status == status)
        
        query = query.order_by(DraftModel.timestamp.desc())
        result = await session.execute(query)
        return result.scalars().all()

async def delete_expired_drafts(days: int = 7):
    """
    만료된 Draft 삭제 (TTL 기반) (Using declarative model)
    """
    from sqlalchemy import delete
    from datetime import datetime, timedelta
    
    async with AsyncSessionLocal() as session:
        expired_time = datetime.utcnow() - timedelta(days=days)
        stmt = delete(DraftModel).where(
            DraftModel.status == 'UNVERIFIED',
            DraftModel.timestamp < expired_time
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


def _normalize_project_key(project_id: str) -> str:
    if not project_id:
        return "system-master"
    return str(project_id).strip().lower()


async def save_growth_run(project_id: str, result_json: dict, artifacts: dict) -> str:
    run_id = str(uuid.uuid4())
    project_key = _normalize_project_key(project_id)
    async with AsyncSessionLocal() as session:
        run = GrowthRunModel(
            id=run_id,
            project_key=project_key,
            result_json=result_json,
        )
        session.add(run)
        for artifact_type, format_map in artifacts.items():
            for fmt, content in format_map.items():
                if isinstance(content, str):
                    session.add(
                        GrowthArtifactModel(
                            run_id=run_id,
                            project_key=project_key,
                            artifact_type=artifact_type,
                            format=fmt,
                            content_text=content,
                        )
                    )
        await session.commit()
    return run_id


async def get_latest_growth_run(project_id: str) -> Optional[dict]:
    from sqlalchemy import select

    project_key = _normalize_project_key(project_id)
    async with AsyncSessionLocal() as session:
        stmt = (
            select(GrowthRunModel)
            .where(GrowthRunModel.project_key == project_key)
            .order_by(GrowthRunModel.created_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        return row.result_json if row else None


async def get_latest_growth_artifact(project_id: str, artifact_type: str, fmt: str) -> Optional[str]:
    from sqlalchemy import select

    project_key = _normalize_project_key(project_id)
    async with AsyncSessionLocal() as session:
        stmt = (
            select(GrowthArtifactModel)
            .where(
                GrowthArtifactModel.project_key == project_key,
                GrowthArtifactModel.artifact_type == artifact_type,
                GrowthArtifactModel.format == fmt,
            )
            .order_by(GrowthArtifactModel.created_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        return row.content_text if row else None
