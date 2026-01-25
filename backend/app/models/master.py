from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class MasterAgentConfig(BaseModel):
    """Configuration for the System Master Agent"""
    model: str = "google/gemini-2.0-flash-001"
    provider: Literal["OPENROUTER", "OLLAMA"] = "OPENROUTER"
    system_prompt: str = """[CRITICAL: ALWAYS RESPOND IN KOREAN]
당신은 BUJA Core 플랫폼의 총괄 지휘관(Supreme Commander)입니다.
사용자의 지시사항에 따라 전략을 설계하고 에이전트를 조율하십시오.
모든 답변은 반드시 한국어로 작성해야 합니다.
"""
    temperature: float = 0.7

class AgentConfigUpdate(BaseModel):
    """Precision commanding model for agent configuration updates"""
    repo_root: Optional[str] = Field(None, description="The absolute path to the repository root on the local machine.")
    tool_allowlist: Optional[List[str]] = Field(None, description="List of allowed tools for the agent. Available tools: read_file, write_file, list_dir, execute_command, git_push, git_pull, git_commit, npm_test, pytest.")
    next_agents: Optional[List[str]] = Field(None, description="List of agent IDs to execute after this agent (for workflow connection).")
    system_prompt: Optional[str] = Field(None, description="The system prompt defining the agent's behavior.")
    model: Optional[str] = Field(None, description="The LLM model to use (e.g., google/gemini-2.0-flash-001, claude-3-5-sonnet).")
    provider: Optional[str] = Field(None, description="LLM Provider: OPENROUTER or OLLAMA.")

class ChatMessage(BaseModel):
    """A single message in the chat history"""
    role: str = Field(..., description="user | assistant | system")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    """Request for sending a message to the master agent"""
    message: str
    history: List[ChatMessage] = Field(default_factory=list)
    project_id: Optional[str] = None
    thread_id: Optional[str] = None
    worker_status: Optional[Dict[str, Any]] = None # Frontend's worker status context

class ChatResponse(BaseModel):
    """Response from the master agent"""
    message: str
    quick_links: List[dict] = Field(default_factory=list, description="List of {label, url} for quick navigation")
