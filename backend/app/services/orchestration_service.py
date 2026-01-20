import asyncio
import json
from typing import Dict, Any, List
from uuid import UUID

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.models.schemas import (
    Project, 
    ProjectAgentConfig, 
    AgentDefinition, 
    JobCreate, 
    ExecutionLocation, 
    ProviderType, 
    JobStatus,
    User
)
from app.services.job_manager import JobManager
from app.services.agent_config_service import AgentState

class OrchestrationService:
    """
    Orchestrates the execution of multi-agent workflows using LangGraph and JobManager.
    """
    
    def __init__(self, job_manager: JobManager, redis_client=None):
        self.job_manager = job_manager
        self.redis_client = redis_client

    async def execute_workflow(self, project: Project, user: User) -> str:
        """
        Start the workflow execution for a project.
        """
        if not project.agent_config:
            raise ValueError("Project has no agent configuration")

        # Build the graph
        workflow = self._build_langgraph(project, user)
        
        # Initialize state
        initial_state = AgentState(
            messages=[HumanMessage(content=f"Start workflow for project: {project.name}")],
            current_agent="START",
            next_agent=project.agent_config.entry_agent_id,
            artifacts={},
            ux_issues=[] # Initialize ux_issues tracker
        )
        
        # Run the workflow (Async)
        asyncio.create_task(self._run_workflow(workflow, initial_state, project.id))
        
        return "Workflow started"

    async def _run_workflow(self, workflow, initial_state, project_id):
        """Run workflow and handle events"""
        try:
            await self._publish_event(project_id, "WORKFLOW_STARTED", {"status": "STARTED"})
            await workflow.ainvoke(initial_state)
            await self._publish_event(project_id, "WORKFLOW_COMPLETED", {"status": "COMPLETED"})
        except Exception as e:
            print(f"Workflow failed: {e}")
            await self._publish_event(project_id, "WORKFLOW_FAILED", {"error": str(e)})

    async def _publish_event(self, project_id: str, event_type: str, data: Dict[str, Any]):
        """Publish event to Redis"""
        if self.redis_client:
            message = {
                "type": event_type,
                "project_id": project_id,
                "data": data,
                "timestamp": asyncio.get_event_loop().time()
            }
            await self.redis_client.publish(f"orchestration:{project_id}", json.dumps(message))

    def _build_langgraph(self, project: Project, user: User):
        """
        Build the StateGraph with nodes that dispatch jobs
        """
        print(f"DEBUG: Building LangGraph for Project: {project.id}")
        workflow = StateGraph(AgentState)
        config = project.agent_config
        
        if not config or not config.agents:
            raise ValueError(f"Project {project.id} has no agents configured")

        agent_ids = [a.agent_id for a in config.agents]
        print(f"DEBUG: Configured Agents: {agent_ids}")
        
        # Add nodes
        for agent in config.agents:
            workflow.add_node(agent.agent_id, self._create_agent_node(agent, project, user))
            
        # Add edges
        for agent in config.agents:
            if not agent.next_agents:
                print(f"DEBUG: Adding edge {agent.agent_id} -> END")
                workflow.add_edge(agent.agent_id, END)
            else:
                for next_id in agent.next_agents:
                    if next_id not in agent_ids:
                        print(f"DEBUG: WARNING - Next agent {next_id} not found in agent list. Connecting to END instead.")
                        workflow.add_edge(agent.agent_id, END)
                    else:
                        print(f"DEBUG: Adding edge {agent.agent_id} -> {next_id}")
                        workflow.add_edge(agent.agent_id, next_id)
                    
        # Set entry point
        if config.entry_agent_id not in agent_ids:
            print(f"DEBUG: WARNING - Entry agent {config.entry_agent_id} not found. Using {agent_ids[0]} as fallback.")
            workflow.set_entry_point(agent_ids[0])
        else:
            workflow.set_entry_point(config.entry_agent_id)
        
        print(f"DEBUG: Compiling workflow for {project.id}...")
        return workflow.compile()

    def _create_agent_node(self, agent_def: AgentDefinition, project: Project, user: User):
        """
        Create a runnable node that dispatches a job to the Worker
        """
        async def agent_node(state: AgentState):
            print(f"🚀 [Orchestrator] Executing Agent: {agent_def.agent_id} ({agent_def.role})")
            await self._publish_event(project.id, "AGENT_STARTED", {"agent_id": agent_def.agent_id, "role": agent_def.role})
            
            # 1. Create Job Request
            # Robust provider mapping
            try:
                provider_val = agent_def.provider.upper()
                if provider_val == "OLLAMA":
                    p_type = ProviderType.OLLAMA
                elif provider_val == "OPENROUTER":
                    p_type = ProviderType.OPENROUTER
                else:
                    p_type = ProviderType[provider_val]
            except Exception:
                print(f"DEBUG: Unknown provider {agent_def.provider}. Defaulting to OLLAMA.")
                p_type = ProviderType.OLLAMA

            job_request = JobCreate(
                execution_location=ExecutionLocation.LOCAL_MACHINE,
                provider=p_type,
                model=agent_def.model,
                repo_root=project.repo_path if project.repo_path else "D:/project/myllm", # Fallback injection
                allowed_paths=[project.repo_path] if project.repo_path else ["D:/project/myllm"],
                steps=[f"Execute role: {agent_def.role}", "Check TASK.md"],
                metadata={
                    "project_id": project.id,
                    "agent_id": agent_def.agent_id,
                    "role": agent_def.role,
                    "system_prompt": agent_def.system_prompt,
                    "current_ux_issues": state.get("ux_issues", []) # Pass accumulated context
                }
            )
            
            # 2. Dispatch Job via JobManager
            try:
                job = await self.job_manager.create_job(user, job_request)
                print(f"   ✅ Job Created: {job.job_id}")
                await self._publish_event(project.id, "JOB_CREATED", {"agent_id": agent_def.agent_id, "job_id": str(job.job_id)})
            except Exception as e:
                print(f"   ❌ Job Creation Failed: {e}")
                await self._publish_event(project.id, "AGENT_FAILED", {"agent_id": agent_def.agent_id, "error": str(e)})
                return {"messages": [AIMessage(content=f"Job creation failed: {e}")]}

            # 3. Wait for Job Completion (Polling)
            # In production, use Redis Pub/Sub or Webhooks
            job_id = str(job.job_id)
            result = None
            
            while True:
                status_data = await self.job_manager.get_job_status(job_id, user)
                status = status_data["status"]
                
                if status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                    result = status_data.get("result")
                    break
                
                await asyncio.sleep(2) # Poll every 2 seconds
                
            # 4. Process Result
            if status == JobStatus.COMPLETED.value:
                print(f"   🎉 Job Completed: {job_id}")
                output = result.get("output", {}) if result else {}
                
                # Extract UX Issues if reported by agent
                new_ux_issues = output.get("ux_issues", [])
                
                await self._publish_event(project.id, "AGENT_COMPLETED", {"agent_id": agent_def.agent_id, "output": output})
                return {
                    "current_agent": agent_def.agent_id,
                    "messages": [AIMessage(content=f"Agent {agent_def.agent_id} completed task.")],
                    "artifacts": {**state.get("artifacts", {}), agent_def.agent_id: output},
                    "ux_issues": new_ux_issues # LangGraph will add these due to operator.add
                }
            else:
                print(f"   ⚠️ Job Failed: {job_id}")
                await self._publish_event(project.id, "AGENT_FAILED", {"agent_id": agent_def.agent_id, "error": "Job failed"})
                return {
                    "current_agent": agent_def.agent_id,
                    "messages": [AIMessage(content=f"Agent {agent_def.agent_id} failed.")]
                }
            
        return agent_node
