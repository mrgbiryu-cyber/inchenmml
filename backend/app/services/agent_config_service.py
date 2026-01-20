from typing import Dict, Any, TypedDict, Annotated, List, Union
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage

from app.models.schemas import ProjectAgentConfig, AgentDefinition, Project
from app.core.neo4j_client import neo4j_client

# Define Agent State
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    current_agent: str
    next_agent: str
    artifacts: Dict[str, Any]
    ux_issues: Annotated[List[Dict[str, str]], operator.add] # UX audit results tracker

class AgentConfigService:
    """
    Service to manage agent configurations and build LangGraph workflows
    """
    
    async def save_agent_config(self, project: Project, config: ProjectAgentConfig) -> None:
        """
        Save agent configuration to Neo4j
        """
        # Update project object with new config
        project.agent_config = config
        
        # Save to Neo4j
        if await neo4j_client.verify_connectivity():
            await neo4j_client.create_project_graph(project)
        else:
            print("Warning: Neo4j not connected. Config saved to memory/mock DB only.")

    async def load_agent_config(self, project_id: str) -> ProjectAgentConfig:
        """
        Load agent configuration from Neo4j (or fallback to Project model if not using Neo4j for retrieval yet)
        """
        # Ideally we fetch from Neo4j, but for now we rely on the Project object passed around or Mock DB
        # This method might be useful if we want to reconstruct config from Graph
        agents_data = await neo4j_client.get_project_agents(project_id)
        if not agents_data:
            return None
            
        # Reconstruct ProjectAgentConfig
        # This is complex because we need entry_agent_id and workflow_type which might be on Project node
        # For Phase 2, we primarily use the Mock DB in projects.py for persistence, 
        # and Neo4j for graph visualization/analytics.
        pass

    def build_langgraph_workflow(self, config: ProjectAgentConfig):
        """
        Build a LangGraph StateGraph from the configuration
        """
        workflow = StateGraph(AgentState)
        
        # Add nodes
        for agent in config.agents:
            workflow.add_node(agent.agent_id, self._create_agent_node(agent))
            
        # Add edges
        for agent in config.agents:
            if not agent.next_agents:
                workflow.add_edge(agent.agent_id, END)
            else:
                for next_id in agent.next_agents:
                    workflow.add_edge(agent.agent_id, next_id)
                    
        # Set entry point
        workflow.set_entry_point(config.entry_agent_id)
        
        return workflow.compile()

    def _create_agent_node(self, agent_def: AgentDefinition):
        """
        Create a runnable node for the agent
        """
        async def agent_node(state: AgentState):
            # This is a placeholder for actual agent execution
            # In Phase 3, we will integrate LLM calls here
            print(f"Executing Agent: {agent_def.agent_id} ({agent_def.role})")
            
            # Simulate processing
            return {
                "current_agent": agent_def.agent_id,
                # "messages": [AIMessage(content=f"Processed by {agent_def.agent_id}")]
            }
            
        return agent_node

# Global instance
agent_config_service = AgentConfigService()
