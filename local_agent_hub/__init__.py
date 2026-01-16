# Local Agent Hub package exports
from local_agent_hub.core.config import settings, worker_config
from local_agent_hub.core.security import (
    verify_job_signature,
    validate_path,
    validate_job_paths,
    SecurityError
)

__version__ = "1.0.0"

__all__ = [
    "settings",
    "worker_config",
    "verify_job_signature",
    "validate_path",
    "validate_job_paths",
    "SecurityError"
]
