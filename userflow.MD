안티그래비티 개발 지시문: BUJA Core Platform 사용자 시나리오 검증 및 기술스택 통합
📋 개요
현재 SYSTEM_OVERVIEW.md에 개발된 BUJA Core Platform을 검토한 결과, 사용자 시나리오의 핵심 기능들이 아직 미구현되어 있습니다. 본 지시문은 사용자 시나리오를 완전히 구현하기 위한 개발 작업을 단계별로 정의합니다.

🔍 GAP 분석: 사용자 시나리오 vs 현재 구현 상태
시나리오	요구사항	현재 상태	GAP
1. myllm 접속	사용자 인증 후 대시보드 접근	✅ JWT 인증 구현됨	-
2. 프로젝트 등록	기존/신규 프로젝트 관리	⚠️ Domain만 존재 (Project 개념 없음)	Project CRUD 필요
3. Agent 설정	프로젝트별 Agent 역할/조합 설정	❌ 미구현	Agent Config UI/API 필요
4. 오케스트라 코딩	Multi-Agent 워크플로우 실행	❌ 미구현	LangGraph 통합 필요
5. DB/온톨로지 저장	Neo4j/Pinecone 저장 및 시각화	❌ 미구현	Vector/Graph DB 연동 필요
📌 Phase 1: 프로젝트 관리 시스템 구축
1.1 Backend - Project API 개발
파일 위치: backend/app/api/v1/projects.py


# 구현해야 할 API 엔드포인트
"""
POST   /api/v1/projects                    # 프로젝트 생성
GET    /api/v1/projects                    # 사용자 프로젝트 목록
GET    /api/v1/projects/{project_id}       # 프로젝트 상세
PATCH  /api/v1/projects/{project_id}       # 프로젝트 수정
DELETE /api/v1/projects/{project_id}       # 프로젝트 삭제
POST   /api/v1/projects/{project_id}/agents  # Agent 설정 저장
GET    /api/v1/projects/{project_id}/agents  # Agent 설정 조회
"""
Project 데이터 모델:


class Project(BaseModel):
    id: str                          # UUID
    name: str                        # 프로젝트 이름
    description: Optional[str]
    project_type: Literal["EXISTING", "NEW"]  # 기존/신규 구분
    repo_path: Optional[str]         # 로컬 경로 (기존 프로젝트용)
    tenant_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    # Agent 설정
    agent_config: ProjectAgentConfig
    
class ProjectAgentConfig(BaseModel):
    workflow_type: Literal["SEQUENTIAL", "PARALLEL", "CUSTOM"]
    agents: List[AgentDefinition]
    entry_agent_id: str              # 시작 Agent
    
class AgentDefinition(BaseModel):
    agent_id: str
    role: str                        # "PLANNER", "CODER", "REVIEWER", "QA"
    model: str                       # "deepseek-chat", "mimo-v2-flash"
    provider: Literal["OPENROUTER", "OLLAMA"]
    system_prompt: str
    next_agents: List[str]           # 다음 단계 Agent ID들
1.2 Frontend - 프로젝트 관리 UI
파일 위치: frontend/src/app/projects/


projects/
├── page.tsx              # 프로젝트 목록
├── new/page.tsx          # 신규 프로젝트 생성
├── [projectId]/
│   ├── page.tsx          # 프로젝트 상세
│   ├── agents/page.tsx   # Agent 설정 페이지
│   └── workflow/page.tsx # 워크플로우 시각화
구현 요구사항:

프로젝트 목록 페이지

카드 형태로 프로젝트 표시
기존/신규 프로젝트 필터
검색 기능
프로젝트 생성 폼

프로젝트 타입 선택 (기존 연동 / 신규 생성)
기존 프로젝트: Git URL 또는 로컬 경로 입력
신규 프로젝트: 템플릿 선택
📌 Phase 2: Agent 설정 시스템 (LangGraph 통합)
2.1 Backend - Agent Configuration Service
파일 위치: backend/app/services/agent_config_service.py


class AgentConfigService:
    """
    Agent 설정을 Neo4j에 저장하고 LangGraph 워크플로우 생성
    """
    
    async def save_agent_config(
        self, 
        project_id: str, 
        config: ProjectAgentConfig
    ) -> None:
        """
        Neo4j에 Agent 구성 저장
        
        노드 생성:
        - (:Project {id: $project_id})
        - (:AgentRole {id: $agent_id, role: $role, model: $model, ...})
        
        관계 생성:
        - (Project)-[:HAS_AGENT]->(AgentRole)
        - (AgentRole)-[:NEXT_STEP]->(AgentRole)
        """
        pass
    
    async def load_agent_config(
        self, 
        project_id: str
    ) -> ProjectAgentConfig:
        """Neo4j에서 Agent 구성 로드"""
        pass
    
    async def build_langgraph_workflow(
        self, 
        config: ProjectAgentConfig
    ) -> CompiledGraph:
        """
        LangGraph StateGraph 빌드
        
        예시:
        graph = StateGraph(AgentState)
        for agent in config.agents:
            graph.add_node(agent.agent_id, create_agent_node(agent))
        for agent in config.agents:
            for next_id in agent.next_agents:
                graph.add_edge(agent.agent_id, next_id)
        graph.set_entry_point(config.entry_agent_id)
        return graph.compile()
        """
        pass
