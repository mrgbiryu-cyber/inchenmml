# -*- coding: utf-8 -*-
import json
import asyncio
import sys

# [UTF-8] Force stdout/stderr to UTF-8 at service level
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage, BaseMessage
from langchain_openai import ChatOpenAI
from app.tools.system_tools import get_active_jobs_tool, get_job_history_tool

from app.core.config import settings
from app.models.master import MasterAgentConfig, ChatMessage, AgentConfigUpdate
from app.core.neo4j_client import neo4j_client
from app.core.logging_config import get_recent_logs
from app.core.database import save_message_to_rdb, get_messages_from_rdb

@tool
async def search_knowledge_tool(query: str, project_id: str = "system-master") -> str:
    """지식 그래프(Neo4j)에서 관련 지식을 검색합니다."""
    results = await neo4j_client.query_knowledge(project_id, query)
    if not results: return "관련된 지식을 찾지 못했습니다."
    formatted = []
    for r in results:
        t = ", ".join(r.get("types", []))
        content = r.get("description") or r.get("content") or r.get("summary") or r.get("name") or str(r)
        formatted.append(f"[{t}] {r.get('title') or r.get('name')}: {content}")
    return "\n".join(formatted)

@tool
async def web_search_intelligence_tool(query: str) -> str:
    """웹 검색을 통해 최신 정보를 수집합니다."""
    from app.core.search_client import search_client
    try:
        results = await asyncio.wait_for(search_client.search(query, max_results=3), timeout=settings.WEB_SEARCH_TIMEOUT_SECONDS)
        if not results: return "검색 결과 없음."
        facts = [f"Fact: {r['content']}\nSource: {r['url']}" for r in results]
        return "\n\n".join(facts)
    except: return "웹 검색 불가."

@tool
async def list_projects() -> str:
    """시스템의 모든 프로젝트 목록을 조회합니다."""
    projects = await neo4j_client.list_projects("tenant_hyungnim")
    if not projects: return "등록된 프로젝트 없음."
    return "\n".join([f"- {p['name']} (ID: {p['id']}): {p.get('description', '설명 없음')}" for p in projects])

@tool
async def get_project_details(project_id: str = None) -> str:
    """특정 프로젝트의 상세 설정과 에이전트 구성을 조회합니다. 작업 후 반드시 이 도구로 상태를 최종 확인하십시오."""
    if not project_id: return "오류: 'project_id' 필요."
    p = await neo4j_client.get_project(project_id)
    if not p: return f"프로젝트 {project_id} 없음."
    
    details = [f"--- PROJECT INFO ---", f"ID: {p['id']}", f"Name: {p['name']}", f"Path: {p.get('repo_path', 'N/A')}", "\n[AGENT CONFIGURATIONS]"]
    config = p.get('agent_config') or {}
    agents = config.get("agents", [])
    if agents:
        details.append(f"Workflow: {config.get('workflow_type')}, Entry: {config.get('entry_agent_id')}")
        details.append(json.dumps(agents, indent=2, ensure_ascii=False))
    else: details.append("에이전트 설정 없음.")
    return "\n".join(details)

@tool
async def execute_project_tool(project_id: str = None) -> str:
    """[최종 단계] 설정을 마치고 실행 준비가 되었음을 선언합니다."""
    return "READY_TO_START_SIGNAL"

@tool
async def reset_project_agents_tool(project_id: str) -> str:
    """[위험] 프로젝트의 모든 에이전트 구성을 물리적으로 삭제합니다. 새 판을 짤 때 반드시 먼저 실행하십시오."""
    try:
        await neo4j_client.delete_project_agents(project_id)
        return f"프로젝트 '{project_id}'의 모든 에이전트가 물리적으로 삭제되었습니다. 이제 깨끗한 상태에서 다시 시작하십시오."
    except Exception as e: return f"삭제 실패: {str(e)}"

@tool
async def add_agent_tool(project_id: str, agent_definition: Dict[str, Any]) -> str:
    """프로젝트에 에이전트를 추가합니다. 'agent_id', 'role', 'type', 'model', 'provider', 'system_prompt', 'config', 'next_agents'가 필수입니다."""
    try:
        from app.models.schemas import Project
        project_data = await neo4j_client.get_project(project_id)
        if not project_data: return "프로젝트 없음."
        config = project_data.get("agent_config") or {"agents": [], "workflow_type": "SEQUENTIAL", "entry_agent_id": ""}
        
        # 중복 제거 후 추가
        agents = [a for a in config.get("agents", []) if a.get("agent_id") != agent_definition.get("agent_id")]
        agents.append(agent_definition)
        config["agents"] = agents
        
        if not config.get("entry_agent_id"): config["entry_agent_id"] = agent_definition.get("agent_id")
            
        project_data["agent_config"] = config
        await neo4j_client.create_project_graph(Project(**project_data))
        return f"에이전트 '{agent_definition.get('role')}' 추가 성공."
    except Exception as e: return f"추가 실패: {str(e)}"

