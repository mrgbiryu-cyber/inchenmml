# -*- coding: utf-8 -*-
"""
Main entry point for Local Worker
"""
import sys
# [UTF-8] Ensure process-level UTF-8 encoding for stdout/stderr
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import signal
from structlog import get_logger

from local_agent_hub.core.config import settings, worker_config
from local_agent_hub.worker.poller import JobPoller
from local_agent_hub.worker.executor import JobExecutor

logger = get_logger(__name__)


class Worker:
    """
    Main Worker application
    
    Coordinates polling and execution
    """
    
    def __init__(self):
        """Initialize worker"""
        if worker_config is None:
            raise RuntimeError(
                "Worker configuration not loaded. "
                "Please ensure agents.yaml exists and is valid."
            )
        
        self.config = worker_config
        self.poller = JobPoller(self.config)
        self.executor = JobExecutor(self.config)
        self.running = False
    
    async def start(self):
        """Start the worker"""
        self.running = True
        
        logger.info(
            "🚀 BUJA Local Worker starting",
            worker_id=self.config.worker.id,
            server_url=self.config.server.url
        )
        
        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self.poller.heartbeat_loop())
            
            # Start polling loop
            await self.poller.poll_loop(self.executor.execute_job)
            
            # Cancel heartbeat
            heartbeat_task.cancel()
            
        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")
        except Exception as e:
            logger.error("Worker error", error=str(e))
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the worker"""
        if not self.running:
            return
        
        logger.info("Stopping worker...")
        self.running = False
        
        # Stop poller
        await self.poller.stop()
        
        # Close executor
        await self.executor.close()
        
        logger.info("✅ Worker stopped")


async def main():
    """Main entry point"""
    try:
        worker = Worker()
        await worker.start()
    except Exception as e:
        import traceback
        logger.error("Fatal error", error=str(e))
        logger.error("Traceback", traceback=traceback.format_exc())
        print(f"\n❌ Fatal error: {e}")
        print(f"\nFull traceback:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    # Configure logging
    import structlog
    import logging
    
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.INFO if worker_config else logging.WARNING
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Run worker
    asyncio.run(main())