2.2 Agent 템플릿 (사전 정의된 설정)
파일 위치: backend/app/data/agent_templates.py


AGENT_TEMPLATES = {
    "coding_workflow": {
        "name": "기본 코딩 워크플로우",
        "description": "Planner → Coder → Reviewer → QA",
        "agents": [
            {
                "agent_id": "planner",
                "role": "PLANNER",
                "model": "deepseek-chat",
                "provider": "OPENROUTER",
                "system_prompt": "당신은 소프트웨어 아키텍트입니다...",
                "next_agents": ["coder"]
            },
            {
                "agent_id": "coder",
                "role": "CODER",
                "model": "mimo-v2-flash",
                "provider": "OLLAMA",
                "system_prompt": "당신은 Python 전문 개발자입니다...",
                "next_agents": ["reviewer"]
            },
            {
                "agent_id": "reviewer",
                "role": "REVIEWER",
                "model": "claude-3.5-sonnet",
                "provider": "OPENROUTER",
                "system_prompt": "당신은 코드 리뷰 전문가입니다...",
                "next_agents": ["qa"]
            },
            {
                "agent_id": "qa",
                "role": "QA",
                "model": "deepseek-chat",
                "provider": "OPENROUTER",
                "system_prompt": "당신은 QA 엔지니어입니다...",
                "next_agents": []  # 종료
            }
        ],
        "entry_agent_id": "planner"
    }
}
2.3 Frontend - Agent 설정 UI
파일 위치: frontend/src/app/projects/[projectId]/agents/page.tsx

UI 요구사항:

드래그 앤 드롭 Agent 배치

ReactFlow 활용
미리 정의된 Agent 타입 팔레트 (Planner, Coder, Reviewer, QA, Custom)
Agent 노드 설정 모달

역할 선택
LLM 모델 선택 (OpenRouter에서 제공하는 모델 목록)
시스템 프롬프트 편집
Provider 선택 (CLOUD/LOCAL)
워크플로우 연결

노드 간 Edge 연결 (Next Agent 설정)
조건부 분기 설정 (Optional)
템플릿 불러오기

사전 정의된 템플릿 선택하여 적용
📌 Phase 3: 오케스트라 코딩 실행 (Multi-Agent Workflow)
3.1 Backend - Orchestration Service
파일 위치: backend/app/services/orchestration_service.py


class OrchestrationService:
    """
    사용자 입력을 받아 Multi-Agent 워크플로우 실행
    """
    
    async def execute_workflow(
        self,
        project_id: str,
        user_input: str,
        user: User
    ) -> str:  # job_id 반환
        """
        1. 프로젝트의 Agent 설정 로드
        2. LangGraph 워크플로우 빌드
        3. 첫 번째 Agent에게 user_input 전달
        4. 워크플로우 실행 (각 단계별 Job 생성)
        5. 최종 결과 반환
        """
        
        # Step 1: Load config
        config = await self.agent_config_service.load_agent_config(project_id)
        
        # Step 2: Build workflow
        graph = await self.agent_config_service.build_langgraph_workflow(config)
        
        # Step 3: Create orchestration job
        orchestration_job_id = str(uuid.uuid4())
        
        # Step 4: Execute with streaming
        async for event in graph.astream(
            {"input": user_input, "messages": []},
            config={"configurable": {"thread_id": orchestration_job_id}}
        ):
            # 각 Agent 단계별로 상태 업데이트
            await self.update_step_status(orchestration_job_id, event)
            
            # LOCAL 실행이 필요한 경우 Job Queue에 추가
            if self.requires_local_execution(event):
                await self.create_local_job(event, project_id, user)
        
        return orchestration_job_id
3.2 실시간 진행 상황 API
파일 위치: backend/app/api/v1/orchestration.py


# 구현해야 할 API 엔드포인트
"""
POST /api/v1/projects/{project_id}/execute
    Request: {"input": "로그인 API를 만들어줘"}
    Response: {"orchestration_id": "uuid", "status": "STARTED"}

GET /api/v1/orchestrations/{orchestration_id}/status
    Response: {
        "orchestration_id": "uuid",
        "status": "RUNNING",
        "current_step": "coder",
        "steps": [
            {"agent": "planner", "status": "COMPLETED", "output": "..."},
            {"agent": "coder", "status": "RUNNING", "progress": 60},
            {"agent": "reviewer", "status": "PENDING"},
            {"agent": "qa", "status": "PENDING"}
        ]
    }

WebSocket /api/v1/orchestrations/{orchestration_id}/stream
    # 실시간 진행 상황 스트리밍
"""
3.3 Frontend - 실행 및 모니터링 UI
파일 위치: frontend/src/app/projects/[projectId]/execute/page.tsx

