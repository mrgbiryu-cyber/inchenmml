"""
Job Poller for Local Worker
Polls backend for pending jobs using long polling
"""
import asyncio
from typing import Optional, Dict, Any
import httpx
from structlog import get_logger

from local_agent_hub.core.config import WorkerConfig
from local_agent_hub.core.security import verify_job_signature, SecurityError

logger = get_logger(__name__)


class JobPoller:
    """
    Polls backend for pending jobs
    
    Uses long polling (30s timeout) for efficient job fetching
    """
    
    def __init__(self, config: WorkerConfig):
        """
        Initialize Job Poller
        
        Args:
            config: Worker configuration
        """
        self.config = config
        self.server_url = config.server.url
        self.worker_token = config.server.worker_token
        self.poll_interval = config.server.poll_interval
        self.timeout = config.server.timeout
        self.public_key = config.security.job_signing_public_key
        self.running = False
        
        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout + 5.0),  # Slightly longer than server timeout
            headers={
                "Authorization": f"Bearer {self.worker_token}",
                "User-Agent": f"BUJA-Worker/{config.worker.id}"
            }
        )
    
    async def poll_once(self) -> Optional[Dict[str, Any]]:
        """
        Poll for a single job
        
        Returns:
            Job dictionary if available, None otherwise
            
        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            logger.debug(f"Polling for jobs at {self.server_url}/api/v1/jobs/pending")
            response = await self.client.get(
                f"{self.server_url}/api/v1/jobs/pending",
                timeout=self.timeout
            )
            
            logger.debug(f"Poll response status: {response.status_code}")
            
            if response.status_code == 200:
                # Check for empty content
                if not response.content:
                    logger.warning("Received 200 OK but empty content")
                    return None

                try:
                    job = response.json()
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {e}", raw_content=response.text[:200])
                    return None
                
                # Check if job is None or empty
                if job is None:
                    logger.debug("Received None from backend (after JSON parse)")
                    return None
                
                logger.info(
                    "Job received from backend",
                    job_id=job.get('job_id'),
                    execution_location=job.get('execution_location')
                )
                return job
            
            elif response.status_code == 204:
                # No jobs available
                # logger.debug("No pending jobs") # Too noisy
                return None
            
            else:
                logger.warning(
                    "Unexpected response from backend",
                    status_code=response.status_code,
                    response=response.text[:200]
                )
                return None
                
        except httpx.TimeoutException:
            # Long polling timeout - this is normal
            logger.debug("Polling timeout (no jobs)")
            return None
        
        except httpx.HTTPError as e:
            logger.error("HTTP error during polling", error=str(e))
            raise
    
    async def verify_and_validate_job(self, job: Dict[str, Any]) -> bool:
        """
        Verify job signature
        
        Args:
            job: Job dictionary
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Verify Ed25519 signature
            verify_job_signature(job, self.public_key)
            
            logger.info(
                "✅ Job signature verified",
                job_id=job.get('job_id')
            )
            return True
            
        except SecurityError as e:
            logger.error(
                "🔒 SECURITY VIOLATION: Invalid job signature",
                job_id=job.get('job_id'),
                error=str(e)
            )
            
            # Report security incident to backend
            await self.report_security_violation(job.get('job_id'), str(e))
            
            return False
    
    async def report_security_violation(self, job_id: str, error: str) -> None:
        """
        Report security violation to backend
        
        Args:
            job_id: Job identifier
            error: Error message
        """
        try:
            await self.client.post(
                f"{self.server_url}/api/v1/security/violations",
                json={
                    "job_id": job_id,
                    "violation_type": "INVALID_SIGNATURE",
                    "error": error,
                    "worker_id": self.config.worker.id
                }
            )
        except Exception as e:
            logger.error("Failed to report security violation", error=str(e))
    
    async def poll_loop(self, executor_callback):
        """
        Main polling loop
        
        Args:
            executor_callback: Async function to call with valid jobs
        """
        self.running = True
        logger.info(
            "Starting job polling loop",
            server_url=self.server_url,
            poll_interval=self.poll_interval
        )
        
        while self.running:
            try:
                # Poll for job
                job = await self.poll_once()
                
                if job is None:
                    # No job available, wait before next poll
                    await asyncio.sleep(self.poll_interval)
                    continue
                
                # Verify signature
                if not await self.verify_and_validate_job(job):
                    # Invalid signature - skip this job
                    logger.warning(
                        "Skipping job with invalid signature",
                        job_id=job.get('job_id')
                    )
                    continue
                
                # Execute job
                logger.info(
                    "Passing job to executor",
                    job_id=job.get('job_id')
                )
                
                try:
                    await executor_callback(job)
                except Exception as e:
                    logger.error(
                        "Job execution failed",
                        job_id=job.get('job_id'),
                        error=str(e)
                    )
                
            except KeyboardInterrupt:
                logger.info("Polling loop interrupted by user")
                self.running = False
                break
            
            except Exception as e:
                logger.error(
                    "Error in polling loop",
                    error=str(e)
                )
                # Wait before retrying
                await asyncio.sleep(self.poll_interval)
        
        logger.info("Polling loop stopped")
    
    async def stop(self):
        """Stop the polling loop"""
        self.running = False
        await self.client.aclose()
        logger.info("Job poller stopped")
    
    async def send_heartbeat(self):
        """
        Send heartbeat to backend
        
        Runs periodically to indicate worker is alive
        """
        try:
            response = await self.client.post(
                f"{self.server_url}/api/v1/workers/heartbeat",
                json={
                    "worker_id": self.config.worker.id,
                    "status": "active",
                    "capabilities": [
                        {
                            "provider": cap.provider,
                            "model": cap.model
                        }
                        for cap in self.config.capabilities
                    ]
                }
            )
            
            if response.status_code == 200:
                logger.debug("Heartbeat sent successfully")
            else:
                logger.warning(
                    "Heartbeat failed",
                    status_code=response.status_code
                )
                
        except Exception as e:
            logger.error("Failed to send heartbeat", error=str(e))
    
    async def heartbeat_loop(self):
        """Background task to send periodic heartbeats"""
        while self.running:
            await self.send_heartbeat()
            await asyncio.sleep(self.config.server.heartbeat_interval)
