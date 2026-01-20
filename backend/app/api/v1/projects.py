from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from datetime import datetime
import uuid

from app.models.schemas import Project, ProjectAgentConfig, User, AgentDefinition, ProjectCreate
from app.api.dependencies import get_current_user
from app.core.neo4j_client import neo4j_client

router = APIRouter()

@router.post("/", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new project"""
    project_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    # Create new project instance
    new_project = Project(
        id=project_id,
        name=project_in.name,
        description=project_in.description,
        project_type=project_in.project_type,
        repo_path=project_in.repo_path,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        created_at=now,
        updated_at=now,
        agent_config=project_in.agent_config
    )

    # Inject Default Agents if none provided
    if not new_project.agent_config:
        # Use project_id prefix to make agent IDs unique to this project
        p_prefix = project_id[:8]
        new_project.agent_config = ProjectAgentConfig(
            workflow_type="SEQUENTIAL",
            entry_agent_id=f"agent_planner_{p_prefix}",
            agents=[
                AgentDefinition(
                    agent_id=f"agent_planner_{p_prefix}",
                    role="PLANNER",
                    model="mimo-v2-flash",
                    provider="OLLAMA",
                    system_prompt="You are a Master Planner. Break down tasks into steps.",
                    next_agents=[f"agent_coder_{p_prefix}"]
                ),
                AgentDefinition(
                    agent_id=f"agent_coder_{p_prefix}",
                    role="CODER",
                    model="mimo-v2-flash",
                    provider="OLLAMA",
                    system_prompt="You are a Senior Coder. Write clean, efficient code.",
                    next_agents=[f"agent_reviewer_{p_prefix}"]
                ),
                AgentDefinition(
                    agent_id=f"agent_reviewer_{p_prefix}",
                    role="REVIEWER",
                    model="mimo-v2-flash",
                    provider="OLLAMA",
                    system_prompt="You are a Code Reviewer. Check for bugs and style.",
                    next_agents=[]
                )
            ]
        )
        print(f"DEBUG: Injected unique default agents for project {project_id}")
    
    # Save to Neo4j
    await neo4j_client.create_project_graph(new_project)
    
    return new_project

@router.get("/", response_model=List[Project])
async def list_projects(
    current_user: User = Depends(get_current_user)
):
    """List all projects for the current user's tenant"""
    # Filter by tenant_id in Neo4j
    projects_data = await neo4j_client.list_projects(current_user.tenant_id)
    return [Project(**p) for p in projects_data]

@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get project details"""
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access (Tenant isolation)
    if project_data["tenant_id"] != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
        
    return Project(**project_data)

@router.patch("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    project_update: dict, # Using dict for partial update
    current_user: User = Depends(get_current_user)
):
    """Update project"""
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project_id != "system-master" and project_data["tenant_id"] != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Update fields
    for key, value in project_update.items():
        if key in project_data and key not in ["id", "tenant_id", "user_id", "created_at"]:
            project_data[key] = value
            
    project_data["updated_at"] = datetime.utcnow()
    updated_project = Project(**project_data)
    
    await neo4j_client.create_project_graph(updated_project)
    
    return updated_project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete project"""
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project_id != "system-master" and project_data["tenant_id"] != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    await neo4j_client.delete_project(project_id)
    return None

@router.post("/{project_id}/agents", response_model=Project)
async def save_agent_config(
    project_id: str,
    config: ProjectAgentConfig,
    current_user: User = Depends(get_current_user)
):
    """Save agent configuration for a project"""
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project_id != "system-master" and project_data["tenant_id"] != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    project_data["agent_config"] = config
    project_data["updated_at"] = datetime.utcnow()
    
    project_obj = Project(**project_data)
    await neo4j_client.create_project_graph(project_obj)
    
    return project_obj

@router.get("/{project_id}/agents", response_model=ProjectAgentConfig)
async def get_agent_config(
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get agent configuration for a project"""
    print(f"DEBUG: GET Agent Config for Project: {project_id}")
    
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    # Check access
    if project_id != "system-master" and project_data["tenant_id"] != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    if not project_data.get("agent_config"):
        # Return default config to allow editor to start with something
        return ProjectAgentConfig(
            workflow_type="SEQUENTIAL",
            entry_agent_id="agent_planner",
            agents=[
                AgentDefinition(
                    agent_id="agent_planner",
                    role="PLANNER",
                    model="mimo-v2-flash",
                    provider="OLLAMA",
                    system_prompt="You are a Master Planner.",
                    next_agents=["agent_coder"]
                ),
                AgentDefinition(
                    agent_id="agent_coder",
                    role="CODER",
                    model="mimo-v2-flash",
                    provider="OLLAMA",
                    system_prompt="You are a Senior Coder.",
                    next_agents=[]
                )
            ]
        )
        
    return ProjectAgentConfig(**project_data["agent_config"])


@router.post("/{project_id}/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_project(
    request: Request,
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Start project execution workflow
    """
    print(f"DEBUG: Starting execution for Project: {project_id}")
    try:
        project_data = await neo4j_client.get_project(project_id)
        if not project_data:
            print(f"DEBUG: Project {project_id} not found in Neo4j")
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check access (Tenant isolation)
        if project_id != "system-master" and project_data["tenant_id"] != current_user.tenant_id:
            print(f"DEBUG: Unauthorized access attempt to project {project_id} by user {current_user.id}")
            raise HTTPException(status_code=403, detail="Not authorized to access this project")
            
        project = Project(**project_data)
        
        # [Defensive] Inject repo_path for system-master if missing
        if project_id == "system-master" and (not project.repo_path or project.repo_path == ""):
            print(f"DEBUG: Injecting default repo_path for {project_id}")
            project.repo_path = "D:/project/myllm"
        
        if not project.agent_config:
            print(f"DEBUG: Project {project_id} has no agent config")
            raise HTTPException(status_code=400, detail="Project has no agent configuration")

        # Initialize Orchestrator
        job_manager = request.app.state.job_manager
        redis_client = request.app.state.redis
        
        from app.services.orchestration_service import OrchestrationService
        orchestrator = OrchestrationService(job_manager, redis_client)
        
        # Start execution
        execution_id = await orchestrator.execute_workflow(project, current_user)
        print(f"DEBUG: Workflow started for {project_id}. ID: {execution_id}")
        return {"message": "Workflow started", "execution_id": execution_id}
    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        import traceback
        print(f"ERROR: Execution failed for {project_id}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/test-agents")
async def test_agents(
    project_id: str,
    payload: dict, # {message: str, agent_ids: List[str]}
    current_user: User = Depends(get_current_user)
):
    """Test a group of agents in a project"""
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project_data.get("agent_config"):
        raise HTTPException(status_code=400, detail="Project has no agent configuration")
    
    message = payload.get("message")
    agent_ids = payload.get("agent_ids", [])
    
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Filter agents to test
    agents_to_test = [
        AgentDefinition(**a) for a in project_data["agent_config"]["agents"]
        if a["agent_id"] in agent_ids
    ]
    
    if not agents_to_test:
        raise HTTPException(status_code=400, detail="No valid agents selected for testing")
    
    from app.services.agent_test_service import agent_test_service
    results = await agent_test_service.test_agent_group(agents_to_test, message)
    
    return results

@router.get("/{project_id}/chat-history", response_model=List[dict])
async def get_chat_history(
    project_id: str,
    limit: int = 50,
    thread_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get chat history for a project"""
    project_data = await neo4j_client.get_project(project_id)
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project_id != "system-master" and project_data["tenant_id"] != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    messages = await neo4j_client.get_chat_history(project_id, limit, thread_id=thread_id)
    return messages
