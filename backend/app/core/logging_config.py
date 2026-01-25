# -*- coding: utf-8 -*-
import logging
import logging.handlers
import os
import structlog
from typing import Any, Dict

def setup_logging(log_dir: str = None):
    """
    Setup structlog to write to both console and a file in the logs directory.
    """
    if log_dir is None:
        # __file__ is backend/app/core/logging_config.py
        # dirname(__file__) -> backend/app/core
        # dirname(dirname(__file__)) -> backend/app
        # dirname(dirname(dirname(__file__))) -> backend
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(base_dir, "logs")
        
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "backend.log")

    # Standard logging handlers
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    console_handler = logging.StreamHandler()

    # Configure standard logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[file_handler, console_handler]
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if not os.environ.get("DEBUG") else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

def get_recent_logs(log_dir: str = None, lines: int = 20) -> str:
    """
    Read the last N lines from the backend log file.
    """
    if log_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(base_dir, "logs")
        
    log_file = os.path.join(log_dir, "backend.log")
    if not os.path.exists(log_file):
        return "No logs found."
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            # Simple way to get last N lines for small-ish log files
            content = f.readlines()
            return "".join(content[-lines:])
    except Exception as e:
        return f"Error reading logs: {str(e)}"
