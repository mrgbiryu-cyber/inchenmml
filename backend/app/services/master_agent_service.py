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
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
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
    
    # [FIX] 읽기 쉬운 마크다운 표 형태로 변경
    details = []
    details.append(f"📊 **{p['name']}** 프로젝트 현황\n")
    details.append(f"**기본 정보**")
    details.append(f"• 프로젝트 ID: `{p['id']}`")
    details.append(f"• 경로: `{p.get('repo_path', 'N/A')}`")
    
    config = p.get('agent_config') or {}
    agents = config.get("agents", [])
    
    if agents:
        details.append(f"• 워크플로우: **{config.get('workflow_type', 'N/A')}**")
        details.append(f"• 시작 에이전트: **{config.get('entry_agent_id', 'N/A')}**\n")
        
        details.append(f"**등록된 에이전트 ({len(agents)}개)**")
        
        # 이모지 매핑
        role_emoji = {
            "PLANNER": "📋",
            "DEVELOPER": "💻",
            "CODER": "💻",
            "QA": "🔍",
            "QA_ENGINEER": "🔍",
            "REVIEWER": "👀",
            "REPORTER": "📄"
        }
        
        for i, agent in enumerate(agents, 1):
            role = agent.get('role', 'UNKNOWN')
            emoji = role_emoji.get(role, "⚙️")
            model = agent.get('model', 'N/A')
            next_agents = agent.get('next_agents', [])
            next_str = ", ".join(next_agents) if next_agents else "완료"
            
            details.append(f"{i}. {emoji} **{role}**")
            details.append(f"   - 모델: `{model}`")
            details.append(f"   - 다음 단계: {next_str}")
    else:
        details.append("⚠️ 에이전트 설정 없음.")
    
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
        
        # [v2.2 RULE 3] ARMED 상태 관리
        self.is_armed: bool = False
        self.armed_mes_hash: Optional[str] = None
        self.current_mes: Dict[str, Any] = {}
        
        # [Hybrid Intent] 선택지 대기 상태 관리
        self.pending_choices: Dict[str, List[str]] = {}  # {project_id: [intent1, intent2, ...]}
        
    def _classify_intent(self, message: str) -> tuple:
        """
        [RULE 1] 하이브리드 Intent 분류
        Returns: (primary_intent, possible_intents)
        - primary_intent가 "UNCLEAR"이면 possible_intents에서 사용자가 선택
        """
        msg_stripped = message.strip()
        
        # [숫자 선택 감지] 사용자가 이전 선택지에서 번호를 선택한 경우
        if msg_stripped in ["1", "2", "3", "4", "5"]:
            return ("USER_CHOICE", [msg_stripped])
        
        # [v2.2 RULE 3.1] "응/예" 단독 입력 필터링
        affirmative_only = ["응", "예", "좋아", "오케이", "ㅇㅇ", "네", "ok", "OK"]
        if msg_stripped in affirmative_only:
            return ("AFFIRMATIVE_ONLY", [])
        
        # === 명확한 Intent (자동 실행) ===
        
        # 1. 명시적 실행 확정 토큰 (최우선)
        confirm_tokens = ["실행 확정", "시작 확정", "작전 개시", "확정한다", "START TASK"]
        if any(t in message for t in confirm_tokens):
            return ("EXECUTION_REQUEST", [])
        
        # 2. 취소/중단
        cancel_tokens = ["취소", "중단", "멈춰", "그만", "하지마", "리셋", "삭제"]
        if any(t in message for t in cancel_tokens):
            return ("CANCEL", [])
        
        topic_shift_pattern = r"(새로운|다른|주제 변경|딴 얘기)"
        if re.search(topic_shift_pattern, message):
            return ("TOPIC_SHIFT", [])
        
        # 3. 명확한 조회 패턴 (현재 + 알려줘/보여줘/구성)
        if ("현재" in message or "지금" in message) and ("알려줘" in message or "보여줘" in message or "구성" in message or "현황" in message):
            return ("STATUS_QUERY", [])
        
        # 4. 명확한 설정 변경 패턴
        if "보강해줘" in message or "채워줘" in message or "추가해줘" in message:
            return ("CONFIG_CHANGE", [])
        
        # 5. 명확한 준비 점검 패턴
        if "준비 상태 점검" in message or "준비 점검" in message:
            return ("READINESS_CHECK", [])
        
        # === 애매한 Intent (선택지 제시) ===
        
        matched = []
        
        # "순서", "잘못", "문제" → 여러 가능성
        if "순서" in message or "잘못" in message or "문제" in message or "이상" in message:
            matched.extend(["STATUS_QUERY", "CONFIG_CHANGE", "READINESS_CHECK"])
        
        # "확인" → 조회 또는 점검
        if "확인" in message and "확인해" not in message:  # "확인해봐"는 STATUS_QUERY
            matched.extend(["STATUS_QUERY", "READINESS_CHECK"])
        elif "확인해" in message:
            return ("STATUS_QUERY", [])
        
        # 중복 제거
        matched = list(dict.fromkeys(matched))
        
        if len(matched) == 0:
            return ("MES_BUILD", [])
        elif len(matched) == 1:
            return (matched[0], [])
        else:
            return ("UNCLEAR", matched)

    def _get_mes_hash(self, project_data: Dict[str, Any]) -> str:
        """[RULE 2] MES 구조 기반 Hash 생성 - 상태 동기화용"""
        config = project_data.get("agent_config", {})
        agents = config.get("agents", [])
        
        # v2.2: 필드 순서 고정 및 공백 정규화
        normalized_data = {
            "entry": config.get("entry_agent_id", ""),
            "workflow": config.get("workflow_type", ""),
            "agents": sorted([
                f"{a.get('agent_id')}:{a.get('model')}:{json.dumps(a.get('config', {}), sort_keys=True)}"
                for a in agents
            ])
        }
        raw_json = json.dumps(normalized_data, sort_keys=True)
        return hashlib.sha256(raw_json.encode()).hexdigest()
        
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
            
            # [v2.2 FIX] 역할 이름 정규화 (대소문자 무시, 동의어 처리)
            role_normalized = str(role).strip().upper()
            
            # repo_root는 프로젝트 공통 경로가 있으면 통과
            if not (c.get("repo_root") or project_repo): 
                missing.append(f"'{role}'의 repo_root")
            
            # 역할별 필수 필드 세분화 (로직 유연화)
            # CODER, DEVELOPER 동의어 처리
            if role_normalized in ["CODER", "DEVELOPER"]:
                if not c.get("mode"): missing.append(f"'{role}'의 mode 설정")
            # QA, REVIEWER, QA_ENGINEER 동의어 처리
            elif role_normalized in ["QA", "REVIEWER", "QA_ENGINEER"]:
                if not c.get("retry_limit"): missing.append(f"'{role}'의 retry_limit")
            
            # tool_allowlist 체크 (REPORTER는 선택사항)
            if role_normalized not in ["REPORTER"] and not c.get("tool_allowlist"): 
                missing.append(f"'{role}'의 tool_allowlist")
            
        if missing: return {"is_complete": False, "missing": missing}
        return {"is_complete": True, "final_summary": project_data.get("description", "모든 연결 및 설정 확인 완료"), "mes_hash": self._get_mes_hash(project_data)}

    async def _check_agent_capability(self, project_id: str, user_requirement: str = "") -> Dict[str, Any]:
        """
        [NEW] 요구사항 vs 현재 에이전트 실행 가능성 매칭
        - 프로젝트 컨텍스트 분석 (파일 구조, 기존 코드)
        - 에이전트 역할 vs 실제 프로젝트 환경 매칭
        - 워크플로우 순서 검증 (순환 참조, 고립된 에이전트)
        Returns: {"can_execute": bool, "issues": List[Dict], "recommendations": List[str]}
        """
        try:
            p_data = await neo4j_client.get_project(project_id)
            if not p_data:
                return {
                    "can_execute": False,
                    "issues": [{"severity": "ERROR", "reason": f"프로젝트 {project_id}를 찾을 수 없습니다."}],
                    "recommendations": []
                }
            
            repo_path_str = p_data.get("repo_path", "")
            repo_path = Path(repo_path_str) if repo_path_str else None
            
            config = p_data.get("agent_config", {})
            agents = config.get("agents", [])
            agent_roles = [str(a.get("role", "")).upper() for a in agents]
            
            issues = []
            recommendations = []
            
            # 1. 경로 존재 및 접근 가능성 체크
            if repo_path and not repo_path.exists():
                issues.append({
                    "severity": "ERROR",
                    "agent": "전체 프로젝트",
                    "reason": f"프로젝트 경로 '{repo_path}'가 존재하지 않습니다.",
                })
                recommendations.append(f"경로 '{repo_path}'를 생성하거나 repo_path 설정을 수정하세요.")
            
            # 2. API 관련 요구사항 vs API 파일 존재 여부
            if "API" in user_requirement.upper() or "인증" in user_requirement or any("API" in r or "AUTH" in r for r in agent_roles):
                has_api_agent = any("API" in r or "AUTH" in r for r in agent_roles)
                api_files = []
                if repo_path and repo_path.exists():
                    api_patterns = ["**/api/**/*.py", "**/routes/**/*.py", "**/endpoints/**/*.py"]
                    for pattern in api_patterns:
                        api_files.extend(list(repo_path.glob(pattern)))
                
                if has_api_agent and not api_files:
                    issues.append({
                        "severity": "WARNING",
                        "agent": "API/AUTH 에이전트",
                        "reason": "프로젝트에 API 엔드포인트 파일이 없는데 API 인증 에이전트가 설정되어 있습니다.",
                    })
                    recommendations.append("API 인증 에이전트를 제거하거나, API 엔드포인트를 먼저 개발하세요.")
            
            # 3. REVIEWER/QA 에이전트 vs 검토 대상 파일 존재 여부
            if any("REVIEWER" in r or "QA" in r for r in agent_roles):
                code_files = []
                if repo_path and repo_path.exists():
                    code_patterns = ["*.py", "*.js", "*.ts", "*.tsx", "*.jsx"]
                    for pattern in code_patterns:
                        code_files.extend(list(repo_path.glob(pattern)))
                
                if not code_files:
                    issues.append({
                        "severity": "WARNING",
                        "agent": "REVIEWER/QA 에이전트",
                        "reason": "검토할 코드 파일이 없는데 검수 에이전트가 설정되어 있습니다.",
                    })
                    recommendations.append("CODER/DEVELOPER 에이전트를 먼저 실행하여 파일을 생성하거나, 워크플로우 순서를 조정하세요.")
            
            # 4. 워크플로우 순서 검증 (순환 참조, 고립된 에이전트)
            workflow_issues = self._validate_workflow_order(agents)
            issues.extend(workflow_issues.get("issues", []))
            recommendations.extend(workflow_issues.get("recommendations", []))
            
            # 5. GIT 에이전트 vs .git 디렉토리 존재 여부
            if any("GIT" in r or "DEPLOY" in r for r in agent_roles):
                git_dir = repo_path / ".git" if repo_path else None
                if git_dir and not git_dir.exists():
                    issues.append({
                        "severity": "WARNING",
                        "agent": "GIT/DEPLOY 에이전트",
                        "reason": "프로젝트가 Git 저장소가 아닌데 GIT 에이전트가 설정되어 있습니다.",
                    })
                    recommendations.append("Git을 초기화(git init)하거나 GIT 에이전트를 제거하세요.")
            
            # 결과 판정
            error_count = sum(1 for issue in issues if issue.get("severity") == "ERROR")
            can_execute = error_count == 0
            
            return {
                "can_execute": can_execute,
                "issues": issues,
                "recommendations": recommendations
            }
        
        except Exception as e:
            print(f"⚠️ _check_agent_capability 실행 중 오류: {e}", flush=True)
            return {
                "can_execute": True,  # 검증 실패 시 기존 동작 유지 (보수적)
                "issues": [],
                "recommendations": []
            }
    
    def _validate_workflow_order(self, agents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        [NEW] 워크플로우 순서 검증
        - 순환 참조 감지
        - 고립된 에이전트 감지
        - 논리적 순서 검증 (PLANNER → DEVELOPER → QA → REPORTER)
        """
        issues = []
        recommendations = []
        
        if not agents:
            return {"issues": [], "recommendations": []}
        
        # 1. 순환 참조 감지 (DFS)
        agent_map = {a.get("agent_id"): a.get("next_agents", []) for a in agents}
        
        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in agent_map.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        visited = set()
        for agent_id in agent_map.keys():
            if agent_id not in visited:
                if has_cycle(agent_id, visited, set()):
                    issues.append({
                        "severity": "ERROR",
                        "agent": "전체 워크플로우",
                        "reason": f"순환 참조가 감지되었습니다. 에이전트 {agent_id}가 자기 자신으로 돌아오는 경로가 있습니다.",
                    })
                    recommendations.append("setup_standard_workflow_tool을 호출하여 워크플로우 순서를 재설정하세요.")
                    break
        
        # 2. 고립된 에이전트 감지 (next_agents가 비어있고, 다른 에이전트에서도 참조되지 않는 경우)
        all_next_agents = set()
        for agent in agents:
            all_next_agents.update(agent.get("next_agents", []))
        
        for agent in agents:
            agent_id = agent.get("agent_id")
            next_agents = agent.get("next_agents", [])
            
            # 시작 에이전트가 아니고, 다른 에이전트에서도 참조되지 않으면 고립됨
            if not next_agents and agent_id not in all_next_agents:
                # 단, 마지막 에이전트(REPORTER 등)는 예외
                role = str(agent.get("role", "")).upper()
                if role not in ["REPORTER", "마무리", "완료"]:
                    issues.append({
                        "severity": "WARNING",
                        "agent": agent_id,
                        "reason": f"에이전트 '{agent_id}'가 워크플로우에서 고립되어 있습니다 (다음 단계도 없고, 다른 에이전트에서도 참조되지 않음).",
                    })
                    recommendations.append(f"에이전트 '{agent_id}'를 워크플로우에 연결하거나 제거하세요.")
        
        return {"issues": issues, "recommendations": recommendations}

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
        # 1. [CRITICAL] 현재 프로젝트 ID를 명확히 강조 (프로젝트 격리)
        # 실제 DB에서 최신 정보를 강제로 긁어옴 (과거 대화보다 우선됨)
        p = await neo4j_client.get_project(project_id)
        current_state = "No project found"
        if p:
            config = p.get('agent_config') or {}
            agents = config.get("agents", [])
            agent_summary = ", ".join([f"{a['role']}({a['agent_id']})" for a in agents]) if agents else "None"
            current_state = f"- Project ID (CURRENT): {project_id}\n- Name: {p['name']}\n- Path: {p.get('repo_path')}\n- Registered Agents: {agent_summary}\n- Entry Agent: {config.get('entry_agent_id')}"

        # 2. 시스템 프롬프트 구성 (최신 DB 상태를 최상단에 배치)
        # [CRITICAL] 현재 프로젝트 ID를 최우선으로 강조
        ctx_header = f"[CRITICAL: ONLY USE PROJECT_ID = {project_id}]\n[ABSOLUTE REALITY - ACTUAL DB STATE FOR PROJECT {project_id}]\n{current_state}\n\n[USER'S LATEST INTENT]\n{message}\n\n[FORBIDDEN: NEVER mention agents not in the above list. NEVER use data from other projects.]\n\n"
        
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
        
        # [v2.2 RULE 1] 하이브리드 인텐트 분류
        intent, possible_intents = self._classify_intent(message)
        print(f"DEBUG: Intent classified as '{intent}' (possible: {possible_intents}) for message: '{message}'", flush=True)
        
        # [Hybrid Intent] USER_CHOICE 처리
        if intent == "USER_CHOICE":
            choice_num = int(possible_intents[0])
            pending = self.pending_choices.get(project_id, [])
            if pending and 1 <= choice_num <= len(pending):
                intent = pending[choice_num - 1]
                self.pending_choices.pop(project_id, None)  # 선택 완료 후 제거
                print(f"DEBUG: User chose intent: {intent}", flush=True)
            else:
                yield "❌ 잘못된 선택입니다. 다시 시도해주세요."
                return
        else:
            # [FIX] 숫자가 아닌 자연어 응답 시 이전 선택지 자동 무효화
            if project_id in self.pending_choices:
                self.pending_choices.pop(project_id, None)
                print(f"DEBUG: User switched from choice mode to natural language. Cleared pending choices.", flush=True)
        
        # [Hybrid Intent] UNCLEAR 처리 (선택지 제시)
        if intent == "UNCLEAR":
            intent_labels = {
                "STATUS_QUERY": "📊 현재 프로젝트 상태 조회",
                "CONFIG_CHANGE": "⚙️ 에이전트 설정 변경",
                "READINESS_CHECK": "✅ 준비 상태 점검 (설정 완료 여부)",
                "EXECUTION_REQUEST": "🚀 작업 실행 확정"
            }
            
            choice_msg = "다음 중 어떤 작업을 원하시나요?\n\n"
            for i, intent_option in enumerate(possible_intents, 1):
                choice_msg += f"{i}. {intent_labels.get(intent_option, intent_option)}\n"
            choice_msg += "\n번호를 선택해주세요."
            
            # 선택지 저장
            self.pending_choices[project_id] = possible_intents
            
            yield choice_msg
            await save_message_to_rdb("assistant", choice_msg, project_id, thread_id)
            return
        
        # [v2.2 RULE 3.2] De-arming 조건 체크 (MES Hash 변경 감지)
        p_data = await neo4j_client.get_project(project_id)
        if p_data:
            self.current_mes = p_data
            current_mes_hash = self._get_mes_hash(p_data)
            
            # MES Hash가 변경되었으면 즉시 De-arm
            if self.is_armed and self.armed_mes_hash and self.armed_mes_hash != current_mes_hash:
                self.is_armed = False
                self.armed_mes_hash = None
                yield "⚠️ 프로젝트 설정이 변경되어 '확정' 상태가 해제되었습니다. 다시 확인 후 '실행 확정'을 해주십시오.\n\n"
        
        # [v2.2 RULE 3.2] CANCEL 또는 TOPIC_SHIFT 시 De-arming
        if intent in ["CANCEL", "TOPIC_SHIFT"]:
            self.is_armed = False
            self.armed_mes_hash = None
            response_text = "✅ 현재 진행 중이던 작업 계획이 초기화되었습니다. 새로운 지시를 내려주십시오." if intent == "CANCEL" else "✅ 대화 주제가 변경되어 이전 작업 계획이 초기화되었습니다."
            yield response_text
            await save_message_to_rdb("assistant", response_text, project_id, thread_id)
            return
        
        # [v2.2 RULE 3.1] "응/예" 단독 입력 시 조기 종료 (버튼 생성 방지)
        if intent == "AFFIRMATIVE_ONLY":
            yield "네, 사용자님. 추가로 필요한 사항이 있으시면 말씀해 주십시오."
            await save_message_to_rdb("assistant", "네, 사용자님. 추가로 필요한 사항이 있으시면 말씀해 주십시오.", project_id, thread_id)
            return
        
        # [v2.2 RULE 4 & 5] STATUS_QUERY와 READINESS_CHECK는 LLM 호출 없이 직접 처리
        full_content = ""
        
        # [v2.2 RULE 4] STATUS_QUERY 처리 (RAG 오염 차단)
        if intent == "STATUS_QUERY":
            try:
                yield "\n\n📊 [실시간 DB 조회] 현재 프로젝트 상태를 조회 중입니다...\n\n"
                details = await get_project_details.ainvoke({"project_id": project_id})
                if not details or "없음" in details or "N/A" in details:
                    fixed_response = "사용자님, 현재 프로젝트 상태를 최신으로 조회할 수 없어 확인되지 않은 내용을 단정해서 말씀드릴 수 없습니다."
                    yield fixed_response
                    full_content += fixed_response
                else:
                    yield details
                    full_content += details
            except Exception as e: 
                fixed_response = f"사용자님, 현재 프로젝트 상태를 최신으로 조회할 수 없어 확인되지 않은 내용을 단정해서 말씀드릴 수 없습니다. (오류: {str(e)})"
                yield fixed_response
                full_content += fixed_response
            await save_message_to_rdb("assistant", full_content, project_id, thread_id)
            return
        
        # [v2.2 RULE 5] READINESS_CHECK 처리 (보고서 + JSON 출력)
        if intent == "READINESS_CHECK":
            full_content = ""  # [FIX] 초기화
            p_data = await neo4j_client.get_project(project_id)
            
            # [NEW] 기술적 설정 완료 체크
            check = self._check_completeness(p_data)
            
            # [NEW] 실행 가능성 체크 (요구사항 vs 에이전트 매칭)
            capability_check = await self._check_agent_capability(project_id, message)
            
            # 1. 실행 불가 사유가 있으면 우선 보고
            if not capability_check["can_execute"]:
                report = "\n\n⚠️ [실행 불가 사유 감지]\n"
                for issue in capability_check["issues"]:
                    severity_emoji = "🚨" if issue.get("severity") == "ERROR" else "⚠️"
                    agent_name = issue.get("agent", "알 수 없음")
                    reason = issue.get("reason", "")
                    report += f"{severity_emoji} **{agent_name}**: {reason}\n"
                
                report += "\n**권장 조치:**\n"
                for i, rec in enumerate(capability_check["recommendations"], 1):
                    report += f"{i}. {rec}\n"
                
                yield report
                full_content += report
                await save_message_to_rdb("assistant", full_content, project_id, thread_id)
                return
            
            # 2. 실행 가능하지만 경고가 있는 경우
            warnings = [issue for issue in capability_check["issues"] if issue.get("severity") == "WARNING"]
            if warnings:
                warning_msg = "\n\n⚠️ [주의 사항]\n"
                for issue in warnings:
                    agent_name = issue.get("agent", "알 수 없음")
                    reason = issue.get("reason", "")
                    warning_msg += f"• **{agent_name}**: {reason}\n"
                yield warning_msg
                full_content += warning_msg
            
            # 3. 기술적 설정 완료 체크
            if check["is_complete"]:
                report = f"\n\n✅ [준비 상태 점검 완료]\n모든 설정이 완료되었습니다. 아래 [START TASK] 버튼을 눌러 작업을 시작하세요.\n\n"
                yield report
                full_content += report
                
                # [FIX] 완료 시 즉시 READY_TO_START JSON 출력
                ready_json = json.dumps({
                    "status": "READY_TO_START", 
                    "final_summary": check.get("final_summary", "모든 설정 완료"),
                    "mes_hash": check.get("mes_hash", "")
                }, ensure_ascii=False)
                yield f"\n{ready_json}"
                full_content += f"\n{ready_json}"
            else:
                report = f"\n\n--- MISSION READINESS REPORT ---\n⚠️ 다음 항목이 미비합니다:\n- " + "\n- ".join(check.get('missing', [])[:5])
                yield report
                full_content += report
            await save_message_to_rdb("assistant", full_content, project_id, thread_id)
            return
        
        # [v2.2 RULE 6] MES_BUILD 처리 (LLM 건너뜀, 현재 상태만 반환)
        if intent == "MES_BUILD":
            # 일반적인 대화나 요구사항 정립 시 → 현재 상태만 간단히 반환
            simple_msg = "사용자님, 구체적인 지시를 주시면 바로 실행하겠습니다.\n\n다음 명령어를 사용하실 수 있습니다:\n• '준비 상태 점검' - 현재 설정 확인\n• '현재 에이전트 구성 알려줘' - 상세 정보 조회\n• '미비 항목 보강해줘' - 자동 설정 보강\n• '실행 확정' - 작업 시작"
            yield simple_msg
            await save_message_to_rdb("assistant", simple_msg, project_id, thread_id)
            return
        
        # [v2.2 RULE 7] CONFIG_CHANGE 처리 (도구만 호출, LLM 건너뜀)
        if intent == "CONFIG_CHANGE":
            yield "⚙️ 설정 변경 요청을 처리 중입니다...\n\n"
            # 1. 현재 프로젝트 데이터 조회
            p_data = await neo4j_client.get_project(project_id)
            if not p_data:
                error_msg = "❌ 프로젝트를 찾을 수 없습니다."
                yield error_msg
                await save_message_to_rdb("assistant", error_msg, project_id, thread_id)
                return
            
            # [NEW] 워크플로우 순서 문제 감지
            if "순서" in message or "잘못" in message:
                config = p_data.get("agent_config", {})
                agents = config.get("agents", [])
                
                # 현재 순서 분석
                workflow_msg = "📋 **현재 워크플로우 순서:**\n\n"
                entry_id = config.get("entry_agent_id")
                if entry_id:
                    workflow_msg += f"시작: **{entry_id}**\n\n"
                    for agent in agents:
                        role = agent.get("role")
                        next_agents = agent.get("next_agents", [])
                        next_str = " → ".join(next_agents) if next_agents else "완료"
                        workflow_msg += f"• {role} → {next_str}\n"
                    
                    workflow_msg += "\n\n**올바른 표준 순서로 자동 수정할까요?**\n"
                    workflow_msg += "표준 순서: PLANNER → DEVELOPER → QA_ENGINEER → REPORTER → 완료\n\n"
                    workflow_msg += "'표준 순서로 수정해줘' 라고 입력하시면 자동으로 수정합니다."
                    
                    yield workflow_msg
                    await save_message_to_rdb("assistant", workflow_msg, project_id, thread_id)
                    return
            
            # 2. 누락된 항목 파악
            check = self._check_completeness(p_data)
            if check["is_complete"]:
                complete_msg = "✅ 이미 모든 설정이 완료되었습니다."
                yield complete_msg
                await save_message_to_rdb("assistant", complete_msg, project_id, thread_id)
                return
            
            missing = check.get("missing", [])
            config = p_data.get("agent_config", {})
            agents = config.get("agents", [])
            
            # 3. 각 에이전트의 누락 항목 자동 보강
            updated_count = 0
            for agent in agents:
                role = agent.get("role", "")
                role_normalized = str(role).strip().upper()
                agent_config = agent.get("config", {})
                updates = {}
                
                # DEVELOPER/CODER에 mode 추가
                if role_normalized in ["CODER", "DEVELOPER"] and not agent_config.get("mode"):
                    updates["mode"] = "REPAIR"
                    updated_count += 1
                
                # QA/REVIEWER에 retry_limit 추가
                if role_normalized in ["QA", "REVIEWER", "QA_ENGINEER"] and not agent_config.get("retry_limit"):
                    updates["retry_limit"] = 3
                    updated_count += 1
                
                # 기타 CUSTOM 타입에 tool_allowlist 추가 (REPORTER 제외)
                if role_normalized not in ["REPORTER", "PLANNER"] and not agent_config.get("tool_allowlist"):
                    updates["tool_allowlist"] = ["read_file", "write_file", "list_dir"]
                    updated_count += 1
                
                # 업데이트 실행
                if updates:
                    await update_agent_config_tool.ainvoke({
                        "project_id": project_id,
                        "agent_id": agent.get("agent_id"),
                        "updates": updates
                    })
            
            # 4. 완료 보고 및 자동 재점검
            if updated_count > 0:
                result_msg = f"✅ {updated_count}개 항목이 자동으로 보강되었습니다.\n\n"
                yield result_msg
                full_content = result_msg
                
                # [FIX] 자동으로 완료 여부 재점검하여 JSON 출력
                p_data_updated = await neo4j_client.get_project(project_id)
                check_updated = self._check_completeness(p_data_updated)
                
                if check_updated["is_complete"]:
                    complete_msg = "✅ 모든 설정이 완료되었습니다! 아래 [START TASK] 버튼을 눌러 작업을 시작하세요.\n\n"
                    yield complete_msg
                    full_content += complete_msg
                    
                    # READY_TO_START JSON 출력
                    ready_json = json.dumps({
                        "status": "READY_TO_START", 
                        "final_summary": check_updated.get("final_summary", "모든 설정 완료"),
                        "mes_hash": check_updated.get("mes_hash", "")
                    }, ensure_ascii=False)
                    yield f"\n{ready_json}"
                    full_content += f"\n{ready_json}"
                else:
                    # 아직 미비한 항목이 있으면 보고
                    remaining_msg = f"⚠️ 아직 다음 항목이 미비합니다:\n- " + "\n- ".join(check_updated.get('missing', [])[:5])
                    yield remaining_msg
                    full_content += remaining_msg
            else:
                result_msg = "✅ 설정 변경이 완료되었습니다."
                yield result_msg
                full_content = result_msg
            
            await save_message_to_rdb("assistant", full_content, project_id, thread_id)
            return
        
        system_instruction = """[CRITICAL] 반드시 100% 순수 한국어로만 답변하십시오. 
[COMMAND] 
1. 호칭은 '사용자님'으로 통일하십시오. 
2. **[행동 우선]** 사용자가 "예", "응", "실행하자" 등 긍정하면 토 달지 말고 즉시 'READY_TO_START' 버튼을 생성하십시오. 로그 확인 지시나 추가 질문으로 시간을 끌지 마십시오.
3. 사용자가 요구사항을 추가하면 질문하지 말고 즉시 'update_agent_config_tool'로 DB를 업데이트한 뒤 보고하십시오.
4. **[절대 금지]** "시스템 관리자에게 문의하십시오", "로그를 확인하십시오" 같은 무책임한 발언을 금지합니다. 당신은 현장 지휘관입니다.
5. 모든 클라우드 모델의 Provider는 'OPENROUTER'로 입력하십시오.
"""

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
            
            # [v2.2 RULE 3] EXECUTION_REQUEST 처리 (강제 게이트)
            if intent == "EXECUTION_REQUEST":
                p_data = await neo4j_client.get_project(project_id)
                check = self._check_completeness(p_data)
                
                if check["is_complete"]: 
                    current_mes_hash = check.get("mes_hash")
                    
                    # [v2.2 RULE 3.1] ARMED 상태 설정 및 확정 토큰 확인
                    # 여기서는 "실행 확정", "작전 개시" 등 명시적 토큰이 있으므로 ARMED 설정
                    self.is_armed = True
                    self.armed_mes_hash = current_mes_hash
                    
                    # 버튼 생성 조건 충족 (AND)
                    # - intent == EXECUTION_REQUEST ✅
                    # - execution_state == ARMED ✅
                    # - current_mes_hash == armed_hash ✅
                    # - confirm_token_present == True ✅
                    ready_json = "\n" + json.dumps({
                        "status": "READY_TO_START", 
                        "final_summary": check["final_summary"],
                        "mes_hash": current_mes_hash
                    }, ensure_ascii=False)
                    yield ready_json; full_content += ready_json
                else:
                    # [v2.2 RULE 5] 자동 부착 제거: intent가 READINESS_CHECK가 아니면 제거
                    # 하지만 EXECUTION_REQUEST이면서 설정 미비인 경우는 보고서 출력
                    report = f"\n\n--- MISSION READINESS REPORT ---\n⚠️ 설정 미비로 확정할 수 없습니다:\n- " + "\n- ".join(check.get('missing', [])[:5])
                    yield report; full_content += report
            
            # [v2.2 RULE 5] 자동 부착 제거 (Response Builder)
            # intent가 READINESS_CHECK나 EXECUTION_REQUEST가 아닌 경우,
            # LLM이 생성한 응답에서 READINESS REPORT와 READY_TO_START JSON 제거
            if intent not in ["READINESS_CHECK", "EXECUTION_REQUEST", "STATUS_QUERY"]:
                import re
                # MISSION READINESS REPORT 제거
                full_content = re.sub(r'---\s*MISSION READINESS REPORT\s*---[\s\S]*?(?=\n\n|\Z)', '', full_content)
                # READY_TO_START JSON 제거
                full_content = re.sub(r'\{\s*"status"\s*:\s*"READY_TO_START"[\s\S]*?\}', '', full_content)
                # 조치 방법 가이드 제거
                full_content = re.sub(r'\*\*🛠️ 조치 방법[\s\S]*?(?=\n\n|\Z)', '', full_content)
                
        except Exception as e: yield f"\n[오류]: {str(e)}"
        finally:
            if full_content: await save_message_to_rdb("assistant", full_content, project_id, thread_id)

    async def process_message(self, message: str, history: List[ChatMessage], project_id: str = None, thread_id: str = None, user: Any = None, worker_status: Dict[str, Any] = None) -> Dict[str, Any]:
        # Simple wrapper for stream_message consistency
        return {"message": "Streaming only for master agent", "quick_links": []}

    async def create_job_from_history(self, history: List[ChatMessage], orchestrator: Any, user: Any) -> Dict[str, Any]: return {"message": "N/A"}