UI 요구사항:

입력 영역

텍스트 입력 또는 아이디어 입력
파일 업로드 (컨텍스트 제공)
실행 진행 상황 표시

각 Agent 단계별 진행률
현재 실행 중인 Agent 하이라이트
각 단계 출력 미리보기
결과 표시

생성된 코드 diff 표시
파일 트리 변경 사항
적용/롤백 버튼
📌 Phase 4: 기술스택 통합 (Neo4j, Pinecone, LangFuse)
4.1 Neo4j AuraDB 연동
파일 위치: backend/app/core/neo4j_client.py


from neo4j import AsyncGraphDatabase

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    async def create_project_graph(self, project: Project):
        """프로젝트 및 Agent 관계 저장"""
        query = """
        MERGE (p:Project {id: $project_id})
        SET p.name = $name, p.tenant_id = $tenant_id
        
        WITH p
        UNWIND $agents AS agent
        MERGE (a:AgentRole {id: agent.agent_id})
        SET a.role = agent.role, a.model = agent.model
        MERGE (p)-[:HAS_AGENT]->(a)
        
        WITH p, a, agent
        UNWIND agent.next_agents AS next_id
        MATCH (next:AgentRole {id: next_id})
        MERGE (a)-[:NEXT_STEP]->(next)
        """
        async with self.driver.session() as session:
            await session.run(query, {
                "project_id": project.id,
                "name": project.name,
                "tenant_id": project.tenant_id,
                "agents": [a.dict() for a in project.agent_config.agents]
            })
    
    async def get_knowledge_graph(self, tenant_id: str) -> dict:
        """지식 그래프 조회 (시각화용)"""
        query = """
        MATCH (p:Project {tenant_id: $tenant_id})-[r]->(n)
        RETURN p, r, n
        """
        async with self.driver.session() as session:
            result = await session.run(query, {"tenant_id": tenant_id})
            return await self._format_for_visualization(result)
환경 변수 추가:


NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
4.2 Pinecone 연동 (Vector DB)
파일 위치: backend/app/core/pinecone_client.py


from pinecone import Pinecone

class PineconeClient:
    def __init__(self, api_key: str, index_name: str):
        self.pc = Pinecone(api_key=api_key)
        self.index = self.pc.Index(index_name)
    
    async def upsert_knowledge(
        self, 
        tenant_id: str, 
        user_id: str,
        content: str,
        metadata: dict
    ):
        """지식 임베딩 저장"""
        embedding = await self.get_embedding(content)
        namespace = f"{tenant_id}_{user_id}"
        
        self.index.upsert(
            vectors=[{
                "id": str(uuid.uuid4()),
                "values": embedding,
                "metadata": {
                    **metadata,
                    "content": content[:1000],  # 미리보기
                    "tenant_id": tenant_id
                }
            }],
            namespace=namespace
        )
    
    async def search_knowledge(
        self,
        tenant_id: str,
        user_id: str,
        query: str,
        top_k: int = 5
    ) -> List[dict]:
        """유사 지식 검색"""
        embedding = await self.get_embedding(query)
        namespace = f"{tenant_id}_{user_id}"
        
        results = self.index.query(
            vector=embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
        return [match.metadata for match in results.matches]
환경 변수 추가:


PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=buja-knowledge
4.3 LangFuse 통합 (Observability)
파일 위치: backend/app/core/langfuse_client.py


from langfuse import Langfuse
from langfuse.decorators import observe

class LangFuseClient:
    def __init__(self):
        self.langfuse = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        )
    
    @observe(name="agent_execution")
    async def trace_agent_execution(
        self,
        agent_id: str,
        input_text: str,
        output_text: str,
        model: str,
        latency_ms: int,
        tokens_used: int
    ):
        """Agent 실행 추적"""
        self.langfuse.trace(
            name=f"agent_{agent_id}",
            input=input_text,
            output=output_text,
            metadata={
                "model": model,
                "latency_ms": latency_ms,
                "tokens": tokens_used
            }
        )
환경 변수 추가:


LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com
4.4 Tavily Search 통합
파일 위치: backend/app/services/search_service.py


from tavily import TavilyClient

class SearchService:
    def __init__(self):
        self.tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    
    async def web_search(self, query: str, max_results: int = 5) -> List[dict]:
        """웹 검색 수행"""
        response = self.tavily.search(
            query=query,
            search_depth="advanced",
            max_results=max_results
        )
        return response["results"]
    
    async def search_and_summarize(self, query: str) -> str:
        """검색 후 요약"""
        response = self.tavily.qna_search(query=query)
        return response["answer"]