@tool
async def update_agent_config_tool(project_id: str, agent_id: str = None, updates: Dict[str, Any] = None) -> str:
    """에이전트 설정을 수정하거나 워크플로우(workflow_type, entry_agent_id)를 변경합니다. 
    'updates'에는 'repo_root', 'tool_allowlist', 'next_agents', 'model' 등이 포함될 수 있습니다.
    'repo_root' 변경 시 'allowed_paths'도 해당 경로를 포함하도록 자동으로 업데이트됩니다."""
    if not updates: return "오류: updates 필요."
    try:
        from app.models.schemas import Project
        project_data = await neo4j_client.get_project(project_id)
        if not project_data: return f"프로젝트 {project_id}를 찾을 수 없습니다."
        
        config = project_data.get("agent_config", {})
        
        # 워크플로우 수준 업데이트
        if "workflow_type" in updates: config["workflow_type"] = updates.pop("workflow_type")
        if "entry_agent_id" in updates: config["entry_agent_id"] = updates.pop("entry_agent_id")
        
        if agent_id:
            agents = config.get("agents", [])
            updated = False
            for agent in agents:
                if agent["agent_id"] == agent_id:
                    c = agent.get("config", {})
                    # repo_root 설정 시 allowed_paths 자동 동기화
                    if "repo_root" in updates:
                        repo_path = updates["repo_root"]
                        c["repo_root"] = repo_path
                        c["allowed_paths"] = [repo_path]
                    
                    for k, v in updates.items():
                        if k == "repo_root": continue # 이미 위에서 처리
                        if k in ["tool_allowlist", "mode", "change_policy", "language_stack", "test_command", "retry_limit", "timeout_sec", "artifact_output"]: 
                            c[k] = v
                        else: agent[k] = v
                    agent["config"] = c
                    updated = True; break
            if not updated: return f"에이전트 {agent_id}를 찾지 못함."
            
        project_data["agent_config"] = config
        await neo4j_client.create_project_graph(Project(**project_data))
        return "업데이트 성공."
    except Exception as e: return f"오류: {str(e)}"

@tool
async def manage_job_queue_tool(action: str, tenant_id: str = "tenant_hyungnim"):
    """시스템 큐 관리. 사용자가 '작업이 멈췄다'고 할 때 'FIX_STUCK'을 실행하세요."""
    from app.core.config import settings
    import redis.asyncio as redis
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        if action == "LIST": return f"대기열 길이: {await redis_client.llen(f'job_queue:{tenant_id}')}"
        elif action == "CLEAR": await redis_client.delete(f"job_queue:{tenant_id}"); return "큐 초기화 완료."
        elif action == "FIX_STUCK":
            count = 0
            for key in await redis_client.keys("job:*:status"):
                if await redis_client.get(key) == "QUEUED":
                    await redis_client.set(key, "FAILED"); count += 1
            return f"{count}개의 멈춘 작업을 정리했습니다."
        return "알 수 없는 액션."
    finally: await redis_client.close()

