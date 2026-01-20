"""
Configuration settings for BUJA Core Platform Backend
Loads environment variables and provides typed configuration
"""
import os
from typing import Optional
from dotenv import load_dotenv  # 👈 [추가] 강제 로딩 도구

# 1. 👇 Pydantic이 읽기 전에, 우리가 먼저 강제로 읽어버립니다.
# (현재 폴더의 .env를 시스템 환경변수로 로드함)
load_dotenv()

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "BUJA Core Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379/0"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Vector Database
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: str = "us-west1-gcp"
    PINECONE_INDEX_NAME: str = "buja-knowledge"
    
    # LLM Providers
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # Search
    TAVILY_API_KEY: Optional[str] = None
    
    # Observability
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    
    # Authentication & Security
    # 2. 👇 이제 환경변수에서 값을 가져옵니다. (없으면 에러)
    JWT_SECRET_KEY: str = Field(..., description="Secret key for JWT signing")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Ed25519 Job Signing Keys
    JOB_SIGNING_PRIVATE_KEY: str = Field(..., description="Ed25519 private key in PEM format")
    JOB_SIGNING_PUBLIC_KEY: str = Field(..., description="Ed25519 public key in PEM format")
    
    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_WEBHOOK_URL: Optional[str] = None
    
    # Rate Limiting & Quotas
    DEFAULT_MONTHLY_QUOTA_USD: float = 100.0
    RATE_LIMIT_PER_TENANT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_USER_PER_SECOND: int = 10
    
    # Job Queue Configuration
    MAX_QUEUED_JOBS_PER_TENANT: int = 50
    JOB_DEFAULT_TIMEOUT_SEC: int = 600
    JOB_MAX_TIMEOUT_SEC: int = 3600
    
    # Worker Management
    WORKER_HEARTBEAT_TIMEOUT_SEC: int = 120
    WORKER_MAX_REASSIGN_COUNT: int = 2
    
    # File System Safety
    MAX_FILE_SIZE_BYTES: int = 1048576  # 1 MB
    MAX_TOTAL_JOB_SIZE_BYTES: int = 10485760  # 10 MB
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"
    CORS_ALLOW_CREDENTIALS: bool = True
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 1.0
    
    # Pydantic 설정 (보조 수단으로 남겨둠)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Global settings instance
settings = Settings()