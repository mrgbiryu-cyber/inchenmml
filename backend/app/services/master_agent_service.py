import json
import asyncio
from typing import List, Dict, Any
from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from app.tools.system_tools import get_active_jobs_tool, get_job_history_tool

try:
    from langchain_community.chat_models import ChatOllama
except ImportError:
    try:
        from langchain_community.chat_models.ollama import ChatOllama
    except ImportError:
        ChatOllama = None # Fallback

from app.core.config import settings
from app.models.master import MasterAgentConfig, ChatMessage
from app.core.neo4j_client import neo4j_client

@tool
async def list_projects() -> str:
    """Lists all available projects in the system. Use this to find project IDs and names."""
    # For system master, we list projects for the main tenant
    projects = await neo4j_client.list_projects("tenant_hyungnim")
    if not projects:
        return "No projects found in the system."
    
    output = []
    for p in projects:
        output.append(f"- {p['name']} (ID: {p['id']}): {p.get('description', 'No description')}")
    return "\n".join(output)

@tool
async def get_project_details(project_id: str) -> str:
    """Gets detailed information about a specific project including its agent configuration."""
    p = await neo4j_client.get_project(project_id)
    if not p:
        return f"Project {project_id} not found."
    
    details = [
        f"Name: {p['name']}",
        f"Description: {p.get('description', 'No description')}",
        f"Type: {p.get('project_type', 'N/A')}",
        f"Repo Path: {p.get('repo_path', 'N/A')}"
    ]
    
    if p.get('agent_config'):
        details.append("\nAgent Configuration:")
        details.append(json.dumps(p['agent_config'], indent=2))
    
    return "\n".join(details)