@tool
async def setup_standard_workflow_tool(project_id: str, flow: List[str] = ["기획자", "개발자", "검수자"]) -> str:
    """[RECOMMENDED] 프로젝트의 에이전트들을 표준 순서로 자동 연결하고 필수 설정을 주입합니다.
    - 대상 에이전트가 '기획자', '개발자', '검수자' 등의 이름을 가지고 있어야 합니다.
    - 이 도구는 repo_root, allowed_paths, tool_allowlist, risk_level, next_agents를 한 번에 해결합니다."""
    try:
        from app.models.schemas import Project
        project_data = await neo4j_client.get_project(project_id)
        if not project_data: return f"오류: 프로젝트 {project_id}를 찾을 수 없습니다."
        
        config = project_data.get("agent_config") or {"agents": [], "workflow_type": "SEQUENTIAL", "entry_agent_id": ""}
        agents = config.get("agents", [])
        if not agents: return "오류: 연결할 에이전트가 없습니다. 먼저 에이전트들을 추가하십시오."
        
        repo_path = project_data.get("repo_path")
        if not repo_path: return "오류: 프로젝트의 '저장소 경로(repo_path)'가 설정되어 있지 않습니다. 프로젝트 정보부터 수정하십시오."
        
        # 역할 매핑 강화 (공백 제거, 대소문자 무시, 한/영 대응)
        role_map = {}
        for a in agents:
            r = str(a.get("role", "")).strip().upper()
            a_id = a.get("agent_id")
            role_map[r] = a_id
            # 상호 매핑
            if r in ["기획자", "PLANNER"]:
                role_map["기획자"] = a_id
                role_map["PLANNER"] = a_id
            elif r in ["개발자", "CODER", "DEVELOPER"]:
                role_map["개발자"] = a_id
                role_map["CODER"] = a_id
                role_map["DEVELOPER"] = a_id
            elif r in ["검수자", "QA", "REVIEWER"]:
                role_map["검수자"] = a_id
                role_map["QA"] = a_id
                role_map["REVIEWER"] = a_id

        actual_flow_ids = []
        for f_role in flow:
            target_id = role_map.get(f_role.strip().upper())
            if target_id:
                actual_flow_ids.append((f_role, target_id))
            
        if not actual_flow_ids:
            return f"오류: 에이전트를 매칭하지 못했습니다. 현재 역할: {list(role_map.keys())}. 요청한 흐름: {flow}"

        # 1. 필수 설정 주입 및 다음 단계 연결
        for i, (role_name, a_id) in enumerate(actual_flow_ids):
            for agent in agents:
                if agent["agent_id"] == a_id:
                    # 필수 설정 강제 주입
                    c = agent.get("config", {})
                    c["repo_root"] = repo_path
                    c["allowed_paths"] = [repo_path]
                    c["tool_allowlist"] = ["read_file", "list_dir", "write_file", "grep", "search_replace", "execute_command"]
                    c["risk_level"] = "medium"
                    agent["config"] = c
                    
                    # 워크플로우 배선
                    if i < len(actual_flow_ids) - 1:
                        next_a_id = actual_flow_ids[i+1][1]
                        agent["next_agents"] = [next_a_id]
                    else:
                        agent["next_agents"] = []
        
        # 2. 시작 지점(Entry) 설정
        config["entry_agent_id"] = actual_flow_ids[0][1]
        config["workflow_type"] = "SEQUENTIAL"
        config["agents"] = agents
        
        project_data["agent_config"] = config
        await neo4j_client.create_project_graph(Project(**project_data))
        
        flow_names = " -> ".join([x[0] for x in actual_flow_ids])
        return f"✅ 성공: [{flow_names}] 워크플로우 배선 및 필수 설정(경로, 도구 권한 등) 주입이 완료되었습니다. 이제 [START TASK]가 가능합니다."
    except Exception as e: return f"❌ 워크플로우 설정 실패: {str(e)}"

