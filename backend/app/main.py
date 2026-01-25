# -*- coding: utf-8 -*-
"""
Main FastAPI application for BUJA Core Platform Backend
"""
import sys
# [UTF-8] Ensure process-level UTF-8 encoding for stdout/stderr
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import redis.asyncio as redis
from structlog import get_logger
from app.core.logging_config import setup_logging
from app.core.database import init_db
from app.services.knowledge_service import knowledge_worker

# Setup logging before any other imports that might use it
setup_logging()

from app.core.config import settings
from app.api.v1 import auth, jobs
from app.services.job_manager import JobManager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting BUJA Core Platform Backend", version=settings.APP_VERSION)
    
    # Initialize RDB
    try:
        await init_db()
        logger.info("RDB initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize RDB", error=str(e))
        raise

    # Initialize Redis connection
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    
    try:
        # Test Redis connection
        await redis_client.ping()
        logger.info("Redis connection established", url=settings.REDIS_URL)
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        raise
    
    # Initialize Job Manager
    job_manager = JobManager(redis_client)
    
    # Start Knowledge Worker
    worker_task = asyncio.create_task(knowledge_worker())
    
    # Store in app state
    app.state.redis = redis_client
    app.state.job_manager = job_manager
    app.state.knowledge_worker = worker_task
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await redis_client.close()
    logger.info("Redis connection closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Server-Centric Hybrid AI Platform - Job Dispatching Engine",
    lifespan=lifespan,
    default_response_class=ORJSONResponse
)

# CORS middleware
# Allow all origins for mobile/external access during development
# Note: allow_origins=["*"] cannot be used with allow_credentials=True
# We use allow_origin_regex to permit all origins while allowing credentials (JWT/Auth headers)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
from app.api.v1 import workers, admin, projects, orchestration, models, agents
app.include_router(workers.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(orchestration.router, prefix="/api/v1/orchestration", tags=["orchestration"])
app.include_router(models.router, prefix="/api/v1/models", tags=["models"])

from app.api.v1 import master
app.include_router(master.router, prefix="/api/v1/master", tags=["master"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
async def health_check(save_to_db: bool = False):
    """Health check endpoint"""
    try:
        # Check Redis connection
        await app.state.redis.ping()
        redis_status = "healthy"
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        redis_status = "unhealthy"
    
    result = {
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "components": {
            "redis": redis_status
        }
    }

    if save_to_db:
        try:
            from app.core.database import AsyncSessionLocal, MessageModel
            from datetime import datetime
            import uuid
            async with AsyncSessionLocal() as session:
                diag_msg = MessageModel(
                    message_id=str(uuid.uuid4()),
                    project_id="system-master",
                    sender_role="assistant",
                    content=f"🏥 [자가진단 완료]\n- 시스템 상태: **{result['status'].upper()}**\n- Redis 연결: {result['components']['redis']}\n- 진단 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n시스템이 건강한 상태입니다. 작업을 계속 진행하셔도 좋습니다.",
                    timestamp=datetime.utcnow()
                )
                session.add(diag_msg)
                await session.commit()
        except Exception as e:
            logger.error("Failed to save health check to DB", error=str(e))

    return result

@app.get("/api/v1/health")
async def api_health_check():
    """API V1 Health check endpoint (alias)"""
    return await health_check()



if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
    
# Force reload comment
