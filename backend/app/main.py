"""
Main FastAPI application for BUJA Core Platform Backend
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
from structlog import get_logger

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
    
    # Store in app state
    app.state.redis = redis_client
    app.state.job_manager = job_manager
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await redis_client.close()
    logger.info("Redis connection closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Server-Centric Hybrid AI Platform - Job Dispatching Engine",
    lifespan=lifespan
)

# CORS middleware
# Allow all origins for mobile/external access during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
from app.api.v1 import workers, admin, projects, orchestration, models
app.include_router(workers.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
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
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        await app.state.redis.ping()
        redis_status = "healthy"
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        redis_status = "unhealthy"
    
    return {
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "components": {
            "redis": redis_status
        }
    }

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