class MasterAgentService:
    """
    Service for the System Master Agent.
    Uses LangChain to process user queries and access system tools.
    """

    def __init__(self):
        # Default config
        self.config = MasterAgentConfig()
        self.config_path = "D:/project/myllm/backend/data/master_config.json"
        self._load_config()
        
    def _load_config(self):
        """Load configuration from disk if exists"""
        import os
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = MasterAgentConfig(**data)
                    print(f"DEBUG: Master configuration loaded from {self.config_path}")
        except Exception as e:
            print(f"ERROR: Failed to load master configuration: {e}")

    def _save_config(self):
        """Save configuration to disk"""
        import os
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config.dict(), f, indent=2, ensure_ascii=False)
                print(f"DEBUG: Master configuration saved to {self.config_path}")
        except Exception as e:
            print(f"ERROR: Failed to save master configuration: {e}")

    def update_config(self, new_config: MasterAgentConfig):
        self.config = new_config
        self._save_config()

    def get_config(self) -> MasterAgentConfig:
        return self.config

    async def _trigger_self_diagnosis(self, project_id: str, thread_id: str, user: Any) -> Dict[str, Any]:
        """
        Initializes and starts the Self-Diagnosis & UX Audit workflow.
        """
        from app.models.schemas import Project, ProjectAgentConfig, AgentDefinition
        from datetime import datetime

        # 동적으로 프로젝트 ID 생성 (유저별로 고유하게 관리 가능)
        diag_project_id = f"diagnosis-{user.tenant_id}"
        p_suffix = user.tenant_id
        
        # 1. Define Diagnosis Workflow
        diag_config = ProjectAgentConfig(
            workflow_type="SEQUENTIAL",
            entry_agent_id=f"agent_architect_{p_suffix}",
            agents=[
                AgentDefinition(
                    agent_id=f"agent_architect_{p_suffix}",
                    role="Architect",
                    model="gpt-4o",
                    provider="OPENROUTER",
                    system_prompt="""파일 구조 스캔 시, 현재 메뉴 이동 flow(프로젝트 선택 -> 채팅/그래프 전환)의 라우팅 구조가 일관적인지, 순환 참조나 끊긴 링크가 없는지 UX 관점에서 분석해라.""",
                    next_agents=[f"agent_tech_qa_{p_suffix}"]
                ),
                AgentDefinition(
                    agent_id=f"agent_tech_qa_{p_suffix}",
                    role="Tech_QA",
                    model="gpt-4o",
                    provider="OPENROUTER",
                    system_prompt="""모바일 접속 시 레이아웃 깨짐, 3D 라이브러리 충돌, 그리고 사이드바-채팅창 간의 반응형 간섭 현상을 기술적으로 검수해라.""",
                    next_agents=[f"agent_reporter_{p_suffix}"]
                ),
                AgentDefinition(
                    agent_id=f"agent_reporter_{p_suffix}",
                    role="Reporter",
                    model="gpt-4o",
                    provider="OPENROUTER",
                    system_prompt="""수집된 모든 결함을 '기술 결함'과 'UX/동선 결함' 섹션으로 나누어 'D:/project/myllm/DIAGNOSIS_REPORT.md'에 기록해라. 
결과 보고서 작성 완료 후, 반드시 "보고서가 D:/project/myllm/DIAGNOSIS_REPORT.md에 저장되었습니다"라는 문구를 포함해라. 
모든 항목은 AS-IS(현재 상태) -> TO-BE(개선안) 형식을 엄수할 것.""",
                    next_agents=[]
                )
            ]
        )

        diag_project = Project(
            id=diag_project_id,
            name="MyLLM Self-Diagnosis",
            description="Automated UX Audit and Technical Health Check",
            project_type="SYSTEM",
            repo_path="D:/project/myllm",
            tenant_id=user.tenant_id,
            user_id=user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            agent_config=diag_config
        )

        # [CRITICAL] Ensure repo_path is absolutely correct for the reporter
        diag_project.repo_path = "D:/project/myllm"

        # 2. Save/Update in Neo4j
        await neo4j_client.create_project_graph(diag_project)

        # 3. Trigger Orchestration
        from app.services.job_manager import JobManager
        from app.services.orchestration_service import OrchestrationService
        import redis.asyncio as redis
        
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        job_manager = JobManager(redis_client)
        orchestrator = OrchestrationService(job_manager, redis_client)

        await orchestrator.execute_workflow(diag_project, user)

        return {
            "message": f"🔍 **[{user.username}] 님의 MyLLM 자가 진단을 시작합니다.**\n\n1. **Architect**: 라우팅 구조 분석 중...\n2. **Tech_QA**: 기술 결함 검수 대기...\n3. **Reporter**: 리포트 생성 대기...\n\n진행 상황은 LogConsole에서 실시간으로 확인 가능하며, 완료 후 프로젝트 목록에서 이 결과를 다시 보실 수 있습니다.",
            "quick_links": [{"label": "진단 프로젝트로 이동", "url": f"/projects/{diag_project_id}"}]
        }

    async def process_message(self, message: str, history: List[ChatMessage], project_id: str = None, thread_id: str = None, user: Any = None, worker_status: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a user message using the configured LLM and tools.
        """
        try:
            # [Trigger] Self-Diagnosis Workflow
            if "자가 진단 시작" in message:
                return await self._trigger_self_diagnosis(project_id, thread_id, user)

            # 1. Initialize LLM
            if self.config.provider == "OLLAMA":
                if ChatOllama is None:
                    raise ImportError("ChatOllama could not be imported from langchain_community")
                llm = ChatOllama(
                    model=self.config.model,
                    base_url="http://localhost:11434",
                    temperature=self.config.temperature,
                    timeout=30.0
                )
            else:
                llm = ChatOpenAI(
                    model=self.config.model,
                    api_key=settings.OPENROUTER_API_KEY,
                    base_url=settings.OPENROUTER_BASE_URL,
                    temperature=self.config.temperature,
                    timeout=60.0
                )

            # [IMPORTANT] Tools mapping
            tools = [list_projects, get_project_details, get_active_jobs_tool, get_job_history_tool]
            
            # 2. Construct System Prompt & Messages
            from datetime import datetime
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            system_prompt = self.config.system_prompt + f"\n\n[Current System Time]: {current_date}"
            
            if worker_status:
                system_prompt += f"\n\n[Frontend Worker Status Context]:\n{json.dumps(worker_status, indent=2, ensure_ascii=False)}"
            
            final_messages = [SystemMessage(content=system_prompt)]
            
            # 3. Merge History (Neo4j + Session)
            all_history_msgs = []
            
            # 3a. Try DB history first
            if project_id:
                try:
                    db_history = await neo4j_client.get_chat_history(project_id, limit=10)
                    for msg in db_history:
                        role = msg.get("role")
                        content = msg.get("content")
                        if role == "user":
                            all_history_msgs.append(HumanMessage(content=content))
                        elif role == "assistant":
                            all_history_msgs.append(AIMessage(content=content))
                except Exception as history_e:
                    print(f"DEBUG: Failed to load DB history: {history_e}")

            # 3b. Add Session History (avoid duplicates)
            session_msgs = []
            windowed_history = history[-10:] if len(history) > 10 else history
            for msg in windowed_history:
                if msg.role == "user":
                    session_msgs.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    session_msgs.append(AIMessage(content=msg.content))
            
            # Simple merge: If session has messages, assume they are more recent/contextual
            # If session is empty (refresh), DB messages are used.
            if session_msgs:
                # To be robust, we could compare contents, but for now we prioritize session
                final_messages.extend(session_msgs)
            else:
                final_messages.extend(all_history_msgs)
            
            final_messages.append(HumanMessage(content=message))

            # 4. Save User Message
            if project_id:
                asyncio.create_task(neo4j_client.save_chat_message(
                    project_id, "user", message, 
                    thread_id=thread_id, user_id=user.id if user else "system"
                ))

            # 5. Invoke LLM with Tools
            try:
                llm_with_tools = llm.bind_tools(tools)
                response = await llm_with_tools.ainvoke(final_messages)
                
                loop_count = 0
                while hasattr(response, 'tool_calls') and response.tool_calls and loop_count < 5:
                    final_messages.append(response)
                    for tool_call in response.tool_calls:
                        t_name = tool_call["name"]
                        t_args = tool_call["args"]
                        t_id = tool_call["id"]
                        
                        print(f"DEBUG: [MASTER_TOOL] {t_name}({t_args})")
                        
                        if t_name == "list_projects":
                            t_out = await list_projects.ainvoke(t_args)
                        elif t_name == "get_project_details":
                            t_out = await get_project_details.ainvoke(t_args)
                        elif t_name == "get_active_jobs_tool":
                            t_out = await get_active_jobs_tool.ainvoke(t_args)
                        elif t_name == "get_job_history_tool":
                            t_out = await get_job_history_tool.ainvoke(t_args)
                        else:
                            t_out = f"Tool {t_name} not found"
                        
                        final_messages.append(ToolMessage(content=str(t_out), tool_call_id=t_id))
                    
                    response = await llm.ainvoke(final_messages)
                    loop_count += 1
                
                response_text = response.content
            except Exception as e:
                print(f"DEBUG: Master tool invoke failed: {e}")
                final_resp = await llm.ainvoke(final_messages)
                response_text = final_resp.content

            # 6. Save Assistant Message
            if project_id:
                asyncio.create_task(neo4j_client.save_chat_message(
                    project_id, "assistant", response_text, 
                    thread_id=thread_id, user_id=user.id if user else "system"
                ))

            return {
                "message": response_text,
                "quick_links": []
            }
            
        except Exception as global_e:
            import traceback
            traceback.print_exc()
            return {
                "message": f"죄송합니다. 오류가 발생했습니다: {str(global_e)}",
                "quick_links": []
            }

    async def create_job_from_history(self, history: List[ChatMessage], orchestrator: Any, user: Any) -> Dict[str, Any]:
        return {"message": "Job creation from history not implemented yet."}