class MasterAgentService:
    def __init__(self):
        self.config_path = "D:/project/myllm/backend/data/master_config.json"
        self._load_config()
        
    def _check_completeness(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        if not project_data or not project_data.get("agent_config"): return {"is_complete": False, "missing": ["에이전트 구성 없음"]}
        config = project_data["agent_config"]
        agents = config.get("agents", [])
        if not agents: return {"is_complete": False, "missing": ["에이전트 없음"]}
        
        entry_id = config.get("entry_agent_id")
        if not entry_id: return {"is_complete": False, "missing": ["시작 에이전트(entry_agent_id) 미설정"]}
        
        agent_ids = {a.get("agent_id") for a in agents}
        if entry_id not in agent_ids: return {"is_complete": False, "missing": [f"시작 에이전트 {entry_id}가 존재하지 않음"]}

        project_repo = project_data.get("repo_path")
        missing = []
        for agent in agents:
            role, c = agent.get("role", ""), agent.get("config", {})
            a_type = agent.get("type", "CUSTOM")
            
            # repo_root는 프로젝트 공통 경로가 있으면 통과
            if not (c.get("repo_root") or project_repo): 
                missing.append(f"'{role}'의 repo_root")
            
            # 역할별 필수 필드 세분화 (로직 유연화)
            if a_type in ["CODER", "DEVELOPER"]:
                if not c.get("mode"): missing.append(f"'{role}'의 mode 설정")
            elif a_type in ["QA", "REVIEWER"]:
                if not c.get("retry_limit"): missing.append(f"'{role}'의 retry_limit")
            
            if not c.get("tool_allowlist"): 
                missing.append(f"'{role}'의 tool_allowlist")
            
        if missing: return {"is_complete": False, "missing": missing}
        return {"is_complete": True, "final_summary": project_data.get("description", "모든 연결 및 설정 확인 완료")}

    def _load_config(self):
        import os
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = MasterAgentConfig(**json.load(f))
                    return
            except: pass
        self.config = MasterAgentConfig()

    def _save_config(self):
        import os
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config.dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Failed to save master_config.json: {e}")

    def update_config(self, new_config: MasterAgentConfig):
        self.config = new_config
        self._save_config()

    def get_config(self) -> MasterAgentConfig:
        self._load_config() # Always load latest
        return self.config

    async def _construct_messages(self, message: str, history: List[ChatMessage], project_id: str, system_instruction: str):
        # 1. 실제 DB에서 최신 정보를 강제로 긁어옴 (과거 대화보다 우선됨)
        p = await neo4j_client.get_project(project_id)
        current_state = "No project found"
        if p:
            config = p.get('agent_config') or {}
            agents = config.get("agents", [])
            agent_summary = ", ".join([f"{a['role']}({a['agent_id']})" for a in agents]) if agents else "None"
            current_state = f"- Name: {p['name']}\n- Path: {p.get('repo_path')}\n- Registered Agents: {agent_summary}\n- Entry Agent: {config.get('entry_agent_id')}"

        # 2. 시스템 프롬프트 구성 (최신 DB 상태를 최상단에 배치)
        ctx_header = f"[ABSOLUTE REALITY - ACTUAL DB STATE]\n{current_state}\n\n[USER'S LATEST INTENT]\n{message}\n\n"
        
        system_prompt = f"{ctx_header}{self.config.system_prompt}\n\n[MANDATORY INSTRUCTION]\n{system_instruction}"
        msgs = [SystemMessage(content=system_prompt)]
        
        def clean(c: str) -> str: return c.replace("형님", "사용자님").replace("하겠습쇼", "하겠습니다") if c else ""
        
        # 3. 과거 대화 주입 (기억력 대폭 강화: 40개까지 로드하여 복잡한 요구사항 보존)
        db_messages = await get_messages_from_rdb(project_id, None, 40)
        for m in db_messages:
            if m.sender_role == "user": msgs.append(HumanMessage(content=clean(m.content)))
            elif m.sender_role == "assistant": msgs.append(AIMessage(content=clean(m.content)))
        
        msgs.append(HumanMessage(content=message))
        return msgs

    async def _get_real_time_context(self, project_id: str) -> str:
        if project_id == "system-master": return "System Master Context"
        p = await neo4j_client.get_project(project_id)
        return f"Project: {p.get('name')}, Path: {p.get('repo_path')}" if p else "No Project Data"

    async def stream_message(self, message: str, history: List[ChatMessage], project_id: str = None, thread_id: str = None, user: Any = None, worker_status: Dict[str, Any] = None):
        # [CRITICAL] UI에서 바뀐 설정을 매 메시지마다 실시간으로 로드
        self._load_config()
        await save_message_to_rdb("user", message, project_id, thread_id, metadata={"user_id": user.id if user else "system"})
        
        system_instruction = """[CRITICAL] 반드시 100% 순수 한국어로만 답변하십시오. 
[COMMAND] 
1. 호칭은 '사용자님'으로 통일하십시오. 
2. **[행동 우선]** 사용자가 "예", "응", "실행하자" 등 긍정하면 토 달지 말고 즉시 'READY_TO_START' 버튼을 생성하십시오. 로그 확인 지시나 추가 질문으로 시간을 끌지 마십시오.
3. 사용자가 요구사항을 추가하면 질문하지 말고 즉시 'update_agent_config_tool'로 DB를 업데이트한 뒤 보고하십시오.
4. **[절대 금지]** "시스템 관리자에게 문의하십시오", "로그를 확인하십시오" 같은 무책임한 발언을 금지합니다. 당신은 현장 지휘관입니다.
5. 모든 클라우드 모델의 Provider는 'OPENROUTER'로 입력하십시오.
"""

        full_content = ""
        try:
            # [FIX] settings.PRIMARY_MODEL 대신 UI에서 설정된 self.config.model을 사용
            llm_model = self.config.model or settings.PRIMARY_MODEL
            print(f"DEBUG: Master Agent using Model: {llm_model}")
            
            llm = ChatOpenAI(
                model=llm_model, 
                api_key=settings.OPENROUTER_API_KEY, 
                base_url=settings.OPENROUTER_BASE_URL, 
                temperature=self.config.temperature or 0.1
            )
            tools = [search_knowledge_tool, web_search_intelligence_tool, list_projects, get_project_details, execute_project_tool, update_agent_config_tool, add_agent_tool, manage_job_queue_tool, reset_project_agents_tool, setup_standard_workflow_tool]
            llm_with_tools = llm.bind_tools(tools)
            final_messages = await self._construct_messages(message, history, project_id, system_instruction)
            
            loop_count = 0
            while loop_count < 8:
                full_msg_chunk = None
                async for chunk in llm_with_tools.astream(final_messages):
                    if full_msg_chunk is None: full_msg_chunk = chunk
                    else: full_msg_chunk += chunk
                    if chunk.content:
                        yield chunk.content; full_content += chunk.content
                
                if full_msg_chunk and hasattr(full_msg_chunk, 'tool_calls') and full_msg_chunk.tool_calls:
                    valid_calls = [tc for tc in full_msg_chunk.tool_calls if tc.get("name")]
                    if not valid_calls: break
                    final_messages.append(AIMessage(content=full_msg_chunk.content or "", tool_calls=valid_calls))
                    for tc in valid_calls:
                        t_name, t_args, t_id = tc["name"], tc["args"], tc.get("id") or f"call_{uuid.uuid4().hex[:12]}"
                        # [CRITICAL] 자동 프로젝트 ID 주입 리스트에 새 도구 추가
                        if t_name in ["get_project_details", "execute_project_tool", "update_agent_config_tool", "add_agent_tool", "reset_project_agents_tool", "setup_standard_workflow_tool"]:
                            t_args["project_id"] = project_id
                        try:
                            t_res = None
                            if t_name == "search_knowledge_tool": t_res = await search_knowledge_tool.ainvoke(t_args)
                            elif t_name == "web_search_intelligence_tool": t_res = await web_search_intelligence_tool.ainvoke(t_args)
                            elif t_name == "list_projects": t_res = await list_projects.ainvoke(t_args)
                            elif t_name == "get_project_details": t_res = await get_project_details.ainvoke(t_args)
                            elif t_name == "execute_project_tool": t_res = await execute_project_tool.ainvoke(t_args)
                            elif t_name == "reset_project_agents_tool": t_res = await reset_project_agents_tool.ainvoke(t_args)
                            elif t_name == "add_agent_tool": t_res = await add_agent_tool.ainvoke(t_args)
                            elif t_name == "update_agent_config_tool": t_res = await update_agent_config_tool.ainvoke(t_args)
                            elif t_name == "manage_job_queue_tool": t_res = await manage_job_queue_tool.ainvoke(t_args)
                            elif t_name == "setup_standard_workflow_tool": t_res = await setup_standard_workflow_tool.ainvoke(t_args)
                            else: t_res = f"도구 {t_name} 없음"
                            t_out = str(t_res)
                        except Exception as e: t_out = f"오류: {str(e)}"
                        final_messages.append(ToolMessage(content=t_out, tool_call_id=t_id))
                    loop_count += 1
                else: break
            
            # [CRITICAL] 사용자님의 실행/긍정 의사가 확인되면 즉시 READY_TO_START 버튼 생성
            confirm_keywords = ["확정", "시작", "진행", "결정", "GO", "개시", "OK", "실행", "예", "응", "하자", "좋아", "가자"]
            if any(kw in message for kw in confirm_keywords) or (len(message.strip()) <= 2 and any(kw in message for kw in ["예", "응", "네", "어", "음"])):
                p_data = await neo4j_client.get_project(project_id)
                check = self._check_completeness(p_data)
                if check["is_complete"]:
                    ready_json = "\n" + json.dumps({"status": "READY_TO_START", "final_summary": check["final_summary"]}, ensure_ascii=False)
                    yield ready_json; full_content += ready_json
                else:
                    report = f"\n\n--- MISSION READINESS REPORT ---\n⚠️ 설정 미비로 확정할 수 없습니다:\n- " + "\n- ".join(check.get('missing', [])[:5])
                    yield report; full_content += report
            else:
                # 확정이 아닌 일반 대화 시에는 안내 문구만 출력 (버튼 생성 안 함)
                pass
        except Exception as e: yield f"\n[오류]: {str(e)}"
        finally:
            if full_content: await save_message_to_rdb("assistant", full_content, project_id, thread_id)

    async def process_message(self, message: str, history: List[ChatMessage], project_id: str = None, thread_id: str = None, user: Any = None, worker_status: Dict[str, Any] = None) -> Dict[str, Any]:
        # Simple wrapper for stream_message consistency
        return {"message": "Streaming only for master agent", "quick_links": []}

    async def create_job_from_history(self, history: List[ChatMessage], orchestrator: Any, user: Any) -> Dict[str, Any]: return {"message": "N/A"}