환경 변수 추가:


TAVILY_API_KEY=tvly-xxxxxxxx
📌 Phase 5: Frontend 시각화 (LangGraph/LangFuse)
5.1 워크플로우 시각화 (ReactFlow)
파일 위치: frontend/src/components/WorkflowVisualizer.tsx


import ReactFlow, { Node, Edge, Background, Controls } from 'reactflow';

interface WorkflowVisualizerProps {
  agents: AgentDefinition[];
  currentStep?: string;
  stepStatuses: Record<string, 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'>;
}

export function WorkflowVisualizer({ agents, currentStep, stepStatuses }: WorkflowVisualizerProps) {
  const nodes: Node[] = agents.map((agent, index) => ({
    id: agent.agent_id,
    position: { x: index * 250, y: 100 },
    data: { 
      label: agent.role,
      model: agent.model,
      status: stepStatuses[agent.agent_id] || 'PENDING'
    },
    type: 'agentNode',
    style: getNodeStyle(stepStatuses[agent.agent_id], agent.agent_id === currentStep)
  }));

  const edges: Edge[] = agents.flatMap(agent =>
    agent.next_agents.map(nextId => ({
      id: `${agent.agent_id}-${nextId}`,
      source: agent.agent_id,
      target: nextId,
      animated: agent.agent_id === currentStep
    }))
  );

  return (
    <ReactFlow nodes={nodes} edges={edges}>
      <Background />
      <Controls />
    </ReactFlow>
  );
}
5.2 LangFuse 대시보드 임베딩
파일 위치: frontend/src/app/projects/[projectId]/traces/page.tsx


export default function TracesPage({ params }: { params: { projectId: string } }) {
  return (
    <div className="h-screen">
      <h1>실행 추적 (LangFuse)</h1>
      
      {/* LangFuse Public Dashboard Embed */}
      <iframe
        src={`https://cloud.langfuse.com/project/${process.env.LANGFUSE_PROJECT_ID}/traces?filter=project_id=${params.projectId}`}
        className="w-full h-full border-0"
      />
      
      {/* 또는 자체 API로 데이터 조회하여 표시 */}
    </div>
  );
}
📌 Implementation Checklist
Backend Tasks
 POST /api/v1/projects - 프로젝트 생성 API
 GET /api/v1/projects - 프로젝트 목록 API
 POST /api/v1/projects/{id}/agents - Agent 설정 저장 API
 Neo4j 클라이언트 구현 (neo4j_client.py)
 Pinecone 클라이언트 구현 (pinecone_client.py)
 LangFuse 통합 (langfuse_client.py)
 Tavily Search 통합 (search_service.py)
 OrchestrationService 구현 (LangGraph 워크플로우 빌드)
 WebSocket 실시간 스트리밍 엔드포인트
Frontend Tasks
 /projects - 프로젝트 목록 페이지
 /projects/new - 프로젝트 생성 페이지
 /projects/[id]/agents - Agent 설정 페이지 (ReactFlow)
 /projects/[id]/execute - 실행 페이지
 /projects/[id]/traces - 실행 추적 페이지
 WorkflowVisualizer 컴포넌트
 Agent 노드 설정 모달
Infrastructure Tasks
 Neo4j AuraDB Free Tier 생성 및 연결
 Pinecone 인덱스 생성 (dimension: 1536 for OpenAI embeddings)
 LangFuse 프로젝트 생성
 Tavily API 키 발급
 환경 변수 업데이트 (.env)
🚀 실행 우선순위
Phase 1 (프로젝트 관리) - 1주

핵심: 사용자가 프로젝트를 등록하고 관리할 수 있어야 함
Phase 2 (Agent 설정) - 1주

핵심: 프로젝트별 Agent 구성을 시각적으로 설정
Phase 4 (DB 연동) - 1주 (Phase 2와 병행 가능)

핵심: Neo4j/Pinecone 연결하여 데이터 영속화
Phase 3 (오케스트라 실행) - 2주

핵심: LangGraph로 Multi-Agent 워크플로우 실행
Phase 5 (시각화) - 1주

핵심: 실행 상태 실시간 모니터링
⚠️ 주의사항
보안: SYSTEM_OVERVIEW.md의 Ed25519 서명 검증 로직을 유지할 것
멀티테넌시: 모든 쿼리에 tenant_id 필터 필수
RBAC: LOCAL_MACHINE 실행은 SUPER_ADMIN 또는 Domain 권한 있는 사용자만
OpenRouter 모델: DeepSeek V3, Claude 3.5 Sonnet 등 선택 가능하도록 동적 모델 목록 제공