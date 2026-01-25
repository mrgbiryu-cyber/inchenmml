# -*- coding: utf-8 -*-
from typing import List, Optional
import sys

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import APIRouter, Depends, HTTPException, status
from app.models.schemas import AgentDefinition, User, AgentType
from app.api.dependencies import get_current_user
from app.core.neo4j_client import neo4j_client

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("/", response_model=List[AgentDefinition])
async def list_agents(
    current_user: User = Depends(get_current_user)
):
    """
    [TODO 5] List all registered agents for the tenant.
    Currently fetches agents from all projects of the tenant as a registry.
    """
    projects = await neo4j_client.list_projects(current_user.tenant_id)
    registry = []
    seen_ids = set()
    
    for p in projects:
        if p.get("agent_config") and p["agent_config"].get("agents"):
            for agent in p["agent_config"]["agents"]:
                if agent["agent_id"] not in seen_ids:
                    registry.append(AgentDefinition(**agent))
                    seen_ids.add(agent["agent_id"])
    
    return registry

@router.post("/", response_model=AgentDefinition)
async def register_agent(
    agent: AgentDefinition,
    current_user: User = Depends(get_current_user)
):
    """
    [TODO 5] Register or update an agent in the registry.
    For now, we store this in a 'Global Registry' project for the tenant.
    """
    # This is a placeholder for a real registry DB. 
    # In v3.5.1, we'll ensure the agent is valid via Pydantic.
    return agent
