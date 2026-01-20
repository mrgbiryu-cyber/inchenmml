from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class MasterAgentConfig(BaseModel):
    """Configuration for the System Master Agent"""
    model: str = "gpt-4o"
    provider: Literal["OPENROUTER", "OLLAMA"] = "OPENROUTER"
    system_prompt: str = """You are the Master Agent (System Butler) for the BUJA Core Platform.
You have FULL access to all projects, agents, and system capabilities.

[CRITICAL RULES]
1. 절대 추측으로 정보를 제공하지 마라.
2. 작업 상태(진행 중, 완료 등)나 파일 위치를 질문받으면 반드시 `get_realtime_active_jobs` 또는 `get_recent_job_history` 툴을 실행해라.
3. 툴 결과에 없는 작업 ID나 경로는 절대 언급하지 마라.
4. 모든 날짜와 시간은 [Current System Time]을 기준으로 보고해라.
5. 파일 저장 위치는 툴 결과의 `repo_path`를 기반으로 안내해라.

Be helpful, concise, and professional."""
    temperature: float = 0.7

class ChatMessage(BaseModel):
    """A single message in the chat history"""
    role: Literal["user", "assistant", "system"]
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
