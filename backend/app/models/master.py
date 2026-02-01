from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid

# [v3.2] Intent Classification System
class MasterIntent(str, Enum):
    """
    v3.2 Intent 분류 체계 (5가지)
    - NATURAL: 자연어 대화 (잡담, 감사, 인사 등)
    - REQUIREMENT: 요구사항 정리 (MES 빌드)
    - FUNCTION_READ: 조회 전용 (현황, 목록, 상태)
    - FUNCTION_WRITE: 실행/변경 (DB Write, 버튼 생성)
    - CANCEL: 취소
    - TOPIC_SHIFT: 주제 변경
    """
    NATURAL = "NATURAL"
    REQUIREMENT = "REQUIREMENT"
    FUNCTION_READ = "FUNCTION_READ"
    FUNCTION_WRITE = "FUNCTION_WRITE"
    CANCEL = "CANCEL"
    TOPIC_SHIFT = "TOPIC_SHIFT"

class ConversationMode(str, Enum):
    """
    [v4.0] Conversation Mode System
    - NATURAL: 자유대화 (Blue)
    - REQUIREMENT: 기획대화 (Green) - Auto Ingestion
    - FUNCTION: 기능대화 (Purple) - Tool Execution
    """
    NATURAL = "NATURAL"
    REQUIREMENT = "REQUIREMENT"
    FUNCTION = "FUNCTION"

# [v3.2] Shadow Mining - Draft Model
class Draft(BaseModel):
    """
    Shadow Mining Draft 모델
    - 자연어 대화에서 설계 정보를 임시로 저장
    - UNVERIFIED 상태로 시작, REQUIREMENT 시 MES로 매칭
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., description="현재 세션 ID")
    user_id: str = Field(..., description="사용자 ID")
    project_id: Optional[str] = Field(None, description="연결된 프로젝트 ID")
    status: Literal["UNVERIFIED", "VERIFIED", "MERGED", "EXPIRED"] = "UNVERIFIED"
    category: Literal["환경", "목표", "산출물", "제약"] = Field(..., description="설계 정보 카테고리")
    content: str = Field(..., description="추출된 설계 정보")
    source: str = Field(default="USER_UTTERANCE", description="정보 출처")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ttl_days: int = Field(default=7, description="만료 기간 (일)")

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
    request_id: Optional[str] = None # [v4.2] Source Tracking ID

class ChatRequest(BaseModel):
    """Request for sending a message to the master agent"""
    message: str
    history: List[ChatMessage] = Field(default_factory=list)
    project_id: Optional[str] = None
    thread_id: Optional[str] = None
    worker_status: Optional[Dict[str, Any]] = None # Frontend's worker status context
    mode: ConversationMode = Field(default=ConversationMode.NATURAL, description="Current conversation mode")

class ChatResponse(BaseModel):
    """Response from the master agent"""
    message: str
    quick_links: List[dict] = Field(default_factory=list, description="List of {label, url} for quick navigation")
    mode: ConversationMode = Field(..., description="Updated conversation mode (Auto-switch result)")
