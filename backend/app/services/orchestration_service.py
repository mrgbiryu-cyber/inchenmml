import asyncio
import json
from typing import Dict, Any, List
from uuid import UUID

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.models.schemas import (
    Project, 
    ProjectAgentConfig, 
    AgentDefinition, 
    JobCreate, 
    ExecutionLocation, 
    ProviderType, 
    JobStatus,
    User
)
from app.services.job_manager import JobManager
from app.services.agent_config_service import AgentState

class OrchestrationService:
    """
    Orchestrates the execution of multi-agent workflows using LangGraph and JobManager.
    """
    
    def __init__(self, job_manager: JobManager, redis_client=None):
        self.job_manager = job_manager
        self.redis_client = redis_client

    async def execute_workflow(self, project: Project, user: User) -> str:
        """
        Start the workflow execution for a project.
        """
        if not project.agent_config:
            raise ValueError("Project has no agent configuration")

        # Build the graph
        workflow = self._build_langgraph(project, user)
        
        # Initialize state
        initial_state = AgentState(
            messages=[HumanMessage(content=f"Start workflow for project: {project.name}")],
            current_agent="START",
            next_agent=project.agent_config.entry_agent_id,
            artifacts={},
            ux_issues=[],
            is_started=True, # [Fix] Set to True as this is triggered by the START button
            approval_granted=False,
            retry_count=0
        )
        
        # Run the workflow (Async)
        asyncio.create_task(self._run_workflow(workflow, initial_state, project.id))
        
        return "Workflow started"

    def _build_langgraph(self, project: Project, user: User):
        """
        Build the StateGraph with nodes that dispatch jobs
        """
        print(f"DEBUG: Building LangGraph for Project: {project.id}")
        workflow = StateGraph(AgentState)
        config = project.agent_config
        
        if not config or not config.agents:
            raise ValueError(f"Project {project.id} has no agents configured")

        agent_ids = [a.agent_id for a in config.agents]
        
        # 1. Add Master/Planning Node (Virtual)
        async def master_planning(state: AgentState):
            print("🚀 [Master] Planning complete.")
            return {"messages": [AIMessage(content='Planning finished.')]}
        
        workflow.add_node("master_planning", master_planning)

        # Agent Nodes
        for agent in config.agents:
            # [Fix] Use default argument to capture current agent_def in closure
            def create_node(a_def=agent):
                return self._create_agent_node(a_def, project, user)
            
            workflow.add_node(agent.agent_id, create_node())
            
        # 3. Define Edges
        workflow.set_entry_point("master_planning")
        workflow.add_edge("master_planning", config.entry_agent_id)

        # Agent to Agent Edges
        for agent in config.agents:
            # [고도화] 검수자(REVIEWER) 또는 QA 역할의 피드백 루프 처리
            if agent.role in ["REVIEWER", "QA"]:
                # [Fix] Use default argument to capture current agent in closure
                def reviewer_routing(state: AgentState, current_agent=agent):
                    # 1. 마지막 작업 결과 확인
                    last_result = state.get("artifacts", {}).get(current_agent.agent_id, {})
                    is_failed = last_result.get("status") == "FAILED" or last_result.get("need_fix") is True
                    
                    if is_failed:
                        # 2. 재시도 횟수 체크 (최대 3회)
                        current_retry = state.get("retry_count", 0)
                        if current_retry < 3:
                            # 3. 되돌아갈 개발자(CODER) 찾기
                            coder_id = next((a.agent_id for a in config.agents if a.role in ["CODER", "DEVELOPER"]), None)
                            if coder_id:
                                print(f"🔄 [피드백 루프] 검수 실패. 개발자({coder_id})에게 재작업 요청 (시도 {current_retry + 1}/3)")
                                return coder_id
                        
                        print(f"❌ [피드백 루프] {current_retry}회 재시도 초과. 작업을 강제 종료합니다.")
                        return END
                    
                    # 4. 검수 통과 시 다음 단계로 진행 (마지막이면 종료)
                    if not current_agent.next_agents:
                        return END
                    return current_agent.next_agents[0]
                
                workflow.add_conditional_edges(agent.agent_id, reviewer_routing)
            else:
                # [Fix] Use default argument to capture current agent in closure
                def sequential_routing(state: AgentState, current_agent=agent):
                    if not current_agent.next_agents:
                        return END
                    
                    next_id = current_agent.next_agents[0]
                    return next_id if next_id in agent_ids else END

                workflow.add_conditional_edges(agent.agent_id, sequential_routing)
        
        # [Fix] Increase recursion limit and return compiled graph
        compiled_graph = workflow.compile()
        compiled_graph.recursion_limit = 50 
        return compiled_graph
        
        # Edge from ask_approval to GIT or END
        def approval_routing(state: AgentState):
            if state.get("approval_granted"):
                git_id = next((a.agent_id for a in config.agents if a.role == "GIT"), None)
                return git_id if git_id else END
            return "ask_approval"

        workflow.add_conditional_edges("ask_approval", approval_routing)
        
        # [Fix] Increase recursion limit to handle complex feedback loops
        return workflow.compile()

    async def _run_workflow(self, workflow, initial_state: AgentState, project_id: str):
        """
        Internal loop to run the compiled graph
        """
        try:
            print(f"DEBUG: Starting Graph Execution for Project: {project_id}")
            await self._publish_event(project_id, "WORKFLOW_STARTED", {
                "project_id": project_id,
                "message": "🚀 워크플로우를 시작합니다."
            })
            
            async for event in workflow.astream(initial_state):
                for node_name, state_update in event.items():
                    print(f"DEBUG: [Node: {node_name}] completed.")
                    
                    # 노드 이름별 한글 설명 매핑
                    display_names = {
                        "master_planning": "📝 마스터 플래닝 (작업 계획 수립)",
                        "wait_for_start": "⏳ 사용자 승인 대기 중",
                        "agent_planner_master": "📋 기획 에이전트 작업 중",
                        "agent_coder_master": "💻 개발 에이전트 코드 작성 중",
                        "agent_reviewer_master": "🔍 리뷰 에이전트 검토 중",
                        "ask_approval": "🚦 최종 배포 승인 대기 중"
                    }
                    display_name = display_names.get(node_name, f"⚙️ {node_name} 작업 완료")

                    await self._publish_event(project_id, "AGENT_COMPLETED", {
                        "agent_id": node_name,
                        "node": node_name,
                        "status": "COMPLETED",
                        "message": f"✅ {display_name} 완료"
                    })
            
            await self._publish_event(project_id, "WORKFLOW_FINISHED", {
                "project_id": project_id,
                "message": "🎉 모든 작업이 끝났습니다! 이제 결과를 확인해 보세요."
            })
                    
        except Exception as e:
            import traceback
            print(f"ERROR: [OrchestrationService] Graph execution failed: {e}")
            traceback.print_exc()
            await self._publish_event(project_id, "WORKFLOW_FAILED", {
                "error": str(e),
                "message": f"❌ 워크플로우 실행 중 오류 발생: {str(e)}"
            })

    async def _publish_event(self, project_id: str, event_type: str, data: Dict[str, Any]):
        """
        Publish execution events to Redis for frontend log synchronization
        """
        if not self.redis_client:
            return
            
        import time
        event = {
            "type": event_type,
            "project_id": project_id,
            "data": data,
            "timestamp": time.time()
        }
        
        event_json = json.dumps(event, ensure_ascii=False)
        
        # [Fix] Channel name MUST match WebSocket subscription in orchestration.py
        channel = f"orchestration:{project_id}"
        await self.redis_client.publish(channel, event_json)
        
        # Also store in Redis LIST with TTL for late joiners
        event_key = f"events:history:{project_id}"
        await self.redis_client.rpush(event_key, event_json)
        await self.redis_client.expire(event_key, 600)  # 10 minute TTL
        
        print(f"DEBUG: [Event] {event_type} published to {channel}")

    def _create_agent_node(self, agent_def: AgentDefinition, project: Project, user: User):
        """
        Create a runnable node that dispatches a job to the Worker
        """
        async def agent_node(state: AgentState):
            role_kr = {
                "PLANNER": "기획",
                "CODER": "개발",
                "REVIEWER": "리뷰",
                "QA": "테스트",
                "GIT": "배포"
            }.get(agent_def.role, agent_def.role)

            print(f"🚀 [Orchestrator] Executing Agent: {agent_def.agent_id} ({agent_def.role})")
            await self._publish_event(project.id, "AGENT_STARTED", {
                "agent_id": agent_def.agent_id, 
                "role": agent_def.role,
                "message": f"📋 {role_kr} 에이전트가 작업을 시작했습니다."
            })
            
            # ... (Job creation logic remains same) ...
            agent_config = agent_def.config if agent_def.config else {}
            repo_root = agent_config.get("repo_root") or project.repo_path or "D:/project/myllm"
            allowed_paths = agent_config.get("allowed_paths") or ([repo_root] if repo_root else ["D:/project/myllm"])
            tool_allowlist = agent_config.get("tool_allowlist")

            try:
                # [Fix] 모델 제작사 이름을 Provider로 보낼 경우 OPENROUTER로 자동 매핑
                p_val = str(agent_def.provider).upper()
                cloud_providers = ["GOOGLE", "OPENAI", "ANTHROPIC", "DEEPSEEK", "OPENROUTER"]
                
                if p_val in cloud_providers:
                    p_type = ProviderType.OPENROUTER
                elif p_val == "OLLAMA":
                    p_type = ProviderType.OLLAMA
                else:
                    p_type = ProviderType.OPENROUTER # 기본값은 클라우드로 안전하게 설정
            except Exception:
                p_type = ProviderType.OPENROUTER

            job_request = JobCreate(
                execution_location=ExecutionLocation.LOCAL_MACHINE,
                provider=p_type,
                model=agent_def.model,
                repo_root=repo_root,
                allowed_paths=allowed_paths,
                steps=[
                    f"🎯 Objective: {agent_def.system_prompt[:200]}...",
                    f"📂 Path: {repo_root}",
                    f"🔧 Role: {agent_def.role}"
                ],
                metadata={
                    "project_id": project.id,
                    "agent_id": agent_def.agent_id,
                    "role": agent_def.role,
                    "system_prompt": agent_def.system_prompt,
                    "tool_allowlist": tool_allowlist,
                    "current_ux_issues": state.get("ux_issues", [])
                }
            )
            
            try:
                job = await self.job_manager.create_job(user, job_request)
                await self._publish_event(project.id, "JOB_CREATED", {
                    "agent_id": agent_def.agent_id, 
                    "job_id": str(job.job_id),
                    "message": f"⚙️ 워커에 일감이 생성되었습니다 (Job ID: {str(job.job_id)[:8]})"
                })
            except Exception as e:
                await self._publish_event(project.id, "AGENT_FAILED", {
                    "agent_id": agent_def.agent_id, 
                    "error": str(e),
                    "message": f"❌ 일감 생성 실패: {str(e)}"
                })
                return {"messages": [AIMessage(content=f"Job creation failed: {e}")]}

            job_id = str(job.job_id)
            while True:
                status_data = await self.job_manager.get_job_status(job_id, user)
                status = status_data["status"]
                if status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                    result = status_data.get("result")
                    break
                await asyncio.sleep(2)
                
            if status == JobStatus.COMPLETED.value:
                output = result.get("output", {}) if result else {}
                large_change = output.get("large_change_detected", False)
                
                # [고도화] 검수 결과에 따른 재시도 횟수 관리
                new_retry_count = state.get("retry_count", 0)
                if agent_def.role in ["REVIEWER", "QA"]:
                    is_failed = output.get("status") == "FAILED" or output.get("need_fix") is True
                    if is_failed:
                        new_retry_count += 1 # 실패 시 카운트 증가
                
                await self._publish_event(project.id, "AGENT_COMPLETED", {
                    "agent_id": agent_def.agent_id, 
                    "output": output,
                    "large_change": large_change,
                    "retry_count": new_retry_count,
                    "message": f"✅ {role_kr} 에이전트 작업 완료."
                })
                
                return {
                    "current_agent": agent_def.agent_id,
                    "messages": [AIMessage(content=f"Agent {agent_def.agent_id} completed task.")],
                    "artifacts": {**state.get("artifacts", {}), agent_def.agent_id: output},
                    "ux_issues": output.get("ux_issues", []),
                    "large_change_detected": large_change or state.get("large_change_detected", False),
                    "retry_count": new_retry_count # 상태 업데이트
                }
            else:
                await self._publish_event(project.id, "AGENT_FAILED", {
                    "agent_id": agent_def.agent_id, 
                    "error": "Job failed",
                    "message": f"⚠️ {role_kr} 에이전트 작업 실패."
                })
                return {
                    "current_agent": agent_def.agent_id,
                    "messages": [AIMessage(content=f"Agent {agent_def.agent_id} failed.")]
                }
            
        return agent_node
