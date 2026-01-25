"""
Configuration for Local Worker
Loads settings from agents.yaml and environment variables
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProviderCapability(BaseModel):
    """LLM provider capability configuration"""
    provider: str = Field(..., description="OLLAMA | OPENROUTER")
    model: str
    endpoint: str
    timeout: int = 120
    max_concurrent: int = 3


class SecurityConfig(BaseModel):
    """Security configuration"""
    job_signing_public_key: str = Field(..., description="Ed25519 public key in PEM format")
    allowed_path_prefixes: List[str] = Field(default_factory=list)
    forbidden_absolute_paths: List[str] = Field(default_factory=list)


class RooCodeConfig(BaseModel):
    """Roo Code integration configuration"""
    enabled: bool = True
    task_file: str = "TASK.md"
    completion_marker: str = ".roo_completed"
    trigger_method: str = "watcher"  # watcher | cli | manual


class ExecutionConfig(BaseModel):
    """Execution configuration"""
    roo_code: RooCodeConfig = Field(default_factory=RooCodeConfig)
    max_file_size_bytes: int = 1048576  # 1 MB
    max_total_size_bytes: int = 10485760  # 10 MB
    git: Dict[str, Any] = Field(default_factory=dict)


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = "INFO"
    file: str = "logs/worker.log"
    max_size_bytes: int = 10485760
    backup_count: int = 5
    format: str = "[%(asctime)s] %(levelname)s: %(message)s"
    structured: bool = True
    json_format: bool = False


class WorkerIdentity(BaseModel):
    """Worker identity configuration"""
    id: str = "worker_001"
    name: str = "Development Worker"
    tags: List[str] = Field(default_factory=list)
    max_memory_mb: int = 4096
    max_cpu_percent: int = 80


class ServerConfig(BaseModel):
    """Backend server connection configuration"""
    url: str = Field(..., description="Backend API URL")
    worker_token: str = Field(..., description="Worker authentication token")
    poll_interval: int = 5
    timeout: int = 30
    heartbeat_interval: int = 30


class WorkerConfig(BaseModel):
    """Complete worker configuration loaded from agents.yaml"""
    server: ServerConfig
    capabilities: List[ProviderCapability]
    security: SecurityConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    worker: WorkerIdentity = Field(default_factory=WorkerIdentity)


class Settings(BaseSettings):
    """
    Worker settings
    
    Loads from:
    1. agents.yaml (primary configuration)
    2. Environment variables (overrides)
    """
    
    # Config file path
    config_file: str = "agents.yaml"
    
    # Environment overrides
    SERVER_URL: Optional[str] = None
    WORKER_TOKEN: Optional[str] = None
    JOB_SIGNING_PUBLIC_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow" # 외부 환경변수 추가 허용
    
    def load_config(self) -> WorkerConfig:
        """
        Load configuration from agents.yaml
        
        Returns:
            WorkerConfig object
            
        Raises:
            FileNotFoundError: If agents.yaml not found
            ValueError: If configuration is invalid
        """
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}\n"
                f"Please copy agents.yaml.example to agents.yaml and configure it."
            )
        
        # Load YAML
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Apply environment overrides
        if self.SERVER_URL:
            config_data['server']['url'] = self.SERVER_URL
        
        if self.WORKER_TOKEN:
            config_data['server']['worker_token'] = self.WORKER_TOKEN
        
        if self.JOB_SIGNING_PUBLIC_KEY:
            config_data['security']['job_signing_public_key'] = self.JOB_SIGNING_PUBLIC_KEY
        
        # Validate and create config
        try:
            worker_config = WorkerConfig(**config_data)
            return worker_config
        except Exception as e:
            raise ValueError(f"Invalid configuration: {e}")


# Global settings instance
settings = Settings()

# Load worker configuration
try:
    worker_config = settings.load_config()
except FileNotFoundError as e:
    # Allow import without config file (for testing)
    print(f"Warning: {e}")
    worker_config = None
