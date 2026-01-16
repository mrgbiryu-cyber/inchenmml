"""
Job Executor for Local Worker
Executes jobs safely with path validation and TASK.md generation
"""
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import time
import subprocess
import httpx
from structlog import get_logger

from local_agent_hub.core.config import WorkerConfig
from local_agent_hub.core.security import (
    validate_job_paths,
    validate_path,
    SecurityError
)

logger = get_logger(__name__)


class JobExecutor:
    """
    Executes jobs with safety checks and Roo Code integration
    
    Process:
    1. Validate repo_root exists
    2. Validate all file paths
    3. Generate TASK.md
    4. Trigger Roo Code (simulated)
    5. Wait for completion
    6. Collect results
    7. Upload to backend
    """
    
    def __init__(self, config: WorkerConfig):
        """
        Initialize Job Executor
        
        Args:
            config: Worker configuration
        """
        self.config = config
        self.server_url = config.server.url
        self.worker_token = config.server.worker_token
        
        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),
            headers={
                "Authorization": f"Bearer {self.worker_token}",
                "User-Agent": f"BUJA-Worker/{config.worker.id}"
            }
        )
    
    async def execute_job(self, job: Dict[str, Any]) -> None:
        """
        Execute a job
        
        Args:
            job: Job dictionary (already signature-verified)
        """
        job_id = job.get('job_id')
        repo_root = job.get('repo_root')
        
        logger.info(
            "Starting job execution",
            job_id=job_id,
            repo_root=repo_root
        )
        
        start_time = time.time()
        
        try:
            # Step 1: Validate repo_root exists
            if not repo_root:
                raise SecurityError("Job missing repo_root")
            
            repo_path = Path(repo_root)
            if not repo_path.exists():
                raise SecurityError(f"repo_root does not exist: {repo_root}")
            
            if not repo_path.is_dir():
                raise SecurityError(f"repo_root is not a directory: {repo_root}")
            
            logger.info("✅ repo_root validated", repo_root=repo_root)
            
            # Step 2: Validate all file paths
            validate_job_paths(job)
            logger.info("✅ All paths validated")
            
            # Step 3: Generate TASK.md
            task_md_path = await self.generate_task_md(job, repo_path)
            logger.info("✅ TASK.md generated", path=str(task_md_path))
            
            # Step 4: Simulate Roo Code execution
            # In production, this would trigger actual Roo Code
            await self.simulate_roo_code_execution(job, repo_path)
            logger.info("✅ Roo Code execution completed (simulated)")
            
            # Step 5: Collect results
            result = await self.collect_results(job, repo_path, start_time)
            logger.info("✅ Results collected")
            
            # Step 6: Upload result to backend
            await self.upload_result(job_id, "COMPLETED", result)
            logger.info("✅ Result uploaded to backend")
            
            # Step 7: Cleanup
            await self.cleanup_artifacts(repo_path)
            logger.info("✅ Cleanup completed")
            
        except SecurityError as e:
            logger.error(
                "🔒 Security violation during execution",
                job_id=job_id,
                error=str(e)
            )
            await self.upload_result(
                job_id,
                "FAILED",
                {"error": str(e), "error_type": "SECURITY_VIOLATION"}
            )
        
        except Exception as e:
            logger.error(
                "Job execution failed",
                job_id=job_id,
                error=str(e)
            )
            await self.upload_result(
                job_id,
                "FAILED",
                {"error": str(e), "error_type": "EXECUTION_ERROR"}
            )
    
    async def generate_task_md(self, job: Dict[str, Any], repo_path: Path) -> Path:
        """
        Generate TASK.md from job specification
        
        Follows template from INTEGRATIONS_AND_OPS.md Section 7.2
        
        Args:
            job: Job dictionary
            repo_path: Repository root path
            
        Returns:
            Path to generated TASK.md
        """
        task_file = self.config.execution.roo_code.task_file
        task_path = repo_path / task_file
        
        # Extract metadata
        metadata = job.get('metadata', {})
        objective = metadata.get('objective', 'No objective specified')
        requirements = metadata.get('requirements', [])
        success_criteria = metadata.get('success_criteria', [])
        language = metadata.get('language', 'Python')
        framework = metadata.get('framework', 'FastAPI')
        code_style = metadata.get('code_style', 'Black + isort')
        notes = metadata.get('notes', 'No additional notes')
        
        # Format file operations
        file_ops_text = self._format_file_operations(job.get('file_operations', []))
        
        # Format requirements
        requirements_text = self._format_requirements(requirements)
        
        # Format success criteria
        success_text = self._format_success_criteria(success_criteria)
        
        # Generate TASK.md content
        task_content = f"""# CODING TASK
**Generated by**: BUJA Core Platform  
**Job ID**: `{job.get('job_id')}`  
**Created**: {job.get('created_at_ts')}  
**Timeout**: {job.get('timeout_sec')}s  

---

## 🎯 Objective
{objective}

## 📋 Requirements

{requirements_text}

## 📁 Files to Modify

{file_ops_text}

## ⚙️ Technical Constraints

- **Language**: {language}
- **Framework**: {framework}
- **Code Style**: {code_style}
- **Type Hints**: Required for all functions
- **Docstrings**: Google style

## 🚫 Restrictions

- Do NOT modify files outside: `{job.get('allowed_paths')}`
- Do NOT import external packages (unless in requirements.txt)
- Do NOT connect to external services

## ✅ Success Criteria

{success_text}

## 📝 Implementation Notes

{notes}

---

**IMPORTANT**: When complete, create file: `.roo_completed`

**This task is digitally signed and verified. Do not modify this file.**
"""
        
        # Write TASK.md
        task_path.write_text(task_content, encoding='utf-8')
        
        return task_path
    
    def _format_file_operations(self, operations: list) -> str:
        """Format file operations as markdown list"""
        if not operations:
            return "- *(No specific file operations)*"
        
        lines = []
        for op in operations:
            action = op.get('action', 'MODIFY')
            path = op.get('path', '')
            description = op.get('description', '')
            
            emoji = {"CREATE": "🆕", "MODIFY": "✏️", "DELETE": "🗑️"}.get(action, "❓")
            lines.append(f"{emoji} **{action}** `{path}`")
            
            if description:
                lines.append(f"   └─ {description}")
        
        return "\n".join(lines)
    
    def _format_requirements(self, requirements: list) -> str:
        """Format requirements as numbered list"""
        if not requirements:
            return "*(No specific requirements)*"
        
        return "\n".join(f"{i+1}. {req}" for i, req in enumerate(requirements))
    
    def _format_success_criteria(self, criteria: list) -> str:
        """Format success criteria as checklist"""
        if not criteria:
            return "- [ ] Task completed"
        
        return "\n".join(f"- [ ] {c}" for c in criteria)
    
    async def simulate_roo_code_execution(self, job: Dict[str, Any], repo_path: Path) -> None:
        """
        Simulate Roo Code execution
        
        In production, this would:
        1. Trigger Roo Code via CLI or file watcher
        2. Wait for .roo_completed marker
        
        For now, we simulate by:
        1. Waiting a short time
        2. Creating .roo_completed marker
        
        Args:
            job: Job dictionary
            repo_path: Repository root path
        """
        completion_marker = self.config.execution.roo_code.completion_marker
        marker_path = repo_path / completion_marker
        
        # Simulate execution time
        timeout = job.get('timeout_sec', 60)
        simulated_time = min(5, timeout)  # Simulate 5 seconds or less
        
        logger.info(
            f"Simulating Roo Code execution ({simulated_time}s)...",
            job_id=job.get('job_id')
        )
        
        await asyncio.sleep(simulated_time)
        
        # Create completion marker
        marker_content = {
            "job_id": job.get('job_id'),
            "completed_at": int(time.time()),
            "status": "success"
        }
        
        import json
        marker_path.write_text(json.dumps(marker_content, indent=2), encoding='utf-8')
        
        logger.info("✅ Completion marker created", path=str(marker_path))
    
    async def collect_results(
        self,
        job: Dict[str, Any],
        repo_path: Path,
        start_time: float
    ) -> Dict[str, Any]:
        """
        Collect execution results
        
        Args:
            job: Job dictionary
            repo_path: Repository root path
            start_time: Job start timestamp
            
        Returns:
            Result dictionary
        """
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Try to get git diff
        diff = ""
        modified_files = []
        
        try:
            # Get git diff
            diff_result = subprocess.run(
                ['git', 'diff', '--unified=3', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            diff = diff_result.stdout
            
            # Get modified files
            files_result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            modified_files = [f for f in files_result.stdout.strip().split('\n') if f]
            
        except subprocess.SubprocessError as e:
            logger.warning(f"Git diff failed: {e}")
            diff = "(Git diff unavailable - no git repository)"
        except FileNotFoundError:
            logger.warning("Git not found")
            diff = "(Git not installed)"
        
        return {
            "status": "COMPLETED",
            "output": {
                "diff": diff,
                "files_modified": modified_files,
                "execution_time_ms": execution_time_ms,
                "execution_log": "Simulated execution completed successfully"
            },
            "metrics": {
                "lines_added": diff.count('\n+') if diff else 0,
                "lines_removed": diff.count('\n-') if diff else 0,
                "files_touched": len(modified_files)
            }
        }
    
    async def upload_result(
        self,
        job_id: str,
        status: str,
        result: Dict[str, Any]
    ) -> None:
        """
        Upload job result to backend
        
        Args:
            job_id: Job identifier
            status: Job status (COMPLETED | FAILED)
            result: Result dictionary
        """
        try:
            response = await self.client.post(
                f"{self.server_url}/api/v1/jobs/{job_id}/result",
                json={
                    "status": status,
                    "output": result.get('output'),
                    "error": result.get('error'),
                    "execution_time_ms": result.get('output', {}).get('execution_time_ms'),
                    "metrics": result.get('metrics')
                }
            )
            
            if response.status_code == 200:
                logger.info(
                    "Result uploaded successfully",
                    job_id=job_id,
                    status=status
                )
            else:
                logger.error(
                    "Failed to upload result",
                    job_id=job_id,
                    status_code=response.status_code,
                    response=response.text
                )
                
        except Exception as e:
            logger.error(
                "Error uploading result",
                job_id=job_id,
                error=str(e)
            )
    
    async def cleanup_artifacts(self, repo_path: Path) -> None:
        """
        Remove temporary files after job completion
        
        Args:
            repo_path: Repository root path
        """
        task_file = self.config.execution.roo_code.task_file
        marker_file = self.config.execution.roo_code.completion_marker
        
        for filename in [task_file, marker_file]:
            file_path = repo_path / filename
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Deleted: {filename}")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
