import asyncio
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from app.core.config import settings
from app.models.schemas import AgentDefinition

class AgentTestService:
    """
    Service to test individual agents or groups of agents.
    """
    
    async def test_agent(self, agent: AgentDefinition, message: str) -> Dict[str, Any]:
        """Run a single message through an agent and return its response."""
        try:
            if agent.provider == "OLLAMA":
                llm = ChatOllama(
                    model=agent.model,
                    base_url="http://localhost:11434",
                    temperature=0.7
                )
            else:
                llm = ChatOpenAI(
                    model=agent.model,
                    api_key=settings.OPENROUTER_API_KEY,
                    base_url=settings.OPENROUTER_BASE_URL,
                    temperature=0.7
                )
            
            prompt = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": message}
            ]
            
            response = await llm.ainvoke(prompt)
            return {
                "agent_id": agent.agent_id,
                "role": agent.role,
                "response": response.content,
                "status": "success"
            }
        except Exception as e:
            return {
                "agent_id": agent.agent_id,
                "role": agent.role,
                "response": str(e),
                "status": "error"
            }

    async def test_agent_group(self, agents: List[AgentDefinition], message: str) -> List[Dict[str, Any]]:
        """Run a message through multiple agents in parallel."""
        tasks = [self.test_agent(agent, message) for agent in agents]
        return await asyncio.gather(*tasks)

agent_test_service = AgentTestService()
